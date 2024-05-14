#! -*- coding: utf-8 -*-
"""default utils module"""
from uuid import uuid4
from notebooks_api import create_app


def default_id():
    """ Generate UUID """
    return str(uuid4())


def default_resource():
    """ Default resource """
    # pylint: disable=import-outside-toplevel
    from notebooks_api.resource.models import Resource
    app = create_app()
    default = app.config["DEFAULT_RESOURCE"]
    return Resource.query.filter(Resource.name == default).first().id


def register_metrics():
    """register metrics with app to capture api log."""
