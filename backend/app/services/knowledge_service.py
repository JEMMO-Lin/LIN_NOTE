"""知识点、知识树和知识问答服务。"""
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError
from app.core.config import settings
from app.models.knowledge_base import KnowledgeBase
from app.models.content_item import ContentItem
from app.models.knowledge_point import KnowledgePoint
from app.schemas.knowledge_point import KnowledgePointUpdate
from app.services.ai_service import AIService
from app.services.search_service import SearchService
from app.services.interfaces.search_service import SearchHit
from app.services.wiki_service import WikiService


@dataclass
class AnswerResult:
    answer: str
    hits: list[SearchHit]
    answer_source: str = "rag"
    wiki_hit: bool = False
    ask_count: int = 0
    wiki_entry_id: str | None = None
    wiki_created: bool = False


class KnowledgeService:
    def __init__(
        self,
        db: AsyncSession,
        ai_service: AIService | None = None,
        search_service: SearchService | None = None,
    ):
        self.db = db
        self.ai = ai_service
        self.search = search_service

    async def list_points(
        self,
        user_id: str,
        kb_id: str,
        content_id: str | None = None,
        category: str | None = None,
    ) -> list[KnowledgePoint]:
        await self._ensure_kb_access(user_id, kb_id)
        stmt = (
            select(KnowledgePoint)
            .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
            .where(
                KnowledgePoint.kb_id == kb_id,
                ContentItem.merge_status == "active",
            )
        )
        if content_id:
            stmt = stmt.where(KnowledgePoint.content_id == content_id)
        if category:
            stmt = stmt.where(KnowledgePoint.category == category)
        result = await self.db.execute(
            stmt.order_by(KnowledgePoint.importance.desc(), KnowledgePoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_point(self, user_id: str, point_id: str) -> KnowledgePoint:
        point = await self.db.get(KnowledgePoint, point_id)
        if point is None:
            raise NotFoundError("知识点不存在")
        await self._ensure_kb_access(user_id, str(point.kb_id))
        return point

    async def update_point(
        self, user_id: str, point_id: str, payload: KnowledgePointUpdate
    ) -> KnowledgePoint:
        point = await self.get_point(user_id, point_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(point, key, value)
        await self.db.flush()
        return point

    async def delete_point(self, user_id: str, point_id: str) -> None:
        point = await self.get_point(user_id, point_id)
        await self.db.delete(point)
        await self.db.flush()

    async def build_tree(self, user_id: str, kb_id: str) -> dict:
        points = await self.list_points(user_id, kb_id)
        nodes = [
            {
                "id": str(point.id),
                "label": point.title,
                "category": point.category,
                "importance": point.importance,
                "content_id": str(point.content_id),
            }
            for point in points
        ]
        edges = []
        point_ids = {str(point.id) for point in points}
        for point in points:
            for related in point.related_points:
                if related in point_ids:
                    edges.append(
                        {"source": str(point.id), "target": related, "relation": "related"}
                    )
        if not edges:
            grouped: dict[str, list[KnowledgePoint]] = defaultdict(list)
            for point in points:
                grouped[point.category or "未分类"].append(point)
            for group in grouped.values():
                for left, right in zip(group, group[1:]):
                    edges.append(
                        {
                            "source": str(left.id),
                            "target": str(right.id),
                            "relation": "same_category",
                        }
                    )
        return {"nodes": nodes, "edges": edges}

    async def answer(
        self, user_id: str, question: str, kb_id: str | None, top_k: int
    ) -> tuple[str, list]:
        """Backward-compatible answer API returning the original tuple."""
        result = await self.answer_with_meta(user_id, question, kb_id, top_k)
        return result.answer, result.hits

    async def answer_with_meta(
        self, user_id: str, question: str, kb_id: str | None, top_k: int
    ) -> AnswerResult:
        if kb_id:
            await self._ensure_kb_access(user_id, kb_id)
        if self.search is None or self.ai is None:
            return AnswerResult("知识问答服务尚未配置。", [])

        wiki: WikiService | None = None
        wiki_entry = None
        if settings.llm_wiki_enabled:
            wiki = WikiService(self.db, settings.llm_wiki_publish_threshold)
            lookup = await wiki.record_and_lookup(user_id, question, kb_id)
            wiki_entry = lookup.entry
            if lookup.is_hit:
                return AnswerResult(
                    answer=wiki_entry.answer or "",
                    hits=wiki.restore_sources(wiki_entry),
                    answer_source="wiki",
                    wiki_hit=True,
                    ask_count=wiki_entry.ask_count,
                    wiki_entry_id=str(wiki_entry.id),
                )

        hits = await self.search.search_documents(
            question, kb_id, mode="hybrid", top_k=top_k
        )
        if not hits and kb_id:
            # Database fallback is limited to slices generated after distillation.
            result = await self.db.execute(
                select(KnowledgePoint)
                .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
                .where(
                    KnowledgePoint.kb_id == kb_id,
                    ContentItem.merge_status == "active",
                    ContentItem.distilled_text.is_not(None),
                )
                .order_by(KnowledgePoint.importance.desc())
                .limit(top_k)
            )
            points = list(result.scalars().all())
            hits = [
                SearchHit(
                    point_id=str(point.id),
                    title=point.title,
                    content=point.content,
                    score=max(0.35, point.importance * 0.7),
                    content_id=str(point.content_id),
                    kb_id=str(point.kb_id),
                )
                for point in points[:top_k]
            ]
        if kb_id is None:
            allowed = await self._allowed_kb_ids(user_id)
            hits = [hit for hit in hits if hit.kb_id in allowed]
        context = "\n\n".join(
            f"[{index + 1}] {hit.title}\n{hit.content}"
            for index, hit in enumerate(hits)
        )
        answer = await self.ai.answer(question, context)
        wiki_created = False
        if wiki is not None and wiki_entry is not None:
            wiki_created = await wiki.learn(wiki_entry, answer, hits)
        return AnswerResult(
            answer=answer,
            hits=hits,
            ask_count=wiki_entry.ask_count if wiki_entry is not None else 0,
            wiki_entry_id=str(wiki_entry.id) if wiki_entry is not None else None,
            wiki_created=wiki_created,
        )

    async def _allowed_kb_ids(self, user_id: str) -> set[str]:
        result = await self.db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.user_id == user_id)
        )
        return {str(value) for value in result.scalars().all()}

    async def _ensure_kb_access(self, user_id: str, kb_id: str) -> None:
        kb = await self.db.get(KnowledgeBase, kb_id)
        if kb is None:
            raise NotFoundError("知识库不存在")
        if str(kb.user_id) != user_id:
            raise PermissionError("无权访问该知识库")
