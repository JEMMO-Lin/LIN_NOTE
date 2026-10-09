"""检索服务

对应架构文档 6 节。
应用层薄封装，将检索委托给 ISearchService 实现（HybridSearchService）。
"""
from typing import Optional

from app.services.interfaces.search_service import ISearchService, SearchHit


class SearchService:
    """检索应用服务"""

    def __init__(self, search_engine: ISearchService):
        self.engine = search_engine

    async def search(
        self,
        query: str,
        kb_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[SearchHit]:
        """混合检索：向量 + 关键词融合排序"""
        return await self.engine.search(query, kb_id, mode, top_k)

    async def search_documents(
        self,
        query: str,
        kb_id: Optional[str] = None,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[SearchHit]:
        """检索原始内容；旧检索实现可降级到知识点检索。"""
        search_documents = getattr(self.engine, "search_documents", None)
        if search_documents is None:
            return await self.search(query, kb_id, mode, top_k)
        return await search_documents(query, kb_id, mode, top_k)
