# -*- coding: utf-8 -*-
""" Decorator associated with the notebook module """
import logging
from flask import g
from .manager import (
    fetch_resource_info,
    get_subscriber_info,
    validate_subscriber_info
)
from .models import (
    Resource,
)

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")

def validate_subscriber(func):
    """
    function to fetch subscriber info from metering and validate subscriber
    Args:
        func:
    Returns:

    """
    def fetch_validate_subscriber(info):
        try:
            log.debug("Inside decorator wrapper fetch_validate_subscriber")
            log.debug("Subscription Resource Request")
            log.debug(info)
            log.debug("Get resource info")
            resource_id = info.data["resource_id"]
            log.debug(resource_id)
            resources = Resource.query.get(resource_id)
            log.debug(resources)
            log.debug("fetch resource info in required format")
            resource_key, resource_request = fetch_resource_info(resources.extra, resources.cpu)
            log.debug(resource_key)
            log.debug(resource_request)
            requested_usage = {resource_key: resource_request}
            log.debug(info.headers['X-Auth-Userid'])
            log.debug("call metering info to fetch subscriber info")
            subscriber_info = get_subscriber_info(info.headers['X-Auth-Userid'],
                                                  resource_key,
                                                  g.product_id)
            log.debug(subscriber_info)
            log.debug(requested_usage)
            log.debug("validate subscriber info")
            validate_subscriber_info(subscriber_info)
            log.debug(subscriber_info["subscriber_id"])
            subscriber_info["resource_key"] = resource_key
            subscriber_info["resource_request"] = resource_request
            log.debug("New subscriber info")
            log.debug(subscriber_info)
            log.debug("call original function")
            response = func(info, subscriber_info)
            log.debug("Response from fetch_validate_subscriber")
            log.debug(response)
            log.debug("Exiting wrapper function")
            return response
        # pylint: disable = broad-except
        except Exception as ex:
            log.exception(ex)
            raise
    log.debug("Exiting decorator function")
    return fetch_validate_subscriber

