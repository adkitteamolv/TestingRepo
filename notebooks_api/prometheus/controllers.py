#! -*- coding: utf-8 -*-

""" Controllers associated with the prometheus module """

import logging

from flasgger import swag_from
from flask import Response
from prometheus_client import generate_latest

from . import prometheus_api


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


@prometheus_api.route("/metrics", methods=["GET"])
@swag_from("swags/metrics.yaml")
def metrics():
    """ API to retrieve utilisation metrics for prometheus """
    content = generate_latest()
    return Response(content)
