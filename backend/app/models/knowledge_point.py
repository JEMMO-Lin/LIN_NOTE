"""知识点模型

对应架构文档 5.3 节 knowledge_points 表。
知识点从内容项中由 AI 提取，可彼此关联，构成知识体系的基本单元。
"""
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, StringArray, TimestampMixin, UUIDPrimaryKey


class KnowledgePoint(Base, UUIDPrimaryKey, TimestampMixin):
    """知识点表"""

    __tablename__ = "knowledge_points"

    content_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("content_items.id"),
        nullable=False,
        index=True,
    )
    kb_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("knowledge_bases.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(
        Float, server_default="0.5", nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_points: Mapped[list[str]] = mapped_column(
        StringArray(), server_default="{}", nullable=False
    )

    content_item = relationship("ContentItem", back_populates="knowledge_points")
