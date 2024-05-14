"""empty message

Revision ID: 285a83b49a94
Revises: 03c1a5760c79
Create Date: 2021-08-12 21:40:37.364678

"""
from alembic import op
import sqlalchemy as sa

from notebooks_api.db_utility import upgrade_alter_column

# revision identifiers, used by Alembic.
revision = '285a83b49a94'
down_revision = '03c1a5760c79'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ad_user', 'user_id', existing_type=sa.Integer, type_=sa.String(length=30),
                    existing_nullable=False)
    op.alter_column('ad_group', 'group_id', existing_type=sa.Integer, type_=sa.String(length=30),
                    existing_nullable=False)
    op.alter_column('ad_mapping', 'user_id', existing_type=sa.Integer, type_=sa.String(length=30),
                    existing_nullable=False)
    op.alter_column('ad_mapping', 'group_id', existing_type=sa.Integer, type_=sa.String(length=30),
                    existing_nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    upgrade_alter_column(table_name="ad_user", column_name="user_id", existing_type=sa.String(length=30),
                         type_=sa.Integer, existing_nullable=False)
    upgrade_alter_column(table_name="ad_group", column_name="group_id", existing_type=sa.String(length=30),
                         type_=sa.Integer, existing_nullable=False)
    upgrade_alter_column(table_name="ad_mapping", column_name="user_id", existing_type=sa.String(length=30),
                         type_=sa.Integer, existing_nullable=False)
    upgrade_alter_column(table_name="ad_mapping", column_name="group_id", existing_type=sa.String(length=30),
                         type_=sa.Integer, existing_nullable=False)
    # ### end Alembic commands ###
