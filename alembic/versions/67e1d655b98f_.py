"""empty message

Revision ID: 67e1d655b98f
Revises: b054e8713682
Create Date: 2021-02-04 13:06:51.812396

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67e1d655b98f'
down_revision = 'b054e8713682'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image", sa.Column('base_template', sa.String(length=100)))
    op.add_column("nb_docker_image", sa.Column('package_type', sa.String(length=20)))


def downgrade():
    op.drop_column("nb_docker_image", "base_template")
    op.drop_column("nb_docker_image", "package_type")
