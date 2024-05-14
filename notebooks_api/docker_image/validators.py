#! -*- coding: utf-8 -*-

""" Validators associated with docker_image module """

import logging
import re
from jsonschema import validate

from notebooks_api.utils.tags import get_tag
from notebooks_api.notebook.models import TemplateStatus

from .constants import CUSTOM_BUILD, PRE_BUILD, PodStatus, InvalidNames, ConfigKeyNames
from .models import DockerImage, DockerImageTag
from flask import current_app as app

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.docker_image")


def get_proxy_details(macro : dict):
    """
    This function checks for the repo_type from config key 
    PROXY_ENABLED_GIT_PROVIDER and if the repo type is in this key then it will
    add the proxy details provided in the config
    """
    macro_details = {}
    if macro.get("repo_type", None) in app.config.get(ConfigKeyNames.PROXY_ENABLED_GIT_PROVIDER, []):
        macro_details.update({'proxy_details': app.config.get(ConfigKeyNames.PROXY_DETAILS)})
    return macro_details


def create(data, schema):
    """
    Validate data for docker image create operation

    Args:
         data (dict): request payload as dict
         schema (dict): schema definition as dict
    """

    # entry log
    log.debug("Entering create with data=%s schema=%s", data, schema)

    validate(data, schema)

    image_type = data.get("type", PRE_BUILD)
    docker_url = data.get("docker_url", None)
    base_image_id = data.get("base_image_id", None)
    git_macros_config = data.get("git_macros_config")
    if git_macros_config:
        for macro in git_macros_config:
            validate_output_dir_name(macro.get("output"))
            proxy_details = get_proxy_details(macro)
            if proxy_details:
                macro.update(proxy_details)

    if (image_type == PRE_BUILD) and (not docker_url):
        raise ValueError("docker_url is required")

    if (image_type == CUSTOM_BUILD) and (not base_image_id):
        raise ValueError("base_image_id is required")

    check_for_duplicate(data.get("name"), None, data.get("tags"), False)


    # exit log
    log.debug("Exiting create")


def check_for_duplicate(docker_image_name, docker_image_id, tags, update):
    """
    Validates if docker template with same name exist in the same project

    Args:
        docker_image_name (string): name of the new docker image
        tags (list): list of the tags associated with docker image
    """

    # entry log
    log.debug(
        "Entering check_for_duplicate with docker_image_name=%s tags=%s",
        docker_image_name,
        tags
    )
    if not tags:
        tags = []

    project_tag = get_tag('project', tags, False)
    result_set = DockerImage.query.filter(DockerImage.name == docker_image_name)\
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id)\
        .filter((DockerImageTag.tag == project_tag) | (DockerImageTag.tag == "default=true"))\
        .first()

    if result_set is not None and update:
        if result_set.id == docker_image_id:
            return
    if result_set is not None:
        log.error(
            "Template with name=%s already exist in project=%s",
            docker_image_name,
            project_tag
        )
        raise ValueError("Template with same name already exist")

    # exit log
    log.debug("Exiting check_for_duplicate")


def validate_output_dir_name(output: str):
    """
    Raise Exception if output name is invalid
    :param output:
    :return: None
    """
    if output in InvalidNames.LINUX_DIRECTORIES:
        raise ValueError(f"The macro output_name - {output} is restricted."
                         f" Restricted Names - {InvalidNames.LINUX_DIRECTORIES}")

    if isinstance(output, str) and not re.match("[A-Za-z0-9_-]*$", output):
        raise ValueError("The macro output_name must only contain alphanumeric characters,"
                         " underscores and dashes")


def validate_update(data, schema):
    """
    Validate data for docker image update operation

    Args:
         data (dict): request payload as dict
         schema (dict): schema definition as dict
    """

    # entry log
    log.debug("Entering update with data=%s schema=%s", data, schema)

    validate(data, schema)

    image_type = data.get("type", PRE_BUILD)
    docker_url = data.get("docker_url", None)
    base_image_id = data.get("base_image_id", None)

    git_macros_config = data.get("git_macros_config")
    if git_macros_config:
        for macro in git_macros_config:
            validate_output_dir_name(macro.get("output"))
            proxy_details = get_proxy_details(macro)
            if proxy_details:
                macro.update(proxy_details)

    if (image_type == PRE_BUILD) and (not docker_url):
        raise ValueError("docker_url is required")

    if (image_type == CUSTOM_BUILD) and (not base_image_id):
        raise ValueError("base_image_id is required")

    # exit log
    log.debug("Exiting update")


def validate_delete(docker_image_id):
    """
    Validate data for docker image delete operation
    Will check if docker image is being used by notebooks

    Args:
         docker_image_id: docker base image id (template used)
    """
    log.debug(
        "Entering validate delete with docker_image_id=%s",
        docker_image_id)

    query_set = TemplateStatus.query.filter(TemplateStatus.template_id == docker_image_id) \
        .filter(TemplateStatus.status.in_([PodStatus.STARTING, PodStatus.RUNNING]))

    # check if not empty,raise exception
    if query_set.count() != 0:
        # pylint: disable=line-too-long
        raise ValueError(
            "The template is in running. Please stop the template first")

    # exit log
    log.debug("Exiting Validate delete")
