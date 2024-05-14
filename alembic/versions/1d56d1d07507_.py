"""empty message

Revision ID: 1d56d1d07507
Revises: d43f6a12aea7
Create Date: 2019-12-30 15:34:59.294545

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d56d1d07507'
down_revision = 'd43f6a12aea7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('nb_docker_image', sa.Column('cran_packages', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('nb_docker_image', 'cran_packages')
