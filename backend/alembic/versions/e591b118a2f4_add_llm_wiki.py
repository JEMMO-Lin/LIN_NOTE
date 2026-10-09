"""add self-growing LLM Wiki

Revision ID: e591b118a2f4
Revises: d43a6b915a20
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.base import GUID, JSONB


revision: str = "e591b118a2f4"
down_revision: Union[str, None] = "d43a6b915a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wiki_entries",
        sa.Column("user_id", GUID(length=36), nullable=False),
        sa.Column("kb_id", GUID(length=36), nullable=True),
        sa.Column("scope_key", sa.String(length=36), nullable=False),
        sa.Column("question", sa.String(length=1000), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("sources", JSONB(), server_default="[]", nullable=False),
        sa.Column("ask_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "scope_key", "question_hash", name="uq_wiki_entry_question"
        ),
    )
    op.create_index("ix_wiki_entries_user_id", "wiki_entries", ["user_id"])
    op.create_index("ix_wiki_entries_kb_id", "wiki_entries", ["kb_id"])
    op.create_index("ix_wiki_entries_is_published", "wiki_entries", ["is_published"])


def downgrade() -> None:
    op.drop_index("ix_wiki_entries_is_published", table_name="wiki_entries")
    op.drop_index("ix_wiki_entries_kb_id", table_name="wiki_entries")
    op.drop_index("ix_wiki_entries_user_id", table_name="wiki_entries")
    op.drop_table("wiki_entries")
