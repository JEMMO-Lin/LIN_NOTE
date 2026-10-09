"""LLM Wiki management endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.wiki import WikiEntryOut, WikiEntryUpdate
from app.services.wiki_service import WikiService


router = APIRouter()


@router.get("", response_model=PaginatedResponse[WikiEntryOut])
async def list_wiki_entries(
    kb_id: str | None = None,
    published_only: bool = True,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    entries = await WikiService(db).list_entries(user_id, kb_id, published_only)
    return PaginatedResponse(
        data=[WikiEntryOut.model_validate(entry) for entry in entries],
        total=len(entries),
        page_size=max(len(entries), 1),
    )


@router.get("/{entry_id}", response_model=DataResponse[WikiEntryOut])
async def get_wiki_entry(
    entry_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    entry = await WikiService(db).get_entry(user_id, entry_id)
    return DataResponse(data=WikiEntryOut.model_validate(entry))


@router.patch("/{entry_id}", response_model=DataResponse[WikiEntryOut])
async def update_wiki_entry(
    entry_id: str,
    payload: WikiEntryUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    entry = await WikiService(db).update_entry(user_id, entry_id, payload)
    return DataResponse(data=WikiEntryOut.model_validate(entry))


@router.delete("/{entry_id}", response_model=DataResponse)
async def delete_wiki_entry(
    entry_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await WikiService(db).delete_entry(user_id, entry_id)
    return DataResponse(message="Wiki 条目已删除")
