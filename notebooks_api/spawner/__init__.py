# -*- coding: utf-8 -*-
# pylint: disable=no-member
"""Spawner module."""
from flask import Blueprint

# pylint: disable=invalid-name
scheduler_api = Blueprint("scheduler", __name__)

# pylint: disable=wrong-import-position
from . import controllers

"""old codes"""
# import os
# import logging
# import sys
# from logging.handlers import RotatingFileHandler
# import requests
#
# from flask import Flask, redirect, Response, g, request, Blueprint, make_response
# from flasgger import Swagger
#
# from mosaic_utils.ai.headers.constants import Headers
# from mosaic_utils.ai.headers.utils import check_project_access, generate_headers
# from .logfilter import ParameterFilter
#
# # pylint: disable=invalid-name
# app = Flask(__name__)
#
# # initialize settings
# base_path = os.path.dirname(os.path.realpath(__file__))
# default = os.path.join(base_path, "configs", "local.cfg")
# config_file = os.getenv("MOSAIC_KUBESPAWNER_SETTINGS", default)
# app.config.from_pyfile(config_file)
#
#
# # define swagger
# swagger_template = {
#     "swagger": "2.0",
#     "info": {
#         "title": "Mosaic KubeSpawner",
#         "description": "REST API's for interacting with scheduler",
#         "contact": {
#             "responsibleOrganization": "Mosaic",
#             "responsibleDeveloper": "Ratan Boddu",
#             "email": "ratan.boddu@lntinfotech.com",
#         },
#         "version": "1.0.0",
#     },
# }
#
# swagger_config = {
#     "headers": [],
#     "specs": [
#         {
#             "endpoint": "specifications",
#             "route": "{}/docs/specifications.json".format(app.config["URL_PREFIX"]),
#             "rule_filter": lambda rule: True,
#             "model_filter": lambda tag: True,
#         }
#     ],
#     "static_url_path": "{}/flasgger_static".format(app.config["URL_PREFIX"]),
#     "swagger_ui": True,
#     "specs_route": "{}/docs".format(app.config["URL_PREFIX"]),
# }
#
# Swagger(app, config=swagger_config, template=swagger_template)
#
# # registering application blueprint
# scheduler_api = Blueprint("scheduler", __name__)
# url_prefix = app.config["URL_PREFIX"]
#
# # pylint: disable=wrong-import-position
# from . import controllers
#
#
# @scheduler_api.route("/")
# def home():
#     """ By default redirect users to swagger """
#     redirect_url = "{}/docs".format(app.config["URL_PREFIX"])
#     return redirect(redirect_url)
#
#
# # pylint: disable=inconsistent-return-statements
# @scheduler_api.before_request
# def authentication():
#     """ Authentication middleware """
#     if request.path in (
#             '/scheduler/api/v1/create_k8_resources_byoc',
#             '/scheduler/api/v1/execute-notebook'
#         ):
#         app.logger.debug('Body: %s', {x: (request.get_json()[x] if x not in ('enabled_repo') \
#             else {y: (request.get_json()['enabled_repo'][y]) if y not in ('password') else '*****' \
#             for y in request.get_json()['enabled_repo']}) for x in request.get_json()})
#     else:
#         if request.method == "POST" or request.method == "PUT":
#             app.logger.debug('Body: %s', request.get_json())
#
#     if app.config["TESTING"]:
#         # pylint: disable=assigning-non-slot
#         g.user = {
#             "mosaicId": "0123456789",
#             "email_address": "test_user@lntinfotech.com",
#             "first_name": "Test",
#             "last_name": "User",
#             "user_roles": "default",
#             "project_id" : "1"
#         }
#         return
#
#     # skip auth
#     if skip_authentication():
#         return
#
#     # authenticate all incoming requests
#     # pylint: disable=assigning-non-slot
#     if all([Headers.x_auth_email in request.headers,
#             Headers.x_auth_userid in request.headers,
#             Headers.x_auth_username in request.headers]):
#         g.user = {
#             "mosaicId": request.headers[Headers.x_auth_userid],
#             "email_address": request.headers[Headers.x_auth_email],
#             "first_name": request.headers[Headers.x_auth_username],
#             "url": request.url
#         }
#         if request.is_json:
#             g.user["json_data"] = request.get_json(silent=True) or {}
#         return
#
#         # raise exception
#     return Response("Please login to continue", status=401)
#
#
# @scheduler_api.before_request
# def authorization():
#     """ Check user privileges """
#     project_ids = app.config.get('PROJECT_LIST', [])
#     # skip in case of test cases
#     if app.config["TESTING"]:
#         return
#     # skip auth
#     if skip_authentication():
#         return
#
#     if Headers.x_project_id in request.headers:
#         g.user["project_id"] = request.headers[Headers.x_project_id]
#
#         if "automl_check" in request.headers:
#             return
#
#         if g.user["project_id"] and g.user["project_id"] in project_ids:
#             return
#
#         if g.user["project_id"]:
#             if skip_authentication_create_k8:
#                 if 'access' in request.headers:
#                     return
#                 else:
#                     return check_project_access(
#                         app.config["CONSOLE_BACKEND_URL"],
#                         g.user["mosaicId"],
#                         g.user["email_address"],
#                         g.user["first_name"],
#                         g.user["project_id"],
#                     )
#
#     return Response("Access denied", status=403)
#
#
# def skip_authentication():
#     """Method to skip authentication"""
#     skip_auth = app.config["SKIP_AUTH"]
#     url = request.url
#     if [auth_url for auth_url in skip_auth if auth_url in url]:
#         return True
#
#
# def skip_authentication_create_k8():
#     """Method to skip authentication"""
#     skip_auth = "/create_k8_resources_byoc"
#     url = request.url
#     if skip_auth in url:
#         return True
#
# app.register_blueprint(scheduler_api, url_prefix=url_prefix)
#
#
# # setting the application logging mechanism
# parameter_filter = ParameterFilter()
# formatter = logging.Formatter(app.config.get('LOG_FORMAT'))
# file_handler = RotatingFileHandler(app.config.get('LOG_FILE_NAME'),
#                                    maxBytes=app.config.get('MAX_SIZE_OF_LOG_FILE'),
#                                    backupCount=app.config.get('KEEP_LOG_DURATION_DAYS'))
# file_handler.setFormatter(formatter)
#
# stream_handler = logging.StreamHandler(sys.stdout)
# stream_handler.setFormatter(formatter)
#
# # define logger
# app.logger.addHandler(file_handler)
# app.logger.addHandler(stream_handler)
# app.logger.addFilter(parameter_filter)
# app.logger.setLevel(app.config.get('LOG_LEVEL'))
