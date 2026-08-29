"""Ring inner-face engraving geometry columns.

Revision ID: a9d24c8e01b7
Revises: f4c07a13b8e2
Create Date: 2026-08-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9d24c8e01b7"
down_revision: Union[str, None] = "f4c07a13b8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("design_candidates", sa.Column("inner_text_geometry_wkt", sa.Text(), nullable=True))
    op.add_column("design_versions", sa.Column("inner_text_geometry_wkt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("design_versions", "inner_text_geometry_wkt")
    op.drop_column("design_candidates", "inner_text_geometry_wkt")
