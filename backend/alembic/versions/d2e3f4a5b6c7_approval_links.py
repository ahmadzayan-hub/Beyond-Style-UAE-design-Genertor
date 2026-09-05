"""approval_links: single-use, expiring secure customer approval links

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("design_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("geometry_hash", sa.String(64), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customer_approvals.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approval_links")
