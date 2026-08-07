"""application document links

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER TABLE ADD CONSTRAINT directly -- batch mode
    # recreates the table under the hood (migrations/env.py's
    # render_as_batch=True note explains why this is needed here).
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('resume_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('cover_letter_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_applications_resume_version', 'resume_versions', ['resume_version_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_applications_cover_letter', 'cover_letters', ['cover_letter_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_applications_cover_letter', type_='foreignkey')
        batch_op.drop_constraint('fk_applications_resume_version', type_='foreignkey')
        batch_op.drop_column('cover_letter_id')
        batch_op.drop_column('resume_version_id')
