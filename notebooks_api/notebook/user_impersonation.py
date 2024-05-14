#! -*- coding: utf-8 -*-
"""User impersonation APIs"""

import logging
from flask import Blueprint, jsonify, request, Response
from flasgger import swag_from
import sqlalchemy.exc

from notebooks_api.utils.exceptions import ErrorCodes
from notebooks_api.notebook.manager import (get_ad_user_info,
                                            add_user_group_details,
                                            delete_user_group_details,
                                            update_user_group_mappings,
                                            update_user_details,
                                            update_group_details)


# pylint: disable=invalid-name
user_impersonation_api = Blueprint("user_impersoantion", __name__)

log = logging.getLogger("notebooks_api.user_impersonation")


@user_impersonation_api.route("/v2/user-impersonation/user-group-details", methods=["GET"])
@user_impersonation_api.route("/v2/user-impersonation/user-group-details/<string:mosaic_user_id>",
                              methods=["GET"])
@swag_from("swags/get_ad_user_details.yaml")
def fetch_ad_user_details(mosaic_user_id=None):
    """
    Fetch user related details from ad user impersonation tables
    Args:
        mosaic_user_id: mosaic user id if need details of a specific user

    Returns:
        json with user group details
    """
    try:
        user_info = get_ad_user_info(mosaic_user_id)
        return jsonify(user_info)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@user_impersonation_api.route("/v2/user-impersonation/user-group-details", methods=["POST"])
@swag_from("swags/add_ad_user_details.yaml")
def add_ad_user_details():
    """
    Add user group details for a user in user impersonation tables
    Returns:
    """
    try:
        payload = request.get_json()
        response = add_user_group_details(payload)
        return Response(response, status=201)
    except sqlalchemy.exc.IntegrityError:
        return ErrorCodes.ERROR_0012, 500
    except Exception as ex: # pylint: disable=broad-except
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@user_impersonation_api.route("/v2/user-impersonation/user-group-details", methods=["delete"])
@swag_from("swags/delete_ad_user_groups.yaml")
def delete_ad_user_details():
    """
    Add user group details for a user in user impersonation tables
    Returns:

    """
    try:
        payload = request.get_json()
        response = delete_user_group_details(payload)
        return Response(response, status=204)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@user_impersonation_api.route("/v2/user-impersonation/user-group-mapping", methods=["PUT"])
@swag_from("swags/update_ad_user_group_mapping.yaml")
def update_ad_user_mappings():
    """
    Update user group details for a user in user impersonation tables
    Returns:

    """
    try:
        payload = request.get_json()
        response, status_code = update_user_group_mappings(payload)
        return Response(response, status=status_code)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@user_impersonation_api.route("/v2/user-impersonation/user-detail/<string:user_id>",
                              methods=["PUT"])
@swag_from("swags/update_ad_user_details.yaml", validation=True, schema_id="update_user")
def update_ad_user_details(user_id):
    """
    Update details of a user in user impersonation tables
    Returns:

    """
    try:
        payload = request.get_json()
        response, status_code = update_user_details(payload, user_id)
        return Response(response, status=status_code)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@user_impersonation_api.route("/v2/user-impersonation/group-detail/<string:group_id>",
                              methods=["PUT"])
@swag_from("swags/update_ad_group_details.yaml", validation=True, schema_id="update_group")
def update_ad_group_details(group_id):
    """
    Update details of a group in user impersonation tables
    Returns:

    """
    try:
        payload = request.get_json()
        response, status_code = update_group_details(payload, group_id)
        return Response(response, status=status_code)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500
