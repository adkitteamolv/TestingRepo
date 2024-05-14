"""empty message

Revision ID: 6959542e0908
Revises: 1d56d1d07507
Create Date: 2020-01-03 11:26:22.743083

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api import get_db_type
from notebooks_api.db_utility import drop_custom_type_enum


# revision identifiers, used by Alembic.
revision = '6959542e0908'
down_revision = '1d56d1d07507'
branch_labels = None
depends_on = None

db_type = get_db_type()


def upgrade():
    op.create_table('nb_template_status',
                    sa.Column('id', sa.String(length=60), nullable=False),
                    sa.Column('created_by', sa.String(length=60), nullable=False),
                    sa.Column('start_date', sa.DateTime(), nullable=True),
                    sa.Column('end_date', sa.DateTime(), nullable=True),
                    sa.Column('template_id', sa.String(length=60), nullable=False),
                    sa.Column('status', sa.Enum('STARTING', 'RUNNING', 'STOPPING', name='NBTemplateStatus'), nullable=True),
                    sa.Column('resource_id', sa.String(length=60), nullable=False),
                    sa.ForeignKeyConstraint(['template_id'], ['nb_docker_image.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['resource_id'], ['nb_resource.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('nb_template_status')
    drop_custom_type_enum(sa.Enum('STARTING', 'RUNNING', 'STOPPING', name='NBTemplateStatus'))
