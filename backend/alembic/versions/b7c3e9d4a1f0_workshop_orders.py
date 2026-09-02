"""Workshop OS orders (state machine + delivery completion fields).

Revision ID: b7c3e9d4a1f0
Revises: a9d24c8e01b7
Create Date: 2026-08-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c3e9d4a1f0"
down_revision: Union[str, None] = "a9d24c8e01b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workshop_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("design_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("design_versions.id"), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_approvals.id"), nullable=False),
        sa.Column("approval_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("material", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("history", postgresql.JSONB()),
        sa.Column("rework_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("receiver_name", sa.String(120)),
        sa.Column("staff_number", sa.String(40)),
        sa.Column("actual_received_date", sa.Date()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.UniqueConstraint("design_version_id"),
    )


def downgrade() -> None:
    op.drop_table("workshop_orders")
