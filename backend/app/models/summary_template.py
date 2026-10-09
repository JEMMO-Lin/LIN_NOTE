"""用户自定义总结模板模型。"""
from sqlalchemy import Boolean, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, JSONB, TimestampMixin, UUIDPrimaryKey


class SummaryTemplate(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "summary_templates"

    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields: Mapped[list[dict]] = mapped_column(
        JSONB(), server_default="[]", nullable=False
    )
    default_style: Mapped[str] = mapped_column(
        String(20), server_default="medium", nullable=False
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False
    )

    user = relationship("User", back_populates="summary_templates")
