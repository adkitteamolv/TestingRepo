"""version_metadata table creation

Revision ID: 7d5de2b8cabf
Revises: 
Create Date: 2024-02-28 10:19:06.101449

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d5de2b8cabf'
down_revision = 'a30e085a2025'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "version_metadata" not in tables:
        op.create_table('version_metadata',
        sa.Column('id', sa.Integer, nullable=False),
        sa.Column('component_type', sa.String(length=255), unique=False, nullable=False),
        sa.Column('component_id', sa.String(length=255), unique=False, nullable=False),
        sa.Column('project_id', sa.String(length=255), unique=False, nullable=False),
        sa.Column('commit_id', sa.String(length=255), nullable=False),
        sa.Column('commit_message', sa.String(length=255), nullable=False),
        sa.Column('version_number', sa.String(length=255), nullable=False),
        sa.Column('checked_in_by', sa.String(length=255), nullable=False),
        sa.Column('checked_in_time', sa.DateTime(), nullable=False),
        sa.Column("data", sa.JSON),
        sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    op.drop_table('version_metadata')

