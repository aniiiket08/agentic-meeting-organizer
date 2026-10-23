"""Persist extracted action items with draft minutes.

Revision ID: 006_minutes_action_items
Revises: 005_username
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_minutes_action_items"
down_revision: Union[str, None] = "005_username"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("minutes") as batch_op:
        batch_op.add_column(
            sa.Column("action_items_json", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("minutes") as batch_op:
        batch_op.drop_column("action_items_json")