#! -*- coding: utf-8 -*-
""" Celery tasks associated with pypi module """

from notebooks_api import make_celery

from .pypi_index import create_index


# pylint: disable=invalid-name
celery = make_celery()


@celery.task
def refresh():
    """Method to create index"""
    create_index()


@celery.task
def refresh_r():
    """Method to create index for r"""
    create_index(language='r')
