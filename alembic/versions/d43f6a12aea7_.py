"""empty message

Revision ID: d43f6a12aea7
Revises: 844a58b24f46
Create Date: 2019-11-11 20:20:07.813767

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd43f6a12aea7'
down_revision = '844a58b24f46'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column("init_script", sa.Text()))


def downgrade():
    op.drop_column("nb_docker_image", "init_script")
