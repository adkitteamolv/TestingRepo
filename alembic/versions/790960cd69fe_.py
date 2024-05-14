""" Column container_uid added in nb_docker_image_extra_attributes

Revision ID: 790960cd69fe
Revises: 285a83b49a94
Create Date: 2021-09-01 11:09:06.189490

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '790960cd69fe'
down_revision = '285a83b49a94'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_docker_image_extra_attributes", sa.Column("container_uid", sa.String(6)))

def downgrade():
    op.drop_column('nb_docker_image_extra_attributes', 'container_uid')
