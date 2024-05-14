"""empty message

Revision ID: cfc8bb04daa2
Revises: 66f911a59a7a
Create Date: 2020-10-20 13:05:00.031558

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfc8bb04daa2'
down_revision = '66f911a59a7a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nb_docker_image_extra_attributes",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=60), nullable=False),
        sa.Column('updated_on', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=60), nullable=False),
        sa.Column("port", sa.String(10), nullable=True),
        sa.Column("cmd", sa.String(500), nullable=True),
        sa.Column("args", sa.String(500), nullable=True),
        sa.Column("base_url_env_key", sa.String(50), nullable=True),
        sa.Column("base_url_env_value", sa.String(50), nullable=True),
        sa.Column('base_image_id', sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(["base_image_id"], ["nb_docker_image.id"]),
    )


def downgrade():
    op.drop_table('nb_docker_image_extra_attributes')
