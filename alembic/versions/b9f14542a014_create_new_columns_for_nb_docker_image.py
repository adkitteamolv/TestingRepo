"""create new columns for nb_docker_image

Revision ID: b9f14542a014
Revises: c99939b65b7e
Create Date: 2022-06-29 11:08:51.867520

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9f14542a014'
down_revision = 'c99939b65b7e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('nb_docker_image', sa.Column('number_of_executors', sa.INTEGER))
    op.add_column('nb_docker_image', sa.Column('executor_resource_id', sa.String(length=60),
                                               sa.ForeignKey('nb_resource.id')))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('nb_docker_image', 'number_of_executors')
    op.drop_column('nb_docker_image', 'executor_resource_id')
    # ### end Alembic commands ###