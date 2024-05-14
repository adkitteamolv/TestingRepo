"""empty message

Revision ID: 844a58b24f46
Revises: b387ee911e71
Create Date: 2019-09-30 15:49:30.875479

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '844a58b24f46'
down_revision = 'b387ee911e71'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column("kernel_type", sa.String(200)))
    op.execute("update nb_docker_image set kernel_type='python' where icon='python.svg';")
    op.execute("update nb_docker_image set kernel_type='r' where icon='r.svg';")
    op.execute("update nb_docker_image set kernel_type='spark' where icon='spark.svg';")


def downgrade():
    op.drop_column("nb_docker_image", "kernel_type")
