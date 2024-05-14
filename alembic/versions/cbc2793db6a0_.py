"""empty message

Revision ID: cbc2793db6a0
Revises: 51d0498c0dc4
Create Date: 2020-10-13 16:25:06.633990

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api import get_db_type
from notebooks_api.db_utility import drop_custom_type_enum, add_column_enum_type


# revision identifiers, used by Alembic.
revision = 'cbc2793db6a0'
down_revision = '51d0498c0dc4'
branch_labels = None
depends_on = None

db_type = get_db_type()


def upgrade():
    add_column_enum_type('nb_resource', 'status', 'NBResourceStatus', 'ENABLED', 'ENABLED', 'DISABLED')


def downgrade():
    op.drop_column('nb_resource', 'status')
    drop_custom_type_enum(sa.Enum('ENABLED', 'DISABLED', name='NBResourceStatus'))
