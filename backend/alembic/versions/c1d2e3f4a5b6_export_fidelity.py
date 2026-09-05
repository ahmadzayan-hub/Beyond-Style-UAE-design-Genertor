"""exports: fidelity + manifest (Export Fidelity Gate)

Revision ID: c1d2e3f4a5b6
Revises: b7c3e9d4a1f0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "b7c3e9d4a1f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exports", sa.Column("fidelity", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("exports", sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("exports", "manifest")
    op.drop_column("exports", "fidelity")
