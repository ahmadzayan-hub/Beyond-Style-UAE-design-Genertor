"""golden production cases

Revision ID: c1a7f30b52d4
Revises: 9520aa9396f0
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1a7f30b52d4'
down_revision: Union[str, None] = '9520aa9396f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'golden_production_cases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('case_id', sa.String(length=64), nullable=False),
        sa.Column('customer_source_text', sa.Text(), nullable=True),
        sa.Column('source_text_status', sa.String(length=40), nullable=False),
        sa.Column('source_text_authority', sa.String(length=48), nullable=False),
        sa.Column('source_text_sha256', sa.String(length=64), nullable=True),
        sa.Column('primary_names', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('language', sa.String(length=16), nullable=False),
        sa.Column('product_type', sa.String(length=48), nullable=False),
        sa.Column('layout_style', sa.String(length=48), nullable=True),
        sa.Column('composition_type', sa.String(length=48), nullable=True),
        sa.Column('construction', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('construction_topology', sa.String(length=96), nullable=True),
        sa.Column('attachment_topology', sa.String(length=96), nullable=True),
        sa.Column('attachment_points', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('chain_topology', sa.String(length=96), nullable=True),
        sa.Column('design_version_id', sa.UUID(), nullable=True),
        sa.Column('canonical_geometry_hash', sa.String(length=64), nullable=True),
        sa.Column('lineage_status', sa.String(length=48), nullable=False),
        sa.Column('material', sa.String(length=64), nullable=True),
        sa.Column('finish', sa.String(length=64), nullable=True),
        sa.Column('dimensions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('stone_or_pearl_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('workshop_changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('manufacturing_result', sa.String(length=32), nullable=False),
        sa.Column('production_success', sa.Boolean(), nullable=False),
        sa.Column('customer_feedback', sa.Text(), nullable=True),
        sa.Column('customer_sentiment', sa.String(length=32), nullable=False),
        sa.Column('customer_approved', sa.Boolean(), nullable=False),
        sa.Column('memory_tier', sa.String(length=48), nullable=False),
        sa.Column('evidence_tier', sa.String(length=48), nullable=False),
        sa.Column('ranking_weight', sa.String(length=16), nullable=False),
        sa.Column('design_fidelity_score', sa.Float(), nullable=True),
        sa.Column('stage_comparison', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('lessons_learned', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('design_dna', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('dna_embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('encoder_version', sa.String(length=32), nullable=False),
        sa.Column('retrieval_keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rights_provenance', sa.String(length=48), nullable=False),
        sa.Column('privacy_status', sa.String(length=32), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['design_version_id'], ['design_versions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id'),
    )


def downgrade() -> None:
    op.drop_table('golden_production_cases')
