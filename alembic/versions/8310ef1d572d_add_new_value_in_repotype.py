"""Add new value in RepoType

Revision ID: 8310ef1d572d
Revises: 132ebebacd6a
Create Date: 2023-05-03 11:40:28.716712

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8310ef1d572d'
down_revision = '132ebebacd6a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE RepoType1 AS ENUM ('Gitlab', 'Bitbucket', 'Github', 'Azuredevops');")
    op.execute('ALTER TABLE nb_git_repository ALTER COLUMN repo_type TYPE RepoType1 USING repo_type::text::RepoType1;')
    op.execute('DROP TYPE "RepoType";')
    op.execute('ALTER TYPE repotype1 RENAME TO "RepoType";')

def downgrade():
    op.execute("CREATE TYPE RepoType2 AS ENUM ('Gitlab', 'Bitbucket', 'Github');")
    op.execute('ALTER TABLE nb_git_repository ALTER COLUMN repo_type TYPE RepoType2 USING repo_type::text::RepoType2;')
    op.execute('DROP TYPE "RepoType";')
    op.execute('ALTER TYPE repotype2 RENAME TO "RepoType";')
