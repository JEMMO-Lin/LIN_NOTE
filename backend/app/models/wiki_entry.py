"""LLM Wiki entry and question-frequency model."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, JSONB, TimestampMixin, UUIDPrimaryKey


class WikiEntry(Base, UUIDPrimaryKey, TimestampMixin):
    """A learned answer scoped to one user and one knowledge base.

    Rows are created on the first question so ``ask_count`` can be tracked.  They
    only become Wiki hits after ``is_published`` is set at the configured
    threshold.
    """

    __tablename__ = "wiki_entries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope_key", "question_hash", name="uq_wiki_entry_question"
        ),
    )

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kb_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # A non-null scope is used in the unique key because NULL uniqueness differs
    # between SQLite and PostgreSQL. "__all__" represents cross-library Q&A.
    scope_key: Mapped[str] = mapped_column(String(36), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list[dict]] = mapped_column(
        JSONB(), server_default="[]", nullable=False
    )
    ask_count: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User", back_populates="wiki_entries")
    knowledge_base = relationship("KnowledgeBase", back_populates="wiki_entries")
