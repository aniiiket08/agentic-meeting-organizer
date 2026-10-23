"""Use the requested action status values.

Revision ID: 012_action_status_values
Revises: 011_action_owner_details
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op


revision: str = "012_action_status_values"
down_revision: Union[str, None] = "011_action_owner_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("UPDATE action_items SET status = 'pending' WHERE status IN ('open', 'blocked')")
    op.execute("UPDATE action_items SET status = 'completed' WHERE status = 'done'")


def downgrade() -> None:
    op.execute("UPDATE action_items SET status = 'open' WHERE status = 'pending'")
    op.execute("UPDATE action_items SET status = 'done' WHERE status = 'completed'")