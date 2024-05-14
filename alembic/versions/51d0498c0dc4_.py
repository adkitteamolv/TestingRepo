"""empty message

Revision ID: 51d0498c0dc4
Revises: a8195a66d634
Create Date: 2020-09-08 14:20:43.510455

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51d0498c0dc4'
down_revision = 'a8195a66d634'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('nb_template_status', sa.Column('pod_name', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('nb_template_status', 'pod_name')
