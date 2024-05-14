"""empty message

Revision ID: f26932f1959a
Revises: 10599284cae5
Create Date: 2023-01-19 11:40:33.574347

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f26932f1959a'
down_revision = '10599284cae5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "cp_docker_image",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('base_image_type', sa.String(length=100), nullable=False),
        sa.Column('docker_url', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint("cp_docker_image_type", "cp_docker_image", ["base_image_type"])

    op.create_table(
        "cp_plugins",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=60), nullable=False),
        sa.Column('updated_on', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=60), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=100), nullable=False),
        sa.Column('plugin_type', sa.Enum('PRE_BUILD', 'CUSTOM_BUILD', name="plugin_type"), nullable=True),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum('enabled', 'disabled', name="plugin_state"), nullable=True),
        sa.Column('input_form_type', sa.Enum('json', 'file', name="form_input_type"), nullable=True),
        sa.Column('input_parameter_json', sa.JSON, default={}, nullable=False),
        sa.Column('input_parameter_file_name', sa.String(length=100), default="", nullable=False),
        sa.Column('base_image_type', sa.String(length=100), nullable=False),
        sa.Column('plugin_code_source', sa.String(length=100), nullable=False),
        sa.Column('valid_sections', sa.Enum('model', 'notebook', 'data', name='sections2'), nullable=True),
        sa.Column('execution_command', sa.String(length=200), default=""),
        sa.Column('icon', sa.String(length=100), nullable=False),
        sa.Column('width', sa.String(length=100), default="48px", nullable=False),
        sa.Column('height', sa.String(length=100), default="48px", nullable=False),
        sa.Column('color', sa.String(length=100), nullable=False),
        sa.Column('thumbnail', sa.String(length=5)),
        sa.Column('multiInputNode', sa.String(length=5), default="true"),
        sa.Column('nodeBackgroundColor', sa.String(length=5)),
        sa.ForeignKeyConstraint(["base_image_type"], ["cp_docker_image.base_image_type"]),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_unique_constraint("cp_plugins_name", "cp_plugins", ["name"])

    op.create_table(
        "cp_plugin_settings",
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('plugin_id', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('advanceSettings', sa.JSON, default={}, nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["cp_plugins.id"]),
        sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('cp_plugin_settings')
    op.drop_table('cp_plugins')
    op.drop_constraint("cp_docker_image_type", "cp_docker_image", type_='unique')
    op.drop_table('cp_docker_image')
    # ### end Alembic commands ###