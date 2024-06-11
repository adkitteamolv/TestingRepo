# -*- coding: utf-8 -*-
""" Utility file to handle DB type  differences"""
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from alembic import op
from notebooks_api import get_db_type

# pylint: disable=line-too-long,invalid-name,too-many-arguments

db_type = get_db_type()


# pylint: disable=inconsistent-return-statements
def upgrade_alter_column(table_name, column_name, existing_type=None, type_=None,
                         server_default=None, new_column_name=None, existing_nullable=None):
    """ Function to return alter statement based on db type"""
    if db_type == "mysql":
        return op.alter_column(
            table_name,
            column_name,
            existing_type=existing_type,
            type_=type_,
            server_default=server_default,
            new_column_name=new_column_name,
            existing_nullable=existing_nullable
            )
    if db_type == "postgresql":
        return op.alter_column(
            table_name,
            column_name,
            type_=type_,
            server_default=server_default,
            new_column_name=new_column_name,
            postgresql_using=None if new_column_name is not None else ("{}::text::{}".format(column_name, convert_mysql_to_postgres_datatype(type_))),
            existing_nullable=existing_nullable
            )


# pylint: disable=inconsistent-return-statements, keyword-arg-before-vararg
def add_column_enum_type(table_name, column_name=None, enum_name=None, server_default=None, *enum_value):
    """ Function to add enum column based on db type"""
    if db_type == "mysql":
        column_type = sa.Enum(*enum_value)
        op.add_column(table_name, sa.Column(column_name, column_type, server_default=server_default))
    if db_type == "postgresql":
        deployment_status = postgresql.ENUM(*enum_value, name=enum_name)
        deployment_status.create(op.get_bind())
        column_type = sa.Enum(*enum_value, name=enum_name)
        op.add_column(table_name, sa.Column(column_name, column_type, server_default=server_default))
    if db_type.startswith('sqlite'):
        column_type = sa.Enum(*enum_value)
        op.add_column(table_name, sa.Column(column_name, column_type, server_default=server_default))


def convert_mysql_to_postgres_datatype(d_type):
    """Return the corrsponding type of a datatype in mysql to corresponding in postgres"""
    if isinstance(d_type, sa.sql.sqltypes.LargeBinary):
        return "bytea"
    if d_type == sa.sql.sqltypes.JSON or isinstance(d_type, sa.sql.sqltypes.JSON):
        return "JSON"


def drop_custom_type_enum(enum_name):
    """ Function to drop custom type"""
    enum_name.drop(op.get_bind(), checkfirst=False)


def alter_enum_type(table_name, column_name, new_enum_value, old_enum_value):
    """ Function to change enum value"""
    if db_type == "mysql":
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.Enum(*old_enum_value),
            type_=sa.Enum(*new_enum_value),
        )
    if db_type == "postgresql":
        replace_enum_values(name=column_name, new=[*new_enum_value], old=[*old_enum_value],
                            modify=[(table_name, column_name)])


# pylint: disable=unused-argument
def replace_enum_values(
        name: str,
        old: [str],
        new: [str],
        modify: [(str, str, str)]
):
    """
    Replaces an enum's list of values.

    Args:
        name: Name of the enum
        new: New list of values
        old: Old list of values
        modify: List of tuples of table name
        and column to modify (which actively use the enum).
    """
    connection = op.get_bind()
    tmp_name = "{}_tmp".format(name)
    # Rename old type
    cmd = "ALTER TYPE {} RENAME TO {};".format(name, tmp_name)
    op.execute(cmd)
    # Create new type
    lsl = sa.Enum(*new, name=name)
    lsl.create(connection)
    # Replace all usages
    for (table, column) in modify:
        cmd_alter = ("ALTER TABLE {table} "
                     "ALTER COLUMN {column} TYPE {enum_name} USING {column}::text::{enum_name};"
        .format(
            table=table,
            column=column,
            enum_name=name
        ))
        op.execute(cmd_alter)
    # Remove old type
    cmd_drop = text("DROP TYPE " + tmp_name)
    op.execute(cmd_drop)

