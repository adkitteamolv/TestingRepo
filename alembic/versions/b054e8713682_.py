"""empty message

Revision ID: b054e8713682
Revises: a0116540a087
Create Date: 2021-01-22 16:23:04.577823

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b054e8713682'
down_revision = 'a0116540a087'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nb_template_status", sa.Column('repo_id', sa.String(length=60)))
    op.add_column("nb_template_status", sa.Column('repo_name', sa.String(length=200)))


def downgrade():
    op.drop_column("nb_template_status", "repo_id")
    op.drop_column("nb_template_status", "repo_name")
