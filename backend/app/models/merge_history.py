"""内容合并历史模型。"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    GUID,
    JSONB,
    StringArray,
    TimestampMixin,
    UUIDPrimaryKey,
)


class MergeHistory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "merge_histories"

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False, index=True
    )
    kb_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("content_items.id"), nullable=False
    )
    source_ids: Mapped[list[str]] = mapped_column(
        StringArray(), server_default="{}", nullable=False
    )
    source_titles: Mapped[list[str]] = mapped_column(
        StringArray(), server_default="{}", nullable=False
    )
    merged_result_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("content_items.id"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(
        String(30), server_default="ai_deduplicate", nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicts: Mapped[list[dict]] = mapped_column(
        JSONB(), server_default="[]", nullable=False
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="merge_histories")
