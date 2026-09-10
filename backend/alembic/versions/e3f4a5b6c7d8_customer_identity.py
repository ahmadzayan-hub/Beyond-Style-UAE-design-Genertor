"""customer identity: customers, login codes, customer sessions, request ownership

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contact_kind", sa.String(8), nullable=False),          # email | phone
        sa.Column("contact_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("contact_masked", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "customer_login_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivery_status", sa.String(40), nullable=False),
    )
    op.create_table(
        "customer_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("design_requests", sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                                               sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_design_requests_customer_id", "design_requests", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_design_requests_customer_id", table_name="design_requests")
    op.drop_column("design_requests", "customer_id")
    op.drop_table("customer_sessions")
    op.drop_table("customer_login_codes")
    op.drop_table("customers")
