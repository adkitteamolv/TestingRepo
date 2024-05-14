#! -*- coding: utf-8 -*-
"""Resource manager module"""

import logging
from flask import (
    current_app as app,
    g,
)

from .models import Resource, db
from .constants import ResourceStatus


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.resource")


def fetch_resources(all_resources):
    """ Fetch resources """

    # query database
    if not all_resources:
        # pylint: disable=line-too-long
        result_set = Resource.query.filter(Resource.extra.in_((app.config["GPU_RESOURCE_KEYS"] + ",cpu").split(","))).filter(
            Resource.status == ResourceStatus.ENABLED).all()
    else:
        result_set = Resource.query.all()
    # prepare response
    resource_set = [x.as_dict() for x in result_set]
    return resource_set


def create_resource(data):
    """
    Create resource

    Args:
        data (dict): Dictionary of data
    """

    # updated user info
    data.update({
        "created_by": g.user["mosaicId"],
        "updated_by": g.user["mosaicId"]
    })

    # ignore timestamps
    data.pop("created_on", None)
    data.pop("updated_on", None)

    try:
        # create object
        resource = Resource(**data)
        # save object
        db.session.add(resource)
        db.session.commit()
        return resource.as_dict()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return e.args[0]


def read_resource(resource_id):
    """
    Read resource using the id

    Args:
        resource_id (str): UUID of the resource
    """

    # fetch object
    resource = Resource.query.get(resource_id)
    return resource.as_dict()


def update_resource(resource_id, data):
    """
    Update the resource

    Args:
        resource_id (str): UUID of the resource
        data (dict): Dictionary of data
    """

    # fetch object
    resource = Resource.query.get(resource_id)

    # updated user info
    data.update({
        "updated_by": g.user["mosaicId"]
    })

    # ignore timestamps
    data.pop("updated_on", None)

    # update object
    for key, val in data.items():
        setattr(resource, key, val)

    try:
        # save to db
        db.session.add(resource)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    return resource.as_dict()


def delete_resource(resource_id):
    """
    Delete resource

    Args:
        resource_id (str): UUID of the resource
    """

    # fetch object
    resource = Resource.query.get(resource_id)

    try:
        # delete from db
        db.session.delete(resource)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
