"""design reviews (append-only human aesthetic review)

Revision ID: e2b91c4d7a05
Revises: d3e8a11c74f6
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e2b91c4d7a05'
down_revision: Union[str, None] = 'd3e8a11c74f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'design_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('recipe_hash', sa.String(length=64), nullable=False),
        sa.Column('product', sa.String(length=48), nullable=False),
        sa.Column('font_id', sa.String(length=64), nullable=False),
        sa.Column('feature_set', sa.String(length=64), nullable=False),
        sa.Column('font_axes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('reviewer', sa.String(length=120), nullable=False),
        sa.Column('decision', sa.String(length=32), nullable=False),
        sa.Column('review_mode', sa.String(length=24), nullable=False),
        sa.Column('scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('engineering_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('superseded', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_design_reviews_item_id', 'design_reviews', ['item_id'])
    op.create_index('ix_design_reviews_product', 'design_reviews', ['product'])
    op.create_index('ix_design_reviews_font_id', 'design_reviews', ['font_id'])
    # Append-only: a review is a record of what a person judged, so it may
    # never be edited or deleted. A revised opinion is a NEW row.
    op.execute("""
        CREATE OR REPLACE FUNCTION design_reviews_append_only()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'design_reviews is append-only: reviews cannot be % ', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER design_reviews_no_update
        BEFORE UPDATE OF item_id, reviewer, decision, scores, note, created_at
        ON design_reviews
        FOR EACH ROW EXECUTE FUNCTION design_reviews_append_only();
    """)
    op.execute("""
        CREATE TRIGGER design_reviews_no_delete
        BEFORE DELETE ON design_reviews
        FOR EACH ROW EXECUTE FUNCTION design_reviews_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS design_reviews_no_delete ON design_reviews")
    op.execute("DROP TRIGGER IF EXISTS design_reviews_no_update ON design_reviews")
    op.execute("DROP FUNCTION IF EXISTS design_reviews_append_only()")
    op.drop_table('design_reviews')
