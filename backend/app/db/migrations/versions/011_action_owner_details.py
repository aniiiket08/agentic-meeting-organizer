"""Store action owners who are not registered users.

Revision ID: 011_action_owner_details
Revises: 010_meeting_invitees_options
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_action_owner_details"
down_revision: Union[str, None] = "010_meeting_invitees_options"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.add_column(sa.Column("owner_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("owner_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("action_items") as batch_op:
        batch_op.drop_column("owner_email")
        batch_op.drop_column("owner_name")