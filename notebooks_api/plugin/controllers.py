#! -*- coding: utf-8 -*-
""" Controllers associated with the plugin module """
# pylint: disable=unused-import
import logging
import re
from flasgger import swag_from
from flask import Response, jsonify, request, g

from mosaic_utils.ai.k8.utils import create_job_name
from notebooks_api.utils.exceptions import ErrorCodes
from notebooks_api.utils.data import clean_data
from . import plugins_api
from .job import ExecutePlugin
from .manager import (
    register_plugin,
    get_plugin_input_data,
    switch_plugin_status,
    update_plugin_data,
    delete_plugin,
    get_plugin_list,
    save_plugin_data,
    data_upload_file,
    get_plugin_data_using_cpi,
    update_job_status
)
from .exceptions import ErrorCodes
from .constants import ENABLED, DISABLED
from ..utils.exceptions import MosaicException, PluginException

log = logging.getLogger("notebooks_api")


@plugins_api.route("/v1/plugin", methods=["POST"])
@swag_from("swags/add_plugin.yaml")
def create_plugin():
    """
    API to create a new plugin
    Args:
        base_image_type
        category
        color
        description
        execution_command
        height
        icon
        input_form_type
        input_parameter_file_name
        input_parameter_json
        multiInputNode
        name
        nodeBackgroundColor
        plugin_code_source
        status
        thumbnail
        type
        valid_sections
        width
    """
    # parse and clean input data
    data = request.get_json()
    data = clean_data(data)
    log.info(f"Inside create_plugin\nrequest_json: {data}")
    log.debug(f"request args: {request.args}")

    if data['name'] == "":
        return ErrorCodes.ERROR_0005, 500
    pattern = r"[\W]"
    match = re.search(pattern, data['name']) \
            or data['name'].startswith("_") \
            or data['name'].endswith("_")
    if match:
        return ErrorCodes.ERROR_0006, 500

    result = register_plugin(data)
    log.info(f"Response from create_plugin: {result}")
    return jsonify(result), 201

import uuid

def is_valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

@plugins_api.route("/v1/plugin_data", methods=["POST"])
@swag_from("swags/get_plugin_data.yaml")
def get_plugin_info():
    """
    API to get the plugin info
    Args:
        plugin_filters
    """
    try:
        data = request.get_json()

        log.info(f"Inside get_plugin_info\nrequest_json: {data}")

        if data != {} and 'plugin_id' not in data:
            return ErrorCodes.ERROR_0002, 500

        if not is_valid_uuid(data['plugin_id']):
            raise PluginException(msg_code="PLUGIN_ID_ERROR_0001")

        if not set(list(data.keys())).issubset(['plugin_id', 'name', 'project_id', 'model_id',
                                                'version_id', 'workflow_id', 'section']):
            return ErrorCodes.ERROR_0011, 500

        result = get_plugin_input_data(data)

        log.info(f"Response from get_plugin_info: {result}")
        return jsonify(result), 200
    except MosaicException as ex:
        log.exception(ex)
        return jsonify(ex.message_dict()), ex.code



@plugins_api.route("/v1/get_plugin_data/custom_plugin_id/<string:custom_plugin_id>/plugin_id/<string:plugin_id>", methods=["GET"])
@swag_from("swags/get_plugin_data_using_custom_plugin_id.yaml")
def get_plugin_data(custom_plugin_id, plugin_id):
    """
    API to get the plugin info using custom plugin id
    Args:
        custom_plugin_id
        plugin_id
    """
    try:
        log.info(f"Inside get_plugin_data\ncustom_plugin_id: {custom_plugin_id}\nplugin_id: {plugin_id}")

        result = get_plugin_data_using_cpi(custom_plugin_id, plugin_id)

        log.info(f"Response from get_plugin_data_using_cpi: {result}")
        return jsonify(result), 200
    except MosaicException as me:
        return jsonify(me.message_dict()), me.code


@plugins_api.route("/v1/switch_plugin_status", methods=["PUT"])
@swag_from("swags/plugin_status.yaml")
def plugin_status():
    """
    API to swith plugin status
    Args:
        id
        status
    """
    # parse and clean input data
    data = request.get_json()
    data = clean_data(data)
    log.info(f"Inside plugin_status\nrequest_json: {data}")
    log.debug(f"request args: {request.args}")

    if data['status'] not in [ENABLED, DISABLED]:
        return ErrorCodes.ERROR_0001, 500
    if "id" not in data:
        return ErrorCodes.ERROR_0002, 500

    result = switch_plugin_status(data)
    log.info(f"Response from plugin_status: {plugin_status}")
    return jsonify(result), 200


