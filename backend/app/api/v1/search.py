"""检索路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.models.knowledge_base import KnowledgeBase
from sqlalchemy import select
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.vector_store.hybrid_search import HybridSearchService
from app.schemas.common import DataResponse
from app.schemas.knowledge_point import SearchQuery, SearchResult
from app.services.interfaces.llm_router import ILLMRouter
from app.services.search_service import SearchService

router = APIRouter()


def _get_search_service(db: AsyncSession, llm_router: ILLMRouter) -> SearchService:
    """装配检索依赖链：LLM 路由 → 混合检索引擎 → 检索服务"""
    engine = HybridSearchService(llm_router=llm_router, db=db)
    return SearchService(search_engine=engine)


@router.post("", response_model=DataResponse[list[SearchResult]])
async def search(
    payload: SearchQuery,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    llm_router: ILLMRouter = Depends(get_llm_router),
):
    """混合检索：向量 + 关键词融合"""
    service = _get_search_service(db, llm_router)
    if payload.kb_id:
        kb = await db.get(KnowledgeBase, payload.kb_id)
        if kb is None or str(kb.user_id) != user_id:
            from app.core.exceptions import PermissionError
            raise PermissionError("无权搜索该知识库")
    hits = await service.search(
        query=payload.query,
        kb_id=payload.kb_id,
        mode=payload.mode,
        top_k=payload.top_k,
    )
    if payload.kb_id is None:
        result = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.user_id == user_id)
        )
        allowed = {str(value) for value in result.scalars().all()}
        hits = [hit for hit in hits if hit.kb_id in allowed]
    return DataResponse(
        data=[
            SearchResult(
                point_id=h.point_id,
                title=h.title,
                content=h.content,
                score=h.score,
                content_id=h.content_id,
                kb_id=h.kb_id,
            )
            for h in hits
        ]
    )
