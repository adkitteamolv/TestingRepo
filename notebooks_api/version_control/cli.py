# #! -*- coding: utf-8 -*-
#
# """ CLI for the app """
#
# import click
# from flask.cli import FlaskGroup
# from sqlalchemy import MetaData
# from sqlalchemy_schemadisplay import create_schema_graph
# from api.models import db as version_db
# from . import app as application
#
# # initialize db
# version_db.init_app(application)
#
# def app_factory():
#     return application
#
#
# @click.group(cls=FlaskGroup)
# def cli():
#     """ CLI for mosaic notebooks """
#     pass
#
#
# def create_db():
#     """ Create database """
#     version_db.create_all()
#
#
# @cli.command()
# def erdiagram():
#     """ Generate ER diagram """
#     connection_string = application.config["SQLALCHEMY_DATABASE_URI"]
#     graph = create_schema_graph(
#         metadata=MetaData(connection_string),
#         show_datatypes=False,
#         show_indexes=False,
#         rankdir='LR',
#         concentrate=False
#     )
#     graph.write_png('erdiagram.png')
#
# @cli.command()
# def test():
#     """ Run test cases """
#     with application.app_context():
#         create_db()
#
# if __name__ == "__main__":
#     cli()
