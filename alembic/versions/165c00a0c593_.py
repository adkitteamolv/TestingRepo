"""empty message

Revision ID: 165c00a0c593
Revises: 59015e7f66a7
Create Date: 2021-07-28 13:30:34.562663

"""
from alembic import op
import sqlalchemy as sa




# revision identifiers, used by Alembic.
revision = '165c00a0c593'
down_revision = '59015e7f66a7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
    	"nb_notebook_pod_metrics",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=60), nullable=False),
        sa.Column('updated_on', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=60), nullable=False),
    	sa.Column('max_memory', sa.Float(), nullable=False),
    	sa.Column('max_cpu', sa.Float(), nullable=False),
        sa.Column('project_id', sa.String(length=60), nullable=True),
        sa.Column('template_id', sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['nb_template_status.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("nb_notebook_pod_metrics")
    # ### end Alembic commands ###
