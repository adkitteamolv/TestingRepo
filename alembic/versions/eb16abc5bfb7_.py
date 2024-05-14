"""empty message

Revision ID: eb16abc5bfb7
Revises: 5e57aa82d34e
Create Date: 2020-04-07 12:21:03.468029

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb16abc5bfb7'
down_revision = '5e57aa82d34e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_template_status", sa.Column("project_id", sa.String(length=60)))


def downgrade():
    op.drop_column("nb_template_status", "project_id")
