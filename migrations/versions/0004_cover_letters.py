"""cover letters

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cover_letters',
    sa.Column('application_id', sa.String(length=36), nullable=True),
    sa.Column('job_posting_id', sa.String(length=36), nullable=False),
    sa.Column('resume_version_id', sa.String(length=36), nullable=False),
    sa.Column('template_id', sa.String(length=36), nullable=False),
    sa.Column('rendered_pdf_path', sa.Text(), nullable=False),
    sa.Column('rendered_tex_path', sa.Text(), nullable=False),
    sa.Column('agent_run_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
    sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cover_letters')
