#! -*- coding: utf-8 -*-
""" Factories for the application """
import os
import sys
import json
import logging

from logging.handlers import RotatingFileHandler
import requests
from requests.exceptions import ConnectionError
from celery import Celery
from flasgger import Swagger
from flask import Flask, g, redirect, request
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from mosaic_utils.ai.headers.utils import generate_headers
from mosaic_utils.ai.headers.constants import Headers
from notebooks_api.utils.exceptions import ErrorCodes, ServiceConnectionError
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


from .data_files.manager import decode_jwt
from .constants import KeycloakRoles
from .logfilter import ParameterFilter
from .exceptions import AuthorizationError, AuthenticationError


# pylint: disable=invalid-name
metrics = None
app = None

# pylint: disable=too-many-locals,too-many-statements
def create_app(metrics_flag=False):
    """ flask app factory """
    # pylint: disable=invalid-name,global-statement
    global metrics

    # define app
    # pylint: disable=redefined-outer-name
    app = Flask(__name__)

    # initialize settings
    base_path = os.path.dirname(os.path.realpath(__file__))
    default = os.path.join(base_path, "configs", "test.cfg")
    config_file = os.getenv("NOTEBOOKS_API_SETTINGS", default)
    app.config.from_pyfile(config_file)


    # register prometheous metrics
    if metrics_flag:
        api_url_prefix = app.config["URL_PREFIX"]
        api_url_prefix = api_url_prefix + '/metrics'

    parameter_filter = ParameterFilter()
    formatter = logging.Formatter(app.config["LOG_FORMAT"])
    logger = logging.getLogger("notebooks_api")

    notebooks_log_file = os.path.join(
        app.config["LOG_DIR"],
        "notebooks_api.notebook.log")
    file_handler = RotatingFileHandler(notebooks_log_file)
    file_handler.setFormatter(formatter)
    logger.setLevel(app.config["LOG_LEVEL"])
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)

    logger.addFilter(parameter_filter)

    # # initialize flask logger
    # flask_log_file = os.path.join(app.config["LOG_DIR"], "flask.app.log")
    # flask_log_handler = RotatingFileHandler(
    #     flask_log_file,
    #     maxBytes=app.config["LOG_MAX_BYTES"],
    #     backupCount=app.config["LOG_BACKUP_COUNT"]
    # )
    # flask_log_handler.setLevel(app.config["LOG_LEVEL"])
    # app.logger.addHandler(flask_log_handler)
    # app.logger.addHandler(stream_handler)

    # initialize notebooks_api logger

    # import blue prints
    # pylint: disable=import-outside-toplevel
    from .pypi import pypi_api
    from .docker_image import docker_image_api
    from .notebook import notebook_api
    from .project import project_api
    from .prometheus import prometheus_api
    from .resource import resource_api
    from .data_files import data_files_api
    from .notebook.user_impersonation import user_impersonation_api
    from .plugin import plugins_api
    from .spawner import scheduler_api
    from .version_control import version_control_api

    # register blue prints
    url_prefix = app.config["URL_PREFIX"]
    app.register_blueprint(pypi_api, url_prefix=url_prefix)
    app.register_blueprint(resource_api, url_prefix=url_prefix)
    app.register_blueprint(notebook_api, url_prefix=url_prefix)
    app.register_blueprint(docker_image_api, url_prefix=url_prefix)
    app.register_blueprint(project_api, url_prefix=url_prefix)
    app.register_blueprint(prometheus_api, url_prefix=url_prefix)
    app.register_blueprint(data_files_api, url_prefix=url_prefix)
    app.register_blueprint(user_impersonation_api, url_prefix=url_prefix)
    app.register_blueprint(plugins_api, url_prefix=url_prefix)
    app.register_blueprint(scheduler_api, url_prefix=url_prefix)
    app.register_blueprint(version_control_api, url_prefix=url_prefix)

    # import models
    from .docker_image.models import db as docker_image_db
    from .notebook.models import db as notebook_db
    from .resource.models import db as resource_db
    from .pypi.models import db as pypi_db
    from .plugin.models import db as plugin_db
    from .version_control.models import db as version_control_db

    # initialize models
    resource_db.init_app(app)
    notebook_db.init_app(app)
    docker_image_db.init_app(app)
    pypi_db.init_app(app)
    plugin_db.init_app(app)
    version_control_db.init_app(app)

    # pylint: disable=invalid-name
    db = SQLAlchemy(app)
    Migrate(app, db)

    # Configure OpenTelemetry
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()

    # define swagger
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Notebooks Backend",
            "description": "REST API's for interacting with notebooks",
            "contact": {
                "responsibleOrganization": "L&T Infotech",
                "responsibleDeveloper": "Akhil Lawrence",
                "email": "akhil.lawrence@lntinfotech.com",
                "url": "www.lntinfotech.com",
            },
            "version": "1.0.0"
        }
    }

    swagger_config = {
        "headers": [
        ],
        "specs": [
            {
                "endpoint": 'specifications',
                "route": '{}/docs/specifications.json'.format(app.config["URL_PREFIX"]),
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "{}/flasgger_static".format(app.config["URL_PREFIX"]),
        "swagger_ui": True,
        "specs_route": "{}/docs".format(app.config["URL_PREFIX"]),
    }

    Swagger(app, config=swagger_config, template=swagger_template)

    def authentication():
        """ Authentication middleware """
        # authenticate all incoming requests
        if all(
                [
                    Headers.x_auth_email in request.headers,
                    Headers.x_auth_userid in request.headers,
                    Headers.x_auth_username in request.headers,
                ]
        ):
            # pylint: disable=assigning-non-slot
            g.user = {
                "mosaicId": request.headers[Headers.x_auth_userid],
                "email_address": request.headers[Headers.x_auth_email],
                "first_name": request.headers[Headers.x_auth_username],
                "url": request.url
            }
            return

        # authenticate requests from mosaic-connector / mosaic-ai-client
        if Headers.authorization in request.headers:
            _, jwt = request.headers[Headers.authorization].split()
            userinfo = decode_jwt(jwt)
            # pylint: disable=assigning-non-slot
            g.user = {
                "mosaicId": userinfo["userid"],
                "email_address": userinfo["useremail"],
                "first_name": userinfo["username"],
            }
            return

        # raise exception
        raise AuthenticationError

    def authorization():
        """ Check user privileges """
        project_ids = app.config.get('PROJECT_LIST', [])
        logger.debug("PROJECT_LIST")
        logger.debug(project_ids)
        skip_project_auth = app.config["SKIP_PROJECT_AUTH"]
        url = request.url
        # authorize all incoming requests
        if Headers.x_project_id in request.headers:
            g.user['project_id'] = request.headers[Headers.x_project_id]
            g.user['realm_name'] = request.headers.get(Headers.x_auth_realm_name)
            if g.user['project_id'] not in project_ids:
                logger.debug("Inside project access check")
                logger.debug(g.user['project_id'])
                response, status = check_project_level_access(
                    app.config["CONSOLE_BACKEND_URL"],
                    g.user['mosaicId'],
                    g.user['email_address'],
                    g.user['first_name'],
                    g.user['project_id']
                )
                if status == 200 and response is not None:
                    logger.debug("Project Access Type : %s", response)
                    g.user["project_access_type"] = \
                        response["accessType"] if response else None
            return
        if [auth_url for auth_url in skip_project_auth if auth_url in url]:
            return
        raise AuthorizationError

    def product_middleware():
        """Middleware for product identification"""
        if Headers.x_product_id in request.headers:
            g.product_id = request.headers[Headers.x_product_id]
        else:
            g.product_id = None

    def get_keycloak_roles(username, realm_name=None):
        headers = {Headers.x_auth_username: username}
        if realm_name:
            user_management = app.config['MULTI_TENANT_USER_MANAGEMENT_URL']
            user_management_url = f"{user_management}/tenants/role/getUserRoles"
            headers[Headers.x_auth_realm_name] = realm_name
        else:
            user_management = app.config['USER_MANAGEMENT_URL']
            user_management_url = f"{user_management}/role/getUserRoles"
        response = requests.get(user_management_url, headers=headers)
        return response

    def keycloak_auth(base_url, username, method, realm_name=None):
        """

        Args:
            base_url: url prefix from config
            username: identify user by username
            method: HTTP method type of request
            realm_name: Real Name where user belongs
        Returns:

        """
        user_roles = get_keycloak_roles(username, realm_name)
        if user_roles.status_code == 200:
            for roles in user_roles.json():
                if base_url in roles['actions'].keys() and \
                        method == "GET" and \
                        KeycloakRoles.view in roles['actions'][base_url]:
                    return
                if base_url in roles['actions'].keys() and \
                        KeycloakRoles.modify in roles['actions'][base_url]:
                    return
        raise AuthorizationError


    # pylint: disable=unused-variable
    @app.before_request
    def skip_authentication():

        skip_auth = app.config['SKIP_AUTH']
        url = request.url
        if app.config["TESTING"]:
            # pylint: disable=assigning-non-slot
            g.user = {
                "mosaicId": "0123456789",
                "email_address": "test_user@lntinfotech.com",
                "first_name": "Test",
                "last_name": "User",
                "user_roles": "default",
                "project_id": "1",
                "project_access_type": "OWNER"
            }
            g.product_id = "MOSAIC_AI"
            return
        if [auth_url for auth_url in skip_auth if auth_url in url]:
            return
        if not app.config["TESTING"]:
            authentication()
            authorization()
            product_middleware()

    # @app.before_request
    # def validate_license():
    #     """ Validate service license """
    #     # skip in case of test cases
    #     if app.config["TESTING"]:
    #         return
    #
    #     # entry log
    #     notebooks_logger.debug("Reading host id")
    #     host_id = '-'.join(re.findall('..', '%012x' % uuid.getnode()))
    #     notebooks_logger.debug(host_id)
    #     service_id = app.config["SERVICE_ID"]
    #     notebooks_logger.debug("Reading service id")
    #     notebooks_logger.debug(service_id)
    #
    #     validate_license_service_url = app.config["VALIDATE_LICENSE_BASE_URL"] +\
    #                                    "license-service/secured/api/v1/license" \
    #                                    "/validateLicenseForService/licenseServiceId={}" \
    #                                    "/licenseHostId={}".format(service_id, host_id)
    #     response = requests.get(validate_license_service_url, proxies={'http':'','https':''})
    #     if response.status_code == 200:
    #         notebooks_logger.debug("License is valid for this service")
    #         return
    #     else:
    #         notebooks_logger.debug("License is invalid for this service.. Permission denied")
    #         return Response(ErrorCodes.MOSAIC_0006, status=403)

    # pylint: disable=unused-variable
    @app.route("/")
    def home():
        """ By default redirect users to swagger """
        redirect_url = "{}/docs".format(url_prefix)
        return redirect(redirect_url)

    # pylint: disable=unused-argument
    def page_not_found(e):
        """ 404 handler """
        return ErrorCodes.ERROR_0001, 404

    # pylint: disable=unused-argument
    def internal_server_error(e):
        """ 500 handler """
        return ErrorCodes.ERROR_0002, 500

    def authentication_error(e):
        """
        Handler for authentication error

        Args:
            error (Exception): exception object

        Returns:
            Response
        """
        return ErrorCodes.MOSAIC_0004, 401

    def authorization_error(e):
        """
        Handler for authorization error

        Args:
            error (Exception): exception object

        Returns:
            Response
        """
        return ErrorCodes.MOSAIC_0005, 403

    app.register_error_handler(AuthenticationError, authentication_error)
    app.register_error_handler(AuthorizationError, authorization_error)
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_server_error)
    return app


def get_application():
    """
    Get application method

    Returns:
        app
    """
    # pylint: disable=invalid-name,global-statement
    global app
    if app is None:
        app = create_app(True)
        return app
    return app


def get_config():
    """ get config method """
    appl = get_application()
    base_path = os.path.dirname(os.path.realpath(__file__))
    default = os.path.join(base_path, "configs", "test.cfg")
    config = appl.config
    appl.config.from_envvar('NOTEBOOKS_API_SETTINGS', default)
    return config


# pylint: disable=redefined-outer-name
def make_celery(app=None):
    """ celery app factory """
    app_config = get_config()
    app = get_application()

    celery = Celery(
        app.import_name,
        broker=app_config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    TaskBase = celery.Task

    # pylint: disable=too-few-public-methods
    class ContextTask(TaskBase):
        """Celery task method"""
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


def get_db_type():
    """Method to get db type"""
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    db_type = url.split("+")[0]
    return db_type


def check_project_level_access(console_url, userid, email, username, project_id):
    """Method that checks project level accesses and gets the access type in return"""
    try:
        headers = generate_headers(userid, email, username, project_id)
        project_access_url = f"{console_url}/secured/api/project/v1/access"
        response = requests.get(project_access_url, headers=headers)
        if response.status_code == 200:
            return response.json(), 200
        raise ValueError("Access denied")
    except ConnectionError as ex:
        raise ServiceConnectionError(msg_code="SERVICE_CONNECTION_ERROR_001")
    except Exception as ex:
        raise ex

