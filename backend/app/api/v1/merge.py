"""内容相似检测与合并路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.infrastructure.llm.prompt_manager import get_prompt_manager
from app.infrastructure.llm.router import get_llm_router
from app.infrastructure.vector_store.hybrid_search import HybridSearchService
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.content_item import ContentOut, MergeRequest, SimilarContentOut
from app.schemas.merge import MergeHistoryOut, MergePreviewOut
from app.services.ai_service import AIService
from app.services.merge_service import MergeService

router = APIRouter()


def _service(db: AsyncSession) -> MergeService:
    llm = get_llm_router()
    return MergeService(
        db=db,
        search_engine=HybridSearchService(llm_router=llm, db=db),
        ai_service=AIService(llm_router=llm, prompt_manager=get_prompt_manager()),
    )


@router.get("/{content_id}/similar", response_model=DataResponse[list[SimilarContentOut]])
async def find_similar(
    content_id: str,
    threshold: float = Query(0.75, ge=0, le=1),
    top_k: int = Query(8, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await _service(db).find_duplicates_for_content(
        user_id, content_id, threshold, top_k
    )
    return DataResponse(data=[SimilarContentOut(**item) for item in items])


@router.post("/preview", response_model=DataResponse[MergePreviewOut])
async def preview_merge(
    payload: MergeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    preview = await _service(db).preview(user_id, payload.target_id, payload.source_ids)
    return DataResponse(data=MergePreviewOut(**preview))


@router.post("", response_model=DataResponse[ContentOut])
async def merge_contents(
    payload: MergeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item, _ = await _service(db).merge_into(
        user_id, payload.target_id, payload.source_ids
    )
    return DataResponse(data=ContentOut.model_validate(item), message="内容已合并")


@router.get("/history/list", response_model=PaginatedResponse[MergeHistoryOut])
async def list_merge_history(
    kb_id: str | None = None,
    content_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await _service(db).list_history(user_id, kb_id, content_id)
    return PaginatedResponse(
        data=[MergeHistoryOut.model_validate(item) for item in items],
        total=len(items),
    )
