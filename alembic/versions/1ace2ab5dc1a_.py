"""empty message

Revision ID: 1ace2ab5dc1a
Revises: 694891f74d98
Create Date: 2018-11-23 17:30:12.306435

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ace2ab5dc1a'
down_revision = '694891f74d98'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('nb_notebook', sa.Column('icon', sa.String(length=200), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('nb_notebook', 'icon')
    # ### end Alembic commands ###
