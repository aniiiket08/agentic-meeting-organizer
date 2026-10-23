"""Persist external invitees and meeting scheduling preferences.

Revision ID: 010_meeting_invitees_options
Revises: 009_action_needs_confirmation
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_meeting_invitees_options"
down_revision: Union[str, None] = "009_action_needs_confirmation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("attendees") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("external_email", sa.String(length=255), nullable=True))

    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("target_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "equipment_needed",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_column("equipment_needed")
        batch_op.drop_column("target_date")

    with op.batch_alter_table("attendees") as batch_op:
        batch_op.drop_column("external_email")
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )