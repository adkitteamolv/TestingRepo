#! -*- coding: utf-8 -*-

""" CLI for the app """

import click
from flask.cli import FlaskGroup
from sqlalchemy import MetaData
from sqlalchemy_schemadisplay import create_schema_graph

from notebooks_api import get_application
from notebooks_api.docker_image.data import load_data as docker_image_data
from notebooks_api.docker_image.models import db as docker_image_db
from notebooks_api.notebook.models import db as notebook_db
from notebooks_api.pypi.data import load_data as pypi_data
from notebooks_api.pypi.models import db as pypi_db
from notebooks_api.pypi.pypi_index import create_index
from notebooks_api.resource.data import load_data as resource_data
from notebooks_api.resource.models import db as resource_db
from notebooks_api.clear_snapshot import remove_old_snapshot_delete_job, get_elegible_snapshot, snapshot_delete_minio, snapshot_delete_db, nas_package_log_delete
from notebooks_api.plugin.data import load_data as plugin_data
from notebooks_api.plugin.models import db as plugin_db
from notebooks_api.pypi.pypi_index import search_package

# pylint: disable=invalid-name

app = get_application()

# initialize db
resource_db.init_app(app)
notebook_db.init_app(app)
docker_image_db.init_app(app)
pypi_db.init_app(app)
plugin_db.init_app(app)


def app_factory():
    """ App method """
    return app


@click.group(cls=FlaskGroup, create_app=app_factory)
def cli():
    """ CLI for mosaic notebooks """


def create_db():
    """ Create database """
    resource_db.create_all()
    docker_image_db.create_all()
    notebook_db.create_all()
    pypi_db.create_all()
    plugin_db.create_all()


def load_data():
    """ Load sample data"""
    resource_data()
    docker_image_data()
    plugin_data()


@cli.command()
def erdiagram():
    """ Generate ER diagram """
    connection_string = app.config["SQLALCHEMY_DATABASE_URI"]
    graph = create_schema_graph(
        metadata=MetaData(connection_string),
        show_datatypes=False,
        show_indexes=False,
        rankdir='LR',
        concentrate=False
    )
    graph.write_png('erdiagram.png')


@cli.command()
def snapshot():
    """ Load master data """
    snap_list = []
    with app.app_context():
        elegible_snapshot = get_elegible_snapshot()
        for snapshot in elegible_snapshot:
            if snapshot_delete_minio(snapshot):
                snap_list.append(snapshot['snapshot_name'])
        if snap_list:
            snapshot_delete_db(snap_list)
        nas_package_log_delete()


@cli.command()
def data():
    """ Load master data """
    with app.app_context():
        load_data()


@cli.command()
def packagedb():
    """ Load package and version data """
    with app.app_context():
        pypi_data()


@cli.command()
def test():
    """ Run test cases """
    with app.app_context():
        create_db()
        load_data()
        pypi_data()


@cli.command()
def index():
    """ Creating elastic index of pypi packages"""
    with app.app_context():
        create_index(refresh=False)


@cli.command()
def refresh():
    """ Refresh records in elastic index of pypi packages"""
    with app.app_context():
        create_index(refresh=True)


@cli.command()
def indexr():
    """ Creating elastic index of CRAN packages"""
    with app.app_context():
        create_index(refresh=False, language='r')


@cli.command()
def refreshr():
    """ Refresh records in elastic index of CRAN packages"""
    with app.app_context():
        create_index(refresh=True, language='r')


@cli.command()
def indexc():
    """ Creating elastic index of conda packages"""
    with app.app_context():
        create_index(refresh=False, language='conda')


@cli.command()
def refreshc():
    """ Refresh records in elastic index of conda packages"""
    with app.app_context():
        create_index(refresh=True, language='conda')


@cli.command()
def indexcr():
    """ Creating elastic index of conda packages"""
    with app.app_context():
        create_index(refresh=False, language='conda-r')

@cli.command()
def indexallpackages():
    """ Fetch all packages and store in DB """
    with app.app_context():
        print("Fetching all packages")
        from datetime import datetime
        start_time = datetime.now() 
        create_index(refresh=False, language='r')
        end_time_r = datetime.now() 
        time_difference = (end_time_r - start_time).total_seconds() * 10**3
        time_difference = int(time_difference/(1000*60))%60
        print("Execution time of 'r' program is: ", time_difference, "min") 

        create_index(refresh=False, language='conda')
        end_time_conda = datetime.now() 
        time_difference = (end_time_conda - end_time_r).total_seconds() * 10**3
        time_difference = int(time_difference/(1000*60))%60
        print("Execution time of 'conda' program is: ", time_difference, "min") 

        create_index(refresh=False, language='conda-r')
        end_time_conda_r = datetime.now() 

        time_difference = (end_time_conda_r - end_time_conda).total_seconds() * 10**3
        time_difference = int(time_difference/(1000*60))%60
        print("Execution time of 'conda-r' program is: ", time_difference, "min") 

        create_index(refresh=False)
        end_time_conda_python = datetime.now() 

        time_difference = (end_time_conda_python - end_time_conda_r).total_seconds() * 10**3
        time_difference = int(time_difference/(1000*60))%60
        print("Execution time of 'python' program is: ", time_difference, "min") 



@cli.command()
def refreshcr():
    """ Refresh records in elastic index of conda packages"""
    with app.app_context():
        create_index(refresh=True, language='conda-r')


@cli.command()
def free():
    """ Delete snapshots which are not used in N days,  N can be configurable """
    with app.app_context():
        remove_old_snapshot_delete_job(app.config['DELETE_SNAPSHOT_OLD_THAN_DAYS'])


if __name__ == "__main__":
    cli()
