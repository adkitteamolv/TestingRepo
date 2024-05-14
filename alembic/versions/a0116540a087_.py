"""empty message

Revision ID: a0116540a087
Revises: cfc8bb04daa2
Create Date: 2020-11-23 13:31:26.727899

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api.db_utility import drop_custom_type_enum


# revision identifiers, used by Alembic.
revision = 'a0116540a087'
down_revision = 'cfc8bb04daa2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nb_git_repository",
        sa.Column('repo_id', sa.String(length=60), nullable=False),
        sa.Column('project_id', sa.String(length=60), nullable=False),
        sa.Column('repo_url', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=60), nullable=True),
        sa.Column('password', sa.String(length=60), nullable=True),
        sa.Column("repo_name", sa.String(length=200), nullable=False),
        sa.Column("repo_status", sa.Enum('Enabled', 'Disabled', name="RepoStatus"), nullable=False),
        sa.Column("base_folder", sa.String(length=200), nullable=True),
        sa.Column("branch", sa.String(length=60), nullable=False),
        sa.Column("repo_type", sa.Enum('Gitlab', 'Bitbucket', 'Github', name="RepoType"), nullable=False),
        sa.PrimaryKeyConstraint('repo_id')
    )


def downgrade():
    op.drop_table('nb_git_repository')
    drop_custom_type_enum(sa.Enum('Gitlab', 'Bitbucket', 'Github', name='RepoType'))
    drop_custom_type_enum(sa.Enum('Enabled', 'Disabled', name='RepoStatus'))


