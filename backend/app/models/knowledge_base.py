"""知识库模型

对应架构文档 5.3 节 knowledge_bases 表。
使用跨库兼容类型，SQLite 与 PostgreSQL 均可运行。
"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, JSONB, StringArray, TimestampMixin, UUIDPrimaryKey


class KnowledgeBase(Base, UUIDPrimaryKey, TimestampMixin):
    """知识库表"""

    __tablename__ = "knowledge_bases"

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        StringArray(), server_default="{}", nullable=False
    )
    settings: Mapped[dict] = mapped_column(
        JSONB(), server_default="{}", nullable=False
    )

    user = relationship("User", back_populates="knowledge_bases")
    # 关联：知识库下的内容项
    content_items = relationship(
        "ContentItem", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    merge_histories = relationship(
        "MergeHistory", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    wiki_entries = relationship(
        "WikiEntry", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
