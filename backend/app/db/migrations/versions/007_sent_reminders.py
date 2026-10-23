"""Create reminder delivery records.

Revision ID: 007_sent_reminders
Revises: 006_minutes_action_items
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_sent_reminders"
down_revision: Union[str, None] = "006_minutes_action_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sent_reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("action_item_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("sent_to_email", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["action_item_id"], ["action_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("sent_reminders")