@plugins_api.route("/v1/update_plugin_data", methods=["PUT"])
@swag_from("swags/update_plugin.yaml")
def update_plugin():
    """
    API to update the plugin data
    Args:
        id
        base_image_type
        category
        color
        description
        execution_command
        height
        icon
        input_form_type
        input_parameter_file_name
        input_parameter_json
        multiInputNode
        name
        nodeBackgroundColor
        plugin_code_source
        status
        thumbnail
        type
        valid_sections
        width
    """
    # parse and clean input data
    data = request.get_json()
    data = clean_data(data)
    log.info(f"Inside update_plugin\nrequest_json: {data}")
    log.debug(f"request args: {request.args}")

    if "id" not in data:
        return ErrorCodes.ERROR_0002, 500

    result = update_plugin_data(data)
    log.info(f"Response from update_plugin: {result}")

    return jsonify(result), 201


@plugins_api.route("/v1/delete_plugin", methods=["DELETE"])
@swag_from("swags/delete_plugin.yaml")
def delete_custom_plugin():
    """
    API to delete a plugin
    Args:
        id
    """
    # parse and clean input data
    data = request.get_json()
    data = clean_data(data)
    log.info(f"Inside delete_custom_plugin\nrequest_json: {data}")
    log.debug(f"request args: {request.args}")

    if "id" not in data:
        return ErrorCodes.ERROR_0002, 500

    result = delete_plugin(data)

    log.info(f"Response from delete_custom_plugin: {result}")
    return jsonify(result), 202


@plugins_api.route("/v1/plugin_data_list/<string:section>", methods=["GET"])
@swag_from("swags/plugin_data_list.yaml")
def get_plugin_list_data(section):
    """
    API to get the list of plugins
    Args:
        section
    """
    log.info(f"Inside get_plugin_list_data\nrequest_json: {section}")
    log.debug(f"request args: {request.args}")
    result = get_plugin_list(section)

    log.info(f"Response from get_plugin_list_data: {result}")
    return jsonify(result), 200


@plugins_api.route("/v1/save_plugin_data", methods=["POST"])
@swag_from("swags/save_plugin_data.yaml")
def save_plugin_data_user():
    """
    API to get the list of plugins
    Args:
        advanceSettings
    """
    # parse and clean input data
    data = request.get_json()
    log.info(f"Inside save_plugin_data_user\nrequest_json: {data}")
    log.debug(f"request args: {request.args}")

    result = save_plugin_data(data)

    log.info(f"Response from save_plugin_data_user: {result}")

    return jsonify(result), 201


@plugins_api.route("/v1/execute-plugin", methods=["POST"])
@swag_from("swags/execute_plugin_jobs.yaml")
def execute_plugin():
    """
      API to execute plugin
      return:
        jobName
        applicationName
        message
    """
    try:
        request_json = request.get_json()
        log.info(f"Inside execute-plugin\nrequest_json: {request_json}")
        log.debug(f"request args: {request.args}")
        job_name = create_job_name(request_json['name'], request_json.get('instance_id', None))
        request_json["job_name"] = job_name
        # async_execute_plugin(g.user, g.product_id, request_json)
        # response = {
        #     "jobName": job_name,
        #     "applicationName": None,
        #     "message": "Success"
        # }
        execute_plugin = ExecutePlugin(g.user, request_json)
        response = execute_plugin.execute_plugin()
        log.info(f"Response from execute_plugin: {response}")
        return jsonify(response), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        update_job_status(request_json['instance_id'], g.user)
        return ErrorCodes.ERROR_0002, 500


@plugins_api.route("/v1/update_recipe", methods=["POST"])
@swag_from("swags/update_recipe.yaml")
def upload_and_unzip_file():
    """
    API to update plugin recipe code
    Args:
        destination_path
        zip_file
    """

    destination_path = request.args.get("destination_path")
    file = request.files['zip_file']
    log.debug(f"Destination Path: {destination_path}, filename: {file.filename}")

    if not destination_path or destination_path == "":
        return ErrorCodes.ERROR_0009, 500
    if not file.filename.endswith(".zip"):
        return ErrorCodes.ERROR_0010, 500

    result = data_upload_file(destination_path, file)

    return jsonify(result), 200
