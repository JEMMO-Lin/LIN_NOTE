"""内容项模型

对应架构文档 5.3 节 content_items 表。
存储从 URL / 文本 / 图片接入并解析后的原始内容与 AI 摘要。
"""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, JSONB, TimestampMixin, UUIDPrimaryKey


class ContentItem(Base, UUIDPrimaryKey, TimestampMixin):
    """内容项表"""

    __tablename__ = "content_items"

    kb_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("knowledge_bases.id"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # url|text|image
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Canonical knowledge text after semantic filtering.  Original text stays
    # untouched for traceability; retrieval and chunking use this field.
    distilled_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_knowledge: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB(), server_default="{}", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default="processed", nullable=False
    )  # pending|processed|failed|cancelled
    merge_status: Mapped[str] = mapped_column(
        String(20), server_default="active", nullable=False
    )  # active|merged|archived
    merged_into_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("content_items.id"), nullable=True
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="content_items")
    knowledge_points = relationship(
        "KnowledgePoint", back_populates="content_item", cascade="all, delete-orphan"
    )
