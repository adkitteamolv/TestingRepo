"""empty message

Revision ID: 1e16fef49797
Revises: 15a343de269f
Create Date: 2021-03-30 14:59:12.933324

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e16fef49797'
down_revision = '30d2b79c2c2d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "nb_git_repository_active",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('repo_id', sa.String(length=60), nullable=False),
        sa.Column('project_id', sa.String(length=60), nullable=False),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["nb_git_repository.repo_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint('id')
    )
    # pass
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('nb_git_repository_active')
    # op.drop_column('nb_git_repository')
    # pass
    # ### end Alembic commands ###