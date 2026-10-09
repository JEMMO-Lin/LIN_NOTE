"""内容相似检测、预览、合并与历史记录。"""
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError, ValidationError
from app.models.content_item import ContentItem
from app.models.knowledge_base import KnowledgeBase
from app.models.merge_history import MergeHistory
from app.models.knowledge_point import KnowledgePoint
from app.services.ai_service import AIService
from app.services.interfaces.search_service import ISearchService


class MergeService:
    """内容合并应用服务"""

    def __init__(
        self,
        db: AsyncSession,
        search_engine: ISearchService,
        ai_service: AIService,
        similarity_threshold: float = 0.85,
    ):
        self.db = db
        self.search = search_engine
        self.ai = ai_service
        self.threshold = similarity_threshold

    async def find_duplicates_for_content(
        self,
        user_id: str,
        content_id: str,
        threshold: float | None = None,
        top_k: int = 8,
    ) -> list[dict]:
        item = await self._get_owned_content(user_id, content_id)
        minimum = threshold if threshold is not None else self.threshold
        hits = await self.search.search(
            f"{item.title}\n{self._knowledge_text(item)}",
            str(item.kb_id),
            mode="hybrid",
            top_k=top_k + 1,
        )
        by_id: dict[str, float] = {}
        for hit in hits:
            if hit.content_id and hit.content_id != content_id:
                by_id[hit.content_id] = max(by_id.get(hit.content_id, 0), hit.score)

        result = await self.db.execute(
            select(ContentItem).where(
                ContentItem.kb_id == item.kb_id,
                ContentItem.id != item.id,
                ContentItem.merge_status == "active",
            )
        )
        candidates = list(result.scalars().all())
        duplicates = []
        for candidate in candidates:
            candidate_id = str(candidate.id)
            lexical = max(
                SequenceMatcher(
                    None, item.title.lower(), candidate.title.lower()
                ).ratio(),
                SequenceMatcher(
                    None,
                    self._knowledge_text(item)[:3000].lower(),
                    self._knowledge_text(candidate)[:3000].lower(),
                ).ratio(),
                SequenceMatcher(
                    None,
                    (item.summary or "")[:1000].lower(),
                    (candidate.summary or "")[:1000].lower(),
                ).ratio(),
            )
            score = max(by_id.get(candidate_id, 0), lexical)
            if score >= minimum:
                duplicates.append(
                    {
                        "id": candidate_id,
                        "title": candidate.title,
                        "summary": candidate.summary,
                        "source_type": candidate.source_type,
                        "similarity": round(score, 4),
                        "created_at": candidate.created_at.isoformat(),
                    }
                )
        return sorted(duplicates, key=lambda value: value["similarity"], reverse=True)[:top_k]

    async def preview(
        self, user_id: str, target_content_id: str, source_content_ids: list[str]
    ) -> dict:
        items = await self._load_merge_items(user_id, target_content_id, source_content_ids)
        merged_text = await self.ai.merge(
            [
                item.distilled_text
                if item.distilled_text is not None
                else (item.summary or item.original_text)
                for item in items
            ]
        )
        merged_summary_result = await self.ai.summarize(merged_text, style="medium")
        merged_summary = merged_summary_result.get("summary", merged_text[:300])
        return {
            "target_id": target_content_id,
            "source_ids": source_content_ids,
            "merged_title": items[0].title,
            "merged_summary": merged_summary,
            "merged_text": merged_text,
            "conflicts": self._detect_conflicts(items),
        }

    async def merge_into(
        self, user_id: str, target_content_id: str, source_content_ids: list[str]
    ) -> tuple[ContentItem, MergeHistory]:
        items = await self._load_merge_items(user_id, target_content_id, source_content_ids)
        target, sources = items[0], items[1:]
        preview = await self.preview(user_id, target_content_id, source_content_ids)
        target.original_text = preview["merged_text"]
        target.distilled_text = preview["merged_text"]
        target.summary = preview["merged_summary"]
        target.extracted_knowledge = {
            "summary": preview["merged_summary"],
            "distillation": {
                "main_topic": target.title,
                "removed_noise_types": ["合并时过滤的重复或非知识信息"],
                "method": "merge",
            },
        }
        target.status = "processed"
        target.metadata_json = {
            **(target.metadata_json or {}),
            "merged_from": [str(item.id) for item in sources],
        }
        for source in sources:
            source.merge_status = "merged"
            source.merged_into_id = target.id

        # The target's old slices described the pre-merge material. Rebuild
        # them from the filtered merged text so stale promotions cannot survive.
        await self.db.execute(
            delete(KnowledgePoint).where(KnowledgePoint.content_id == target.id)
        )
        points = await self.ai.extract_knowledge_points(preview["merged_text"])
        for point in points:
            try:
                importance = min(1.0, max(0.0, float(point.get("importance", 0.5))))
            except (TypeError, ValueError):
                importance = 0.5
            self.db.add(
                KnowledgePoint(
                    content_id=target.id,
                    kb_id=target.kb_id,
                    title=point.get("title", "未命名知识点"),
                    content=point.get("content", ""),
                    category=point.get("category", ""),
                    importance=importance,
                )
            )

        history = MergeHistory(
            user_id=user_id,
            kb_id=target.kb_id,
            target_id=target.id,
            source_ids=[str(item.id) for item in sources],
            source_titles=[item.title for item in sources],
            merged_result_id=target.id,
            summary=preview["merged_summary"],
            conflicts=preview["conflicts"],
        )
        self.db.add(history)
        await self.db.flush()
        await self.db.refresh(target)
        await self.db.refresh(history)
        return target, history

    async def list_history(
        self, user_id: str, kb_id: str | None = None, content_id: str | None = None
    ) -> list[MergeHistory]:
        stmt = select(MergeHistory).where(MergeHistory.user_id == user_id)
        if kb_id:
            await self._ensure_kb_access(user_id, kb_id)
            stmt = stmt.where(MergeHistory.kb_id == kb_id)
        if content_id:
            stmt = stmt.where(MergeHistory.merged_result_id == content_id)
        result = await self.db.execute(stmt.order_by(MergeHistory.created_at.desc()))
        return list(result.scalars().all())

    async def _load_merge_items(
        self, user_id: str, target_content_id: str, source_content_ids: list[str]
    ) -> list[ContentItem]:
        unique_ids = list(dict.fromkeys([target_content_id, *source_content_ids]))
        if len(unique_ids) < 2:
            raise ValidationError("至少选择两条不同内容进行合并")
        items = [await self._get_owned_content(user_id, item_id) for item_id in unique_ids]
        if len({str(item.kb_id) for item in items}) != 1:
            raise ValidationError("只能合并同一知识库中的内容")
        if any(item.merge_status != "active" for item in items):
            raise ValidationError("已被合并或归档的内容不能再次合并")
        return items

    @staticmethod
    def _knowledge_text(item: ContentItem) -> str:
        if item.distilled_text is not None:
            return item.distilled_text
        return item.summary or ""

    async def _get_owned_content(self, user_id: str, content_id: str) -> ContentItem:
        item = await self.db.get(ContentItem, content_id)
        if item is None:
            raise NotFoundError("内容不存在")
        await self._ensure_kb_access(user_id, str(item.kb_id))
        return item

    async def _ensure_kb_access(self, user_id: str, kb_id: str) -> None:
        kb = await self.db.get(KnowledgeBase, kb_id)
        if kb is None:
            raise NotFoundError("知识库不存在")
        if str(kb.user_id) != user_id:
            raise PermissionError("无权访问该知识库")

    @staticmethod
    def _detect_conflicts(items: list[ContentItem]) -> list[dict]:
        conflicts = []
        summaries = [item.summary for item in items if item.summary]
        if len(summaries) > 1:
            similarity = min(
                SequenceMatcher(None, summaries[0], summary).ratio()
                for summary in summaries[1:]
            )
            if similarity < 0.25:
                conflicts.append(
                    {
                        "type": "summary_difference",
                        "message": "多条内容的摘要差异较大，已在合并结果中同时保留。",
                    }
                )
        return conflicts
