#! -*- coding: utf-8 -*-
""" Docker image API's module"""
from marshmallow import ValidationError

import logging
import json
from flasgger import swag_from
from flask import Response, jsonify, request
from flask import current_app as app
from mosaic_utils.ai.audit_log.utils import audit_logging
from notebooks_api.utils.data import clean_data
from .models import DockerImage, DockerImageTag, db
from . import docker_image_api
from .manager import (
    create_docker_image,
    create_base_template,
    delete_docker_image,
    fetch_docker_images,
    read_docker_image,
    update_docker_image,
    list_docker_images,
    list_all_docker_images,
    fetch_commands_for_scheduling,
    list_all_template_resources,
    toggle_docker_image_status,
    list_docker_images_type
)
from .validators import (
    validate_update,
    create as validate_create,
    validate_delete,
    check_for_duplicate

)
from .schemas import (
    validate_create_base_template
)

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


@docker_image_api.route("/v1/docker-images", methods=["GET"])
@swag_from("swags/list.yaml")
def list_api():
    """
    API to list the docker images
    """
    # parse input data
    project = request.args.get("project")
    image_type = request.args.get("type")
    kernel_type = request.args.get("kernel_type")
    if image_type and kernel_type and project:
        # list images to edit notebook
        docker_images = list_docker_images(image_type, kernel_type, project)
    elif image_type and project:
        # fetch docker image object
        docker_images = fetch_docker_images(image_type, project)
    elif image_type:
        # fetch local prebuild docker image object
        docker_images = list_docker_images_type(image_type)
    else:
        docker_images = list_all_docker_images(project)
    # send response
    return jsonify(docker_images)


@docker_image_api.route("/v1/docker-images", methods=["POST"])
@swag_from(
    "swags/create.yaml",
    validation=True,
    schema_id="create_docker_image",
    validation_function=validate_create
)
def create_api():
    """
    API to create the docker image
    """

    # parse and clean input data
    try:
        data = request.get_json()
        data = clean_data(data)

        # create docker image object
        result = create_docker_image(data)
        log.debug("audit_logging create template : %s", result.as_dict().get("id"))
        log.debug(result.as_dict())
        audit_logging(
            console_url=app.config["CONSOLE_BACKEND_URL"],
            action_type="CREATE",
            object_id=result.as_dict().get("id"),
            object_name=result.as_dict().get("name"),
            object_type="TEMPLATE",
            object_json=json.dumps(data),
            headers=request.headers,
        )

        # committing to database as entire execution has completed successfully
        db.session.commit()
        # send response
        return jsonify(result.as_dict()), 201
    except Exception as e:
        log.exception(e)
        # rolling back the transaction on failure
        db.session.rollback()

@docker_image_api.route("/v1/docker-images/create_base_template", methods=["POST"])
@swag_from(
    "swags/create_base_template.yaml",
    validation=True,
    validation_function=validate_create
)
def create_base_template_api():
    """
    API to create the base template
    """
    project_id = request.args.get("project")
    # # parse and clean input data
    data = request.get_json()
    data = clean_data(data)
    try:
        validate_create_base_template(data)
    except ValidationError as ex:
        log.info(ex)
        return Response(str(ex), status=400)
    result = create_base_template(data)
    log.debug("audit_logging create base template : %s", result.as_dict().get("id"))
    log.debug(result.as_dict())
    if 'X-Project-Id' in request.headers:
        audit_logging(
            console_url=app.config["CONSOLE_BACKEND_URL"],
            action_type="CREATE",
            object_id=result.as_dict().get("id"),
            object_name=result.as_dict().get("name"),
            object_type="TEMPLATE",
            object_json=json.dumps(data),
            headers=request.headers,
        )

    # send response
    return jsonify(result.as_dict()), 201


@docker_image_api.route("/v1/docker-images/<uuid:docker_image_id>",
                        methods=["GET"])
@swag_from("swags/read.yaml")
def read_api(docker_image_id):
    """
    API to fetch the docker image

    Args:
        docker_image_id (UUID): UUID of the docker image
    """
    # parse input data
    docker_image_id = str(docker_image_id)

    # fetch docker image
    docker_image = read_docker_image(docker_image_id)

    # send response
    return jsonify(docker_image)


