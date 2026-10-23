"""Flag action items that need a human to confirm missing owners.

Revision ID: 009_action_needs_confirmation
Revises: 008_action_source_timestamp
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_action_needs_confirmation"
down_revision: Union[str, None] = "008_action_source_timestamp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.add_column(
            sa.Column("needs_confirmation", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.drop_column("needs_confirmation")