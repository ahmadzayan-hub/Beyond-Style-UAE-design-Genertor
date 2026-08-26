"""golden case design process and variant selection

Revision ID: d3e8a11c74f6
Revises: c1a7f30b52d4
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd3e8a11c74f6'
down_revision: Union[str, None] = 'c1a7f30b52d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'golden_production_cases',
        sa.Column('design_process', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'golden_production_cases',
        sa.Column('variant_selection', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('golden_production_cases', 'variant_selection')
    op.drop_column('golden_production_cases', 'design_process')
