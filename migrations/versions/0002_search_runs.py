"""search runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07 22:47:59.600864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('search_runs',
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('query', sa.JSON(), nullable=False),
    sa.Column('sources_queried', sa.JSON(), nullable=False),
    sa.Column('postings_found', sa.Integer(), nullable=False),
    sa.Column('postings_deduped_new', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    # SQLite can't ALTER TABLE ADD CONSTRAINT directly -- batch mode
    # recreates the table under the hood (migrations/env.py's
    # render_as_batch=True note explains why this is needed here).
    with op.batch_alter_table('job_postings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('search_run_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_job_postings_search_run', 'search_runs', ['search_run_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('job_postings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_job_postings_search_run', type_='foreignkey')
        batch_op.drop_column('search_run_id')
    op.drop_table('search_runs')
