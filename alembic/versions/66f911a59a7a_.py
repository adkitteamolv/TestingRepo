"""empty message

Revision ID: 66f911a59a7a
Revises: cbc2793db6a0
Create Date: 2020-10-15 09:28:52.640572

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '66f911a59a7a'
down_revision = 'cbc2793db6a0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column("gpu_docker_url", sa.String(200)))


def downgrade():
    op.drop_column("nb_docker_image", "gpu_docker_url")
