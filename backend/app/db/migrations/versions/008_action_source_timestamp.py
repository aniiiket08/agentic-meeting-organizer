"""Store source timestamps on tracked actions.

Revision ID: 008_action_source_timestamp
Revises: 007_sent_reminders
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_action_source_timestamp"
down_revision: Union[str, None] = "007_sent_reminders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.add_column(sa.Column("source_timestamp", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.drop_column("source_timestamp")