"""alter to add commit_type column

Revision ID: a8195a66d634
Revises: eb16abc5bfb7
Create Date: 2020-08-13 12:40:13.279897

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8195a66d634'
down_revision = 'eb16abc5bfb7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column("auto_commit", sa.Boolean(), server_default='1'))

def downgrade():
    op.drop_column('nb_docker_image', 'auto_commit')
