"""CP14 add quote revisions table

Revision ID: e6a7b8c9d0f1
Revises: d4e5f6a7b8c9
Create Date: 2026-10-20 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e6a7b8c9d0f1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add quote_revisions table and immutability trigger."""
    op.create_table(
        'quote_revisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('quote_version', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('change_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('snapshot_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name='fk_quote_revisions_quote_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_quote_revisions_user_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quote_id', 'revision_number', name='uq_quote_revisions_quote_id_revision_number')
    )
    op.create_index(op.f('ix_quote_revisions_id'), 'quote_revisions', ['id'], unique=False)
    op.create_index(op.f('ix_quote_revisions_quote_id'), 'quote_revisions', ['quote_id'], unique=False)
    op.create_index(op.f('ix_quote_revisions_user_id'), 'quote_revisions', ['user_id'], unique=False)

    # Database-level immutability protection: prevent UPDATE and DELETE on quote_revisions
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_quote_revision_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'quote_revisions records are immutable and cannot be updated or deleted';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_quote_revisions_immutable
    BEFORE UPDATE OR DELETE ON quote_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_quote_revision_mutation();
    """)


def downgrade() -> None:
    """Downgrade schema to remove quote_revisions table safely."""
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT count(*) FROM quote_revisions")).scalar()
    if result and result > 0:
        raise RuntimeError(
            f"Cannot downgrade: {result} quote revision record(s) exist. "
            "Dropping the table would destroy historical audit data."
        )

    # Drop trigger and function in reverse order of creation
    op.execute("DROP TRIGGER IF EXISTS trg_quote_revisions_immutable ON quote_revisions;")
    op.execute("DROP FUNCTION IF EXISTS prevent_quote_revision_mutation();")

    op.drop_index(op.f('ix_quote_revisions_user_id'), table_name='quote_revisions')
    op.drop_index(op.f('ix_quote_revisions_quote_id'), table_name='quote_revisions')
    op.drop_index(op.f('ix_quote_revisions_id'), table_name='quote_revisions')
    op.drop_table('quote_revisions')
