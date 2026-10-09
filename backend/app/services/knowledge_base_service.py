"""知识库服务

对应架构文档 3.1 节。
职责：知识库的创建、管理、权限控制。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import (
    KBStats,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
)


class KnowledgeBaseService:
    """知识库应用服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_kb(self, user_id: str, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        """创建知识库"""
        kb = KnowledgeBase(user_id=user_id, **payload.model_dump())
        self.db.add(kb)
        await self.db.flush()
        return kb

    async def get_kb(self, user_id: str, kb_id: str) -> KnowledgeBase:
        """获取知识库（含权限校验）"""
        kb = await self.db.get(KnowledgeBase, kb_id)
        if kb is None:
            raise NotFoundError("知识库不存在")
        if str(kb.user_id) != user_id:
            raise PermissionError("无权访问该知识库")
        return kb

    async def list_kbs(self, user_id: str) -> list[KnowledgeBase]:
        """列出用户的知识库"""
        result = await self.db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_kb(
        self, user_id: str, kb_id: str, payload: KnowledgeBaseUpdate
    ) -> KnowledgeBase:
        """更新知识库"""
        kb = await self.get_kb(user_id, kb_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(kb, field, value)
        await self.db.flush()
        await self.db.refresh(kb)
        return kb

    async def delete_kb(self, user_id: str, kb_id: str) -> None:
        """删除知识库（级联删除内容与知识点）"""
        kb = await self.get_kb(user_id, kb_id)
        await self.db.delete(kb)
        await self.db.flush()

    async def get_kb_stats(self, user_id: str, kb_id: str) -> KBStats:
        """获取知识库统计信息"""
        from sqlalchemy import func

        from app.models.content_item import ContentItem
        from app.models.knowledge_point import KnowledgePoint

        await self.get_kb(user_id, kb_id)

        content_count = await self.db.scalar(
            select(func.count(ContentItem.id)).where(
                ContentItem.kb_id == kb_id,
                ContentItem.merge_status == "active",
            )
        )
        kp_count = await self.db.scalar(
            select(func.count(KnowledgePoint.id))
            .join(ContentItem, KnowledgePoint.content_id == ContentItem.id)
            .where(
                KnowledgePoint.kb_id == kb_id,
                ContentItem.merge_status == "active",
            )
        )
        last_updated = await self.db.scalar(
            select(func.max(ContentItem.updated_at)).where(ContentItem.kb_id == kb_id)
        )
        return KBStats(
            kb_id=kb_id,
            content_count=content_count or 0,
            knowledge_point_count=kp_count or 0,
            last_updated=last_updated,
        )
