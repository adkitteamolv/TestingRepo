"""Convert datatype of git_macros_config in nb_docker_image

Revision ID: 30d2b79c2c2d
Revises: 82435a37de09
Create Date: 2021-03-23 00:51:11.257163

"""
import sqlalchemy as sa
from alembic import op

from notebooks_api.db_utility import upgrade_alter_column
# revision identifiers, used by Alembic.
revision = '30d2b79c2c2d'
down_revision = '82435a37de09'
branch_labels = None
depends_on = None


def upgrade():
    """
    :return:
    """
    op.alter_column('nb_docker_image', 'git_macros_config',
                    existing_type=sa.JSON,
                    type_=sa.String(length=500),
                    existing_nullable=True)
    # upgrade_alter_column(table_name="nb_docker_image", column_name="git_macros_config",
    #                      type_=sa.String, existing_type=sa.JSON,
    #                      server_default=None, new_column_name=None, existing_nullable=True)


def downgrade():
    """
    :return:
    """
    upgrade_alter_column(table_name="nb_docker_image", column_name="git_macros_config", existing_type=sa.String(500),
                         type_=sa.JSON,
                         server_default=None, new_column_name=None, existing_nullable=True)

    # op.alter_column('nb_docker_image', 'git_macros_config',
    #                 type_=sa.JSON,
    #                 existing_type=sa.String(length=255),
    #                 existing_nullable=True)
