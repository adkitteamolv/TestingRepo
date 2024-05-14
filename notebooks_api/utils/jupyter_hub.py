#! -*- coding: utf-8 -*-
"""jupyter hub module"""
import logging
from functools import wraps

import requests
from flask import current_app as app, g

from mosaic_utils.ai.headers.constants import Headers

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


def handle_anonymous_user(func):
    """Method to handle anonymous user"""
    @wraps(func)
    def wrapped(*args, **kwargs):
        """Handle users"""
        user_id = g.user["mosaicId"]
        hub_base_url = app.config["HUB_BASE_URL"]
        hub_auth_token = app.config["HUB_AUTH_TOKEN"]

        request_url = "{}/users/{}".format(hub_base_url, user_id)
        request_headers = {
            "Authorization": "Token {}".format(hub_auth_token),
            Headers.x_auth_username: g.user["first_name"],
            Headers.x_auth_email: g.user["email_address"],
            Headers.x_auth_userid: g.user["mosaicId"],
        }
        log.debug("Request to validating running container")
        response = requests.get(request_url, headers=request_headers)
        log.debug("Received response from spawner server=%s", response)

        if response.status_code == 404:
            log.debug("Request to spawner to create new container")
            requests.post(request_url, headers=request_headers)
            log.debug("Received response from spawner server for new container")

        return func(*args, **kwargs)

    return wrapped


def create_pod_name(project_id, user_id, notebook_id, notebook_type, spcs_data={}):
    """
    Method to create pod name

    :param project_id:
    :param user_id:
    :param notebook_id:
    :return:
    """
    if notebook_type == "jupyter":
        prefix = "jy"
    elif notebook_type == "custom-python":
        prefix = "cp"
    elif notebook_type == "rstudio":
        prefix = "rs"
    else:
        prefix = "nb"

    pod_name = "{}-{}-{}-{}".format(
        prefix,
        notebook_id,
        user_id,
        project_id
    )
    # take first 63 char from pod name, as k8 resource name can be upto 63
    pod_name = pod_name if len(pod_name) < 63 else pod_name[:63]

    # to remove spaces & special characters apart from '-' from job name,
    # keeps only alphanumeric values
    pod_name = "".join(e for e in pod_name if e == "-" or e.isalnum())
    # if pod_name ends with "-" remove that
    pod_name = pod_name[:-1] if pod_name[-1] == "-" else pod_name
    if spcs_data:
        pod_name = pod_name.replace("-", "_")
    log.debug(pod_name)

    return pod_name
