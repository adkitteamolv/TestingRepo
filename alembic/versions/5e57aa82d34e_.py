"""empty message

Revision ID: 5e57aa82d34e
Revises: 6959542e0908
Create Date: 2020-02-10 15:12:27.436983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e57aa82d34e'
down_revision = '6959542e0908'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column("index_url", sa.Text()))


def downgrade():
    op.drop_column("nb_docker_image", "index_url")
