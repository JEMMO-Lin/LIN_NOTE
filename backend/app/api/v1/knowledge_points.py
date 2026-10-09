"""知识点、知识树与知识问答路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.infrastructure.llm.prompt_manager import get_prompt_manager
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.vector_store.hybrid_search import HybridSearchService
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.knowledge_point import (
    AskRequest,
    AskResponse,
    KnowledgePointOut,
    KnowledgePointUpdate,
    KnowledgeTreeOut,
    SearchResult,
)
from app.services.ai_service import AIService
from app.services.knowledge_service import KnowledgeService
from app.services.search_service import SearchService

router = APIRouter()


def _service(db: AsyncSession, with_ai: bool = False) -> KnowledgeService:
    if not with_ai:
        return KnowledgeService(db)
    llm = get_llm_router()
    return KnowledgeService(
        db,
        ai_service=AIService(llm_router=llm, prompt_manager=get_prompt_manager()),
        search_service=SearchService(HybridSearchService(llm_router=llm, db=db)),
    )


@router.get("", response_model=PaginatedResponse[KnowledgePointOut])
async def list_points(
    kb_id: str,
    content_id: str | None = None,
    category: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await _service(db).list_points(user_id, kb_id, content_id, category)
    return PaginatedResponse(
        data=[KnowledgePointOut.model_validate(item) for item in items],
        total=len(items),
        page_size=max(len(items), 1),
    )


@router.post("/ask", response_model=DataResponse[AskResponse])
async def ask_knowledge(
    payload: AskRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await _service(db, with_ai=True).answer_with_meta(
        user_id, payload.question, payload.kb_id, payload.top_k
    )
    sources = [
        SearchResult(
            point_id=hit.point_id,
            title=hit.title,
            content=hit.content,
            score=hit.score,
            content_id=hit.content_id,
            kb_id=hit.kb_id,
        )
        for hit in result.hits
    ]
    return DataResponse(
        data=AskResponse(
            answer=result.answer,
            sources=sources,
            answer_source=result.answer_source,
            wiki_hit=result.wiki_hit,
            ask_count=result.ask_count,
            wiki_entry_id=result.wiki_entry_id,
            wiki_created=result.wiki_created,
        )
    )


@router.get("/tree/{kb_id}", response_model=DataResponse[KnowledgeTreeOut])
async def get_knowledge_tree(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    tree = await _service(db).build_tree(user_id, kb_id)
    return DataResponse(data=KnowledgeTreeOut(**tree))


@router.get("/{point_id}", response_model=DataResponse[KnowledgePointOut])
async def get_point(
    point_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    point = await _service(db).get_point(user_id, point_id)
    return DataResponse(data=KnowledgePointOut.model_validate(point))


@router.patch("/{point_id}", response_model=DataResponse[KnowledgePointOut])
async def update_point(
    point_id: str,
    payload: KnowledgePointUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    point = await _service(db).update_point(user_id, point_id, payload)
    return DataResponse(data=KnowledgePointOut.model_validate(point))


@router.delete("/{point_id}", response_model=DataResponse)
async def delete_point(
    point_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _service(db).delete_point(user_id, point_id)
    return DataResponse(message="知识点已删除")
