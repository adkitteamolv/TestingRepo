"""added column access_category in nb_git_repo

Revision ID: d386484e9c38
Revises: 262242f4bb31
Create Date: 2021-06-09 11:17:57.047773

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api.db_utility import drop_custom_type_enum, add_column_enum_type

# revision identifiers, used by Alembic.
revision = 'd386484e9c38'
down_revision = '262242f4bb31'
branch_labels = None
depends_on = None



def upgrade():
    add_column_enum_type('nb_git_repository', 'access_category', 'RepoAccessCategory', 'PUBLIC', 'PUBLIC', 'PRIVATE')


def downgrade():
    # pass
    op.drop_column('nb_git_repository', 'access_category')
    drop_custom_type_enum(sa.Enum('PUBLIC', 'PRIVATE', name='RepoAccessCategory'))
