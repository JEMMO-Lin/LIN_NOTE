"""complete MVP and phase-2 domain models

Revision ID: d43a6b915a20
Revises: c2aa8cf7199a
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.base import GUID, JSONB, StringArray

revision: str = "d43a6b915a20"
down_revision: Union[str, None] = "c2aa8cf7199a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("settings", JSONB(), server_default="{}", nullable=False)
        )

    with op.batch_alter_table("content_items") as batch_op:
        batch_op.add_column(
            sa.Column("metadata", JSONB(), server_default="{}", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "merge_status", sa.String(length=20), server_default="active", nullable=False
            )
        )
        batch_op.add_column(sa.Column("merged_into_id", GUID(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_content_items_merged_into_id",
            "content_items",
            ["merged_into_id"],
            ["id"],
        )

    op.create_table(
        "summary_templates",
        sa.Column("user_id", GUID(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fields", JSONB(), server_default="[]", nullable=False),
        sa.Column(
            "default_style", sa.String(length=20), server_default="medium", nullable=False
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_summary_templates_user_id", "summary_templates", ["user_id"], unique=False
    )

    op.create_table(
        "merge_histories",
        sa.Column("user_id", GUID(length=36), nullable=False),
        sa.Column("kb_id", GUID(length=36), nullable=False),
        sa.Column("target_id", GUID(length=36), nullable=False),
        sa.Column("source_ids", StringArray(), server_default="{}", nullable=False),
        sa.Column("source_titles", StringArray(), server_default="{}", nullable=False),
        sa.Column("merged_result_id", GUID(length=36), nullable=False),
        sa.Column(
            "strategy",
            sa.String(length=30),
            server_default="ai_deduplicate",
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("conflicts", JSONB(), server_default="[]", nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["merged_result_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merge_histories_user_id", "merge_histories", ["user_id"])
    op.create_index("ix_merge_histories_kb_id", "merge_histories", ["kb_id"])


def downgrade() -> None:
    op.drop_index("ix_merge_histories_kb_id", table_name="merge_histories")
    op.drop_index("ix_merge_histories_user_id", table_name="merge_histories")
    op.drop_table("merge_histories")
    op.drop_index("ix_summary_templates_user_id", table_name="summary_templates")
    op.drop_table("summary_templates")
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_constraint("fk_content_items_merged_into_id", type_="foreignkey")
        batch_op.drop_column("merged_into_id")
        batch_op.drop_column("merge_status")
        batch_op.drop_column("metadata")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("settings")
