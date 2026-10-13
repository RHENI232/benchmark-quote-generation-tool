"""Phase 1 add app_settings table

Revision ID: d4e5f6a7b8c9
Revises: ac6664ae68e8
Create Date: 2026-10-13 10:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'ac6664ae68e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('bool_value', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=False)
    op.execute(
        "INSERT INTO app_settings (key, bool_value, updated_at) "
        "VALUES ('catalog_entry_cost_visibility', true, CURRENT_TIMESTAMP) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_table('app_settings')

