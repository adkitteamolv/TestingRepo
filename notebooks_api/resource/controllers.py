#! -*- coding: utf-8 -*-
"""Controllers for resources"""
import logging

from flasgger.utils import swag_from
from flask import Response, jsonify, request

from notebooks_api.utils.data import clean_data

from . import resource_api
from .manager import (
    create_resource,
    delete_resource,
    fetch_resources,
    read_resource,
    update_resource,
)


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


@resource_api.route("/v1/resources", methods=["GET"])
@swag_from("swags/list.yaml")
def list_api():
    """
    API to list resources
    """
    # pylint: disable=line-too-long
    resources = fetch_resources(all_resources=False) if request.args.get("all_resources") is None else fetch_resources(all_resources=True)

    # send response
    return jsonify(resources)


@resource_api.route("/v1/resources", methods=["POST"])
@swag_from("swags/create.yaml", validation=True, schema_id="create_resource")
def create_api():
    """
    API to create resource
    """

    # parse input data
    data = request.get_json()
    data = clean_data(data)

    # create log
    log.debug("Creating resource with data=%s", data)

    # create resource
    resource = create_resource(data)

    # send response
    return jsonify(resource), 201


@resource_api.route("/v1/resources/<uuid:resource_id>", methods=["GET"])
@swag_from("swags/read.yaml")
def read_api(resource_id):
    """
    API to read resource by id
    """

    # cast to string
    resource_id = str(resource_id)

    # fetch resource with given id
    resource = read_resource(resource_id)

    # send response
    return jsonify(resource)


@resource_api.route("/v1/resources/<uuid:resource_id>", methods=["PUT"])
@swag_from("swags/update.yaml", validation=True, schema_id="update")
def update_api(resource_id):
    """
    API to update resource by id
    """

    # cast to string
    resource_id = str(resource_id)

    # parse input
    data = request.get_json()
    data = clean_data(data, update=True)

    # Update resource log
    log.debug(
        "Updating resource for resource_id=%s data=%s",
        resource_id,
        data)

    # fetch resource using id
    update_resource(resource_id, data)

    # send response
    return Response(status=200)


@resource_api.route("/v1/resources/<uuid:resource_id>", methods=["DELETE"])
@swag_from("swags/delete.yaml")
def delete_api(resource_id):
    """
    API to delete resource by id
    """

    # cast to string
    resource_id = str(resource_id)

    # Deleting resource log
    log.debug("Deleting resource for  resource_id=%s", resource_id)

    # delete resource
    delete_resource(resource_id)

    # send response
    return Response(status=204)
