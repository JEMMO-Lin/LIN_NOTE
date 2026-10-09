"""总结模板管理路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.summary_template import (
    SummaryTemplateCreate,
    SummaryTemplateOut,
    SummaryTemplateUpdate,
)
from app.services.template_service import TemplateService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SummaryTemplateOut])
async def list_templates(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    items = await TemplateService(db).list_templates(user_id)
    return PaginatedResponse(
        data=[SummaryTemplateOut.model_validate(item) for item in items],
        total=len(items),
    )


@router.post("", response_model=DataResponse[SummaryTemplateOut])
async def create_template(
    payload: SummaryTemplateCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await TemplateService(db).create_template(user_id, payload)
    return DataResponse(data=SummaryTemplateOut.model_validate(item))


@router.get("/{template_id}", response_model=DataResponse[SummaryTemplateOut])
async def get_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await TemplateService(db).get_template(user_id, template_id)
    return DataResponse(data=SummaryTemplateOut.model_validate(item))


@router.patch("/{template_id}", response_model=DataResponse[SummaryTemplateOut])
async def update_template(
    template_id: str,
    payload: SummaryTemplateUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await TemplateService(db).update_template(user_id, template_id, payload)
    return DataResponse(data=SummaryTemplateOut.model_validate(item))


@router.delete("/{template_id}", response_model=DataResponse)
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await TemplateService(db).delete_template(user_id, template_id)
    return DataResponse(message="模板已删除")
