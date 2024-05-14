"""Added tables to store packages and versions

Revision ID: a9b4edede4c3
Revises: 91607552aab4
Create Date: 2023-03-27 12:35:48.208093

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9b4edede4c3'
down_revision = '91607552aab4'
branch_labels = None
depends_on = None


def upgrade():
    # add new columns
    op.add_column('nb_pypi_package', sa.Column('package_name', sa.String(length=255), nullable=True))
    op.add_column('nb_pypi_package', sa.Column('package_version', sa.String(length=50), nullable=True))
    op.add_column('nb_pypi_package', sa.Column('language', sa.String(length=50), nullable=True))
    op.add_column('nb_pypi_package', sa.Column('language_version', sa.String(length=50), nullable=True))

    # remove old column
    op.drop_column('nb_pypi_package', 'name')

    # Rename tables to more generic names
    op.rename_table('nb_pypi_package', 'nb_external_package')
    op.rename_table('nb_pypi_package_version', 'nb_external_package_version')



def downgrade():
    # Rename table 
    op.rename_table('nb_external_package', 'nb_pypi_package')
    op.rename_table('nb_external_package_version', 'nb_pypi_package_version')

    # add old column back
    op.add_column('nb_pypi_package', sa.Column('name', sa.String(length=255), nullable=True))

    # remove new columns
    op.drop_column('nb_pypi_package', 'package_name')
    op.drop_column('nb_pypi_package', 'package_version')
    op.drop_column('nb_pypi_package', 'language')
    op.drop_column('nb_pypi_package', 'language_version')
    