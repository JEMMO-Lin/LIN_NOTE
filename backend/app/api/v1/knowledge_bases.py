"""知识库管理、统计与导出路由。"""
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.knowledge_base import (
    KBStats,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.models.content_item import ContentItem
from app.models.knowledge_point import KnowledgePoint

router = APIRouter()


@router.post("", response_model=DataResponse[KnowledgeBaseOut])
async def create_kb(
    payload: KnowledgeBaseCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库"""
    service = KnowledgeBaseService(db)
    kb = await service.create_kb(user_id, payload)
    return DataResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.get("", response_model=PaginatedResponse[KnowledgeBaseOut])
async def list_kbs(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的知识库"""
    service = KnowledgeBaseService(db)
    kbs = await service.list_kbs(user_id)
    return PaginatedResponse(
        data=[KnowledgeBaseOut.model_validate(kb) for kb in kbs],
        total=len(kbs),
    )


@router.get("/{kb_id}", response_model=DataResponse[KnowledgeBaseOut])
async def get_kb(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库详情"""
    service = KnowledgeBaseService(db)
    kb = await service.get_kb(user_id, kb_id)
    return DataResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.patch("/{kb_id}", response_model=DataResponse[KnowledgeBaseOut])
async def update_kb(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库"""
    service = KnowledgeBaseService(db)
    kb = await service.update_kb(user_id, kb_id, payload)
    return DataResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.delete("/{kb_id}", response_model=DataResponse)
async def delete_kb(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库"""
    service = KnowledgeBaseService(db)
    await service.delete_kb(user_id, kb_id)
    return DataResponse(message="已删除")


@router.get("/{kb_id}/stats", response_model=DataResponse[KBStats])
async def get_kb_stats(
    kb_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库统计"""
    service = KnowledgeBaseService(db)
    stats = await service.get_kb_stats(user_id, kb_id)
    return DataResponse(data=stats)


@router.get("/{kb_id}/export")
async def export_kb(
    kb_id: str,
    format: str = "markdown",
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = KnowledgeBaseService(db)
    kb = await service.get_kb(user_id, kb_id)
    content_result = await db.execute(
        select(ContentItem)
        .where(ContentItem.kb_id == kb.id, ContentItem.merge_status == "active")
        .order_by(ContentItem.created_at.desc())
    )
    contents = list(content_result.scalars().all())
    point_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.kb_id == kb.id)
    )
    points = list(point_result.scalars().all())
    points_by_content: dict[str, list[KnowledgePoint]] = {}
    for point in points:
        points_by_content.setdefault(str(point.content_id), []).append(point)

    filename = quote(kb.name)
    if format == "json":
        payload = {
            "knowledge_base": {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description,
                "category": kb.category,
                "tags": kb.tags,
                "settings": kb.settings,
            },
            "contents": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "source_type": item.source_type,
                    "source_url": item.source_url,
                    "summary": item.summary,
                    "original_text": item.original_text,
                    "knowledge_points": [
                        {
                            "id": str(point.id),
                            "title": point.title,
                            "content": point.content,
                            "category": point.category,
                            "importance": point.importance,
                        }
                        for point in points_by_content.get(str(item.id), [])
                    ],
                    "created_at": item.created_at.isoformat(),
                }
                for item in contents
            ],
        }
        return Response(
            json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}.json"},
        )

    lines = [f"# {kb.name}", "", kb.description or "", ""]
    if kb.tags:
        lines.extend([f"标签：{'、'.join(kb.tags)}", ""])
    for item in contents:
        lines.extend([f"## {item.title}", ""])
        if item.source_url:
            lines.extend([f"来源：{item.source_url}", ""])
        if item.summary:
            lines.extend(["### 摘要", "", item.summary, ""])
        item_points = points_by_content.get(str(item.id), [])
        if item_points:
            lines.extend(["### 知识点", ""])
            for point in item_points:
                lines.extend([f"- **{point.title}**：{point.content}"])
            lines.append("")
        lines.extend(["### 原始内容", "", item.original_text, "", "---", ""])
    return Response(
        "\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}.md"},
    )
