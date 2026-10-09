"""混合检索服务

对应架构文档 6.3 节 HybridSearchService。
融合向量检索与关键词检索，按权重排序，兼顾语义精度与关键词召回。
"""
import logging
import math
from collections import Counter
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.content_item import ContentItem
from app.services.interfaces.llm_router import ILLMRouter
from app.services.interfaces.search_service import ISearchService, SearchHit
from app.infrastructure.vector_store.chroma_store import (
    ChromaVectorStore,
    CONTENT_COLLECTION,
    KNOWLEDGE_POINT_COLLECTION,
    get_vector_store,
)

logger = logging.getLogger(__name__)


class HybridSearchService(ISearchService):
    """混合检索服务"""

    VECTOR_WEIGHT = 0.7
    KEYWORD_WEIGHT = 0.3

    def __init__(
        self,
        llm_router: ILLMRouter,
        db: AsyncSession,
        vector_store: Optional[ChromaVectorStore] = None,
    ):
        self.llm = llm_router
        self.db = db
        self.vector_store = vector_store or get_vector_store()

    async def search(
        self,
        query: str,
        kb_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[SearchHit]:
        """检索

        mode:
        - vector: 纯向量检索
        - keyword: 纯关键词检索
        - hybrid: 混合检索（推荐）
        """
        if mode == "vector":
            return await self._vector_search(query, kb_id, top_k)
        elif mode == "keyword":
            return await self._keyword_search(query, kb_id, top_k)
        else:
            vector_results = await self._vector_search(query, kb_id, top_k)
            keyword_results = await self._keyword_search(query, kb_id, top_k)
            return self._fusion_rank(vector_results, keyword_results, top_k)

    async def search_documents(
        self,
        query: str,
        kb_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[SearchHit]:
        """RAG retrieval over canonical distilled documents."""
        if mode == "vector":
            return await self._document_vector_search(query, kb_id, top_k)
        if mode == "keyword":
            return await self._document_keyword_search(query, kb_id, top_k)
        vector_results = await self._document_vector_search(query, kb_id, top_k)
        keyword_results = await self._document_keyword_search(query, kb_id, top_k)
        return self._fusion_rank(vector_results, keyword_results, top_k)

    async def _document_vector_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        try:
            embedding = await self.llm.embed(query)
            hits = await self.vector_store.query(
                CONTENT_COLLECTION,
                query_embedding=embedding,
                kb_id=kb_id,
                top_k=top_k,
            )
            scores = {str(hit["id"]): hit["score"] for hit in hits}
            ids = list(scores)
            stmt = select(ContentItem).where(
                ContentItem.id.in_(ids), ContentItem.merge_status == "active"
            )
            if kb_id:
                stmt = stmt.where(ContentItem.kb_id == kb_id)
            result = await self.db.execute(stmt)
            formatted = []
            for item in result.scalars().all():
                knowledge_text = self._knowledge_text(item)
                if not knowledge_text:
                    continue
                formatted.append(
                    SearchHit(
                        point_id=str(item.id),
                        title=item.title,
                        content=knowledge_text,
                        score=scores.get(str(item.id), 0.0),
                        content_id=str(item.id),
                        kb_id=str(item.kb_id),
                    )
                )
            formatted.sort(key=lambda hit: hit.score, reverse=True)
            return formatted or await self._local_document_search(query, kb_id, top_k)
        except Exception as exc:
            logger.warning("原始文档向量检索失败，使用本地语义降级: %s", exc)
            return await self._local_document_search(query, kb_id, top_k)

    async def _document_keyword_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        conditions = [
            ContentItem.title.ilike(f"%{query}%"),
            ContentItem.distilled_text.ilike(f"%{query}%"),
        ]
        stmt = (
            select(ContentItem)
            .where(ContentItem.merge_status == "active")
            .where(or_(*conditions))
        )
        if kb_id:
            stmt = stmt.where(ContentItem.kb_id == kb_id)
        result = await self.db.execute(stmt.limit(top_k))
        items = list(result.scalars().all())
        hits = []
        for item in items:
            item_text = self._knowledge_text(item)
            if not item_text:
                continue
            hits.append(
                SearchHit(
                    point_id=str(item.id),
                    title=item.title,
                    content=item_text,
                    score=0.9 if query.casefold() in item.title.casefold() else 0.6,
                    content_id=str(item.id),
                    kb_id=str(item.kb_id),
                )
            )
        return hits

    async def _local_document_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        stmt = select(ContentItem).where(ContentItem.merge_status == "active")
        if kb_id:
            stmt = stmt.where(ContentItem.kb_id == kb_id)
        result = await self.db.execute(stmt.limit(1000))
        query_vector = self._ngrams(query)
        hits = []
        for item in result.scalars().all():
            knowledge_text = self._knowledge_text(item)
            if not knowledge_text:
                continue
            score = self._cosine(
                query_vector, self._ngrams(f"{item.title} {knowledge_text}")
            )
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    point_id=str(item.id),
                    title=item.title,
                    content=knowledge_text,
                    score=score,
                    content_id=str(item.id),
                    kb_id=str(item.kb_id),
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    @staticmethod
    def _knowledge_text(item: ContentItem) -> str:
        # NULL means legacy/unprocessed data and must not fall back to raw text.
        # An empty value explicitly means the source had no knowledge to index.
        if item.distilled_text is not None:
            return item.distilled_text.strip()
        return ""

    async def _vector_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        """向量检索：Embedding + HNSW 近邻"""
        try:
            embedding = await self.llm.embed(query)
            hits = await self.vector_store.query(
                KNOWLEDGE_POINT_COLLECTION,
                query_embedding=embedding,
                kb_id=kb_id,
                top_k=top_k,
            )
            scores = {str(hit["id"]): hit["score"] for hit in hits}
            result = await self.db.execute(
                select(KnowledgePoint)
                .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
                .where(
                    KnowledgePoint.id.in_(list(scores)),
                    ContentItem.merge_status == "active",
                    ContentItem.distilled_text.is_not(None),
                )
            )
            formatted = [
                SearchHit(
                    point_id=str(point.id),
                    title=point.title,
                    content=point.content,
                    score=scores.get(str(point.id), 0.0),
                    content_id=str(point.content_id),
                    kb_id=str(point.kb_id),
                )
                for point in result.scalars().all()
            ]
            formatted.sort(key=lambda hit: hit.score, reverse=True)
            return formatted or await self._local_semantic_search(query, kb_id, top_k)
        except Exception as e:
            logger.warning("向量检索失败，使用本地语义降级: %s", e)
            return await self._local_semantic_search(query, kb_id, top_k)

    async def _keyword_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        """关键词检索：SQLite FTS5 / PostgreSQL GIN 通用实现

        使用 SQLAlchemy 的 LIKE 作为基础实现，兼容所有数据库。
        后续可升级为 SQLite FTS5 或 PostgreSQL GIN。
        """
        try:
            # 构建查询条件
            conditions = [
                KnowledgePoint.title.ilike(f"%{query}%"),
                KnowledgePoint.content.ilike(f"%{query}%"),
            ]
            if kb_id:
                stmt = (
                    select(KnowledgePoint)
                    .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
                    .where(KnowledgePoint.kb_id == kb_id)
                    .where(ContentItem.merge_status == "active")
                    .where(ContentItem.distilled_text.is_not(None))
                    .where(or_(*conditions))
                    .limit(top_k)
                )
            else:
                stmt = (
                    select(KnowledgePoint)
                    .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
                    .where(ContentItem.merge_status == "active")
                    .where(ContentItem.distilled_text.is_not(None))
                    .where(or_(*conditions))
                    .limit(top_k)
                )

            result = await self.db.execute(stmt)
            points = list(result.scalars().all())

            hits = []
            for point in points:
                # 计算简单相关性分数：标题命中更高权重
                score = 0.5
                if query.lower() in point.title.lower():
                    score = 0.9
                elif query.lower() in point.content.lower():
                    score = 0.6

                hits.append(
                    SearchHit(
                        point_id=str(point.id),
                        title=point.title,
                        content=point.content,
                        score=score,
                        content_id=str(point.content_id),
                        kb_id=str(point.kb_id),
                    )
                )
            return hits
        except Exception as e:
            logger.warning("关键词检索失败，返回空结果: %s", e)
            return []

    def _fusion_rank(
        self,
        vector_results: list[SearchHit],
        keyword_results: list[SearchHit],
        top_k: int,
    ) -> list[SearchHit]:
        """加权融合排序"""
        scores: dict[str, float] = {}
        merged: dict[str, SearchHit] = {}

        for hit in vector_results:
            scores[hit.point_id] = scores.get(hit.point_id, 0.0) + hit.score * self.VECTOR_WEIGHT
            merged[hit.point_id] = hit

        for hit in keyword_results:
            scores[hit.point_id] = scores.get(hit.point_id, 0.0) + hit.score * self.KEYWORD_WEIGHT
            if hit.point_id not in merged:
                merged[hit.point_id] = hit

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        result = []
        for point_id, score in ranked:
            hit = merged[point_id]
            result.append(
                SearchHit(
                    point_id=hit.point_id,
                    title=hit.title,
                    content=hit.content,
                    score=score,
                    content_id=hit.content_id,
                    kb_id=hit.kb_id,
                )
            )
        return result

    async def _local_semantic_search(
        self, query: str, kb_id: Optional[str], top_k: int
    ) -> list[SearchHit]:
        """无 Embedding/ChromaDB 时用字符 n-gram 余弦相似度本地降级。"""
        stmt = (
            select(KnowledgePoint)
            .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
            .where(ContentItem.merge_status == "active")
            .where(ContentItem.distilled_text.is_not(None))
        )
        if kb_id:
            stmt = stmt.where(KnowledgePoint.kb_id == kb_id)
        result = await self.db.execute(stmt.limit(1000))
        points = list(result.scalars().all())
        query_vector = self._ngrams(query)
        hits = []
        for point in points:
            score = self._cosine(
                query_vector, self._ngrams(f"{point.title} {point.content}")
            )
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    point_id=str(point.id),
                    title=point.title,
                    content=point.content,
                    score=score,
                    content_id=str(point.content_id),
                    kb_id=str(point.kb_id),
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    @staticmethod
    def _ngrams(text: str) -> Counter:
        normalized = "".join(text.lower().split())
        if len(normalized) < 2:
            return Counter(normalized)
        return Counter(normalized[index : index + 2] for index in range(len(normalized) - 1))

    @staticmethod
    def _cosine(left: Counter, right: Counter) -> float:
        if not left or not right:
            return 0.0
        dot = sum(value * right.get(key, 0) for key, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
