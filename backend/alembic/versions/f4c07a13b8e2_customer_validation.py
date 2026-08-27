"""customer validation responses (separate from expert reviews)

Revision ID: f4c07a13b8e2
Revises: e2b91c4d7a05
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f4c07a13b8e2'
down_revision: Union[str, None] = 'e2b91c4d7a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'customer_validation_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('pack_id', sa.String(length=64), nullable=False),
        sa.Column('respondent_token', sa.String(length=64), nullable=False),
        sa.Column('would_buy', sa.String(length=16), nullable=False),
        sa.Column('premium_feel', sa.Integer(), nullable=False),
        sa.Column('readability', sa.Integer(), nullable=False),
        sa.Column('uniqueness', sa.Integer(), nullable=False),
        sa.Column('preferred_product', sa.String(length=48), nullable=True),
        sa.Column('price_band', sa.String(length=32), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cvr_item_id', 'customer_validation_responses', ['item_id'])
    op.create_index('ix_cvr_pack_id', 'customer_validation_responses', ['pack_id'])
    op.create_index('ix_cvr_respondent', 'customer_validation_responses', ['respondent_token'])
    # Append-only, like expert reviews: a customer's answer is a record of
    # what they said, not a mutable row.
    op.execute("""
        CREATE OR REPLACE FUNCTION customer_responses_append_only()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'customer_validation_responses is append-only: cannot %', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER cvr_no_update
        BEFORE UPDATE OF item_id, would_buy, premium_feel, readability, uniqueness, created_at
        ON customer_validation_responses
        FOR EACH ROW EXECUTE FUNCTION customer_responses_append_only();
    """)
    op.execute("""
        CREATE TRIGGER cvr_no_delete BEFORE DELETE ON customer_validation_responses
        FOR EACH ROW EXECUTE FUNCTION customer_responses_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS cvr_no_delete ON customer_validation_responses")
    op.execute("DROP TRIGGER IF EXISTS cvr_no_update ON customer_validation_responses")
    op.execute("DROP FUNCTION IF EXISTS customer_responses_append_only()")
    op.drop_table('customer_validation_responses')
