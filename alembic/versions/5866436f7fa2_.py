"""empty message

Revision ID: 5866436f7fa2
Revises: 1ace2ab5dc1a
Create Date: 2018-12-14 18:32:22.344415

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api import get_db_type
from notebooks_api.db_utility import drop_custom_type_enum


# revision identifiers, used by Alembic.
revision = '5866436f7fa2'
down_revision = '1ace2ab5dc1a'
branch_labels = None
depends_on = None

db_type = get_db_type()


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('nb_pod',
    sa.Column('id', sa.String(length=60), nullable=False),
    sa.Column('created_on', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('updated_on', sa.DateTime(), nullable=True),
    sa.Column('updated_by', sa.String(length=60), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('STARTING', 'RUNNING', 'STOPPING', name='NBPod'), nullable=True),
    sa.Column('docker_image_id', sa.String(length=60), nullable=True),
    sa.ForeignKeyConstraint(['docker_image_id'], ['nb_docker_image.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('nb_pod_tag',
    sa.Column('id', sa.String(length=60), nullable=False),
    sa.Column('created_on', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('updated_on', sa.DateTime(), nullable=True),
    sa.Column('updated_by', sa.String(length=60), nullable=False),
    sa.Column('tag', sa.String(length=200), nullable=False),
    sa.Column('pod_id', sa.String(length=60), nullable=True),
    sa.ForeignKeyConstraint(['pod_id'], ['nb_pod.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.drop_table('nb_notebook_pod')
    drop_custom_type_enum(sa.Enum('STARTING', 'RUNNING', 'STOPPING', name='NBPodStatus'))
    op.create_table('nb_notebook_pod',
    sa.Column('id', sa.String(length=60), nullable=False),
    sa.Column('created_on', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('updated_on', sa.DateTime(), nullable=True),
    sa.Column('updated_by', sa.String(length=60), nullable=False),
    sa.Column('pod_id', sa.String(length=60), nullable=True),
    sa.Column('notebook_id', sa.String(length=60), nullable=True),
    sa.ForeignKeyConstraint(['notebook_id'], ['nb_notebook.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pod_id'], ['nb_pod.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('nb_notebook_pod')
    op.drop_table('nb_pod_tag')
    op.drop_table('nb_pod')
    drop_custom_type_enum(sa.Enum('STARTING', 'RUNNING', 'STOPPING', name="NBPod"))

    op.create_table('nb_notebook_pod',
    sa.Column('id', sa.String(length=60), nullable=False),
    sa.Column('created_on', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('updated_on', sa.DateTime(), nullable=True),
    sa.Column('updated_by', sa.String(length=60), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('STARTING', 'RUNNING', 'STOPPING', name='NBPodStatus'), nullable=True),
    sa.Column('notebook_id', sa.String(length=60), nullable=True),
    sa.ForeignKeyConstraint(['notebook_id'], ['nb_notebook.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
