"""内容项仓储"""
from typing import Optional

from sqlalchemy import func, select

from app.infrastructure.repositories.base import BaseRepository
from app.models.content_item import ContentItem


class ContentRepository(BaseRepository[ContentItem]):
    """内容项仓储"""

    model = ContentItem

    async def list_by_kb(
        self,
        kb_id: str,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ContentItem], int]:
        """分页查询知识库下的内容"""
        stmt = select(ContentItem).where(ContentItem.kb_id == kb_id)
        if status:
            stmt = stmt.where(ContentItem.status == status)

        total = await self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.db.execute(
            stmt.order_by(ContentItem.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total or 0