@docker_image_api.route("/v1/docker-images/<uuid:docker_image_id>",
                        methods=["PUT"])
@swag_from(
    "swags/update.yaml",
    validation=True,
    schema_id="update_docker_image",
    validation_function=validate_update
)
def update_api(docker_image_id):
    """
    API to update the docker image

    Args:
        docker_image_id (UUID): UUID of the docker image
    """

    # parse and clean data
    data = request.get_json()
    data = clean_data(data, update=True)
    docker_image_id = str(docker_image_id)

    try:
        check_for_duplicate(
            data.get("name"),
            docker_image_id,
            data.get("tags"),
            True)
    # pylint: disable=broad-except
    except Exception as ex:
        return Response(ex.args[0], status=400)

    # update docker image
    log.debug("Updating docker image =%s", docker_image_id)
    update_docker_image(docker_image_id, data)
    log.debug("audit_logging update template : %s", docker_image_id)
    docker_image = DockerImage.query.get(docker_image_id)
    log.debug(docker_image.as_dict())
    audit_logging(
        console_url=app.config["CONSOLE_BACKEND_URL"],
        action_type="UPDATE",
        object_id=docker_image_id,
        object_name=docker_image.as_dict().get("name"),
        object_type="TEMPLATE",
        object_json=json.dumps(data),
        headers=request.headers,
    )


    # send response
    return Response(status=200)


@docker_image_api.route("/v1/docker-images/<uuid:docker_image_id>/toggle-display-status",
                        methods=["PUT"])
@swag_from(
    "swags/toggle.yaml",
    validation=True,
)
def toggle_display_status(docker_image_id):
    """
    API to update the docker image

    Args:
        docker_image_id (UUID): UUID of the docker image
    """
    try:
        data = request.get_json()
        toggle_docker_image_status(str(docker_image_id), data["show"])
        return Response("Updated", status=200)
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@docker_image_api.route("/v1/docker-images/<string:docker_image_id>",
                        methods=["DELETE"])
@swag_from("swags/delete.yaml")
def delete_api(docker_image_id):
    """
    API to delete the docker image

    Args:
        docker_image_id (string): UUID of the docker image
    """
    try:
        validate_delete(docker_image_id)
    # pylint: disable=broad-except
    except Exception as ex:
        return Response(ex.args[0], status=400)

    # parse data
    docker_image_id = str(docker_image_id)

    # delete docker image
    log.debug("Deleting docker image %s", docker_image_id)
    log.debug("audit_logging delete template : %s", docker_image_id)
    docker_image = DockerImage.query.get(docker_image_id)
    delete_docker_image(docker_image_id)

    # Audit logging only when project-id is present in request headers
    if 'X-Project-Id' in request.headers:
        audit_logging(
            console_url=app.config["CONSOLE_BACKEND_URL"],
            action_type="DELETE",
            object_id=docker_image_id,
            object_name=docker_image.as_dict().get("name"),
            object_type="TEMPLATE",
            object_json=json.dumps({"docker_image_id" : docker_image_id}),
            headers=request.headers,
        )
    # send response
    return Response(status=204)


@docker_image_api.route(
    "/v1/<uuid:docker_image_id>/fetch-schedule-commands",
    methods=["POST"])
@swag_from("swags/fetch-schedule-commands.yaml")
def fetch_schedule_commands(docker_image_id):
    """
    API to fetch the schedule commands for docker image

    Args:
        docker_image_id (UUID): UUID of the docker image
    """

    data = request.get_json()
    # parse input data
    docker_image_id = str(docker_image_id)

    # fetch docker image
    docker_image = read_docker_image(docker_image_id)

    # fetch schedule commands
    schedule_commands = fetch_commands_for_scheduling(docker_image, data)

    # send response
    return jsonify(schedule_commands)


@docker_image_api.route("/healthz", methods=["GET"])
def health_check():
    """ Health check method """
    return "Health Check"


@docker_image_api.route("/v1/template-resources", methods=["GET"])
@swag_from("swags/list_template_resources.yaml")
def list_template_resources():
    """
    API to list the docker images
    """
    # parse input data
    docker_images = list_all_template_resources()

    # send response
    return jsonify(docker_images)
