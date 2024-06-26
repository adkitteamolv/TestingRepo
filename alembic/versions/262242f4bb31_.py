"""Git_macros_config column dtype change varchar(500) -> Text

Revision ID: 262242f4bb31
Revises: 70bfd092da16
Create Date: 2021-05-12 09:39:13.884375

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '262242f4bb31'
down_revision = '70bfd092da16'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('nb_docker_image', 'git_macros_config',
                    existing_type=sa.String(length=500),
                    type_=sa.Text,
                    existing_nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('nb_docker_image', 'git_macros_config',
                    type_=sa.String(length=500),
                    existing_type=sa.Text,
                    existing_nullable=True)
    # ### end Alembic commands ###
