"""add column snapshot_life

Revision ID: 10599284cae5
Revises: c99939b65b7e
Create Date: 2022-08-11 16:11:30.399984

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10599284cae5'
down_revision = 'b9f14542a014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_data_snapshot", sa.Column("snapshot_life", sa.Integer(), server_default='90'))


def downgrade():
    op.drop_column('nb_data_snapshot', 'snapshot_life')
