"""add canonical distilled content

Revision ID: f72c8e4a1d39
Revises: e591b118a2f4
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f72c8e4a1d39"
down_revision: Union[str, None] = "e591b118a2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.add_column(sa.Column("distilled_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_column("distilled_text")
