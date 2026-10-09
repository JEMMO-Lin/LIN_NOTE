"""知识库仓储"""
from typing import Optional

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """知识库仓储"""

    model = KnowledgeBase

    async def list_by_user(self, user_id: str) -> list[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())
