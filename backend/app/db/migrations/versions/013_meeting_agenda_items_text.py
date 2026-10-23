"""Add agenda_items_text column to meetings table.

Revision ID: 013_meeting_agenda_items_text
Revises: 012_action_status_values
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_meeting_agenda_items_text"
down_revision: Union[str, None] = "012_action_status_values"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("agenda_items_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_column("agenda_items_text")
