"""Initial schema: users, items, tags, item_tags; enable pgvector.

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Installed now, used for semantic search in v2.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("content_type", sa.String(16)),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "content_type IN ('article', 'video', 'repo', 'tool', 'other')", name="content_type"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')", name="item_status"
        ),
    )
    op.create_index("ix_items_user_id", "items", ["user_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_tags_user_id_name"),
        sa.CheckConstraint(
            "name = lower(btrim(name)) AND name <> ''", name="ck_tags_name_normalized"
        ),
    )

    op.create_table(
        "item_tags",
        sa.Column(
            "item_id", sa.Uuid(), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "tag_id", sa.Uuid(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("source", sa.String(16), nullable=False),
        sa.CheckConstraint("source IN ('ai', 'user')", name="tag_source"),
    )
    op.create_index("ix_item_tags_tag_id", "item_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_table("item_tags")
    op.drop_table("tags")
    op.drop_table("items")
    op.drop_table("users")
