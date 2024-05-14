#! -*- coding: utf-8 -*-

""" Controllers associated with the project module """

from datetime import datetime

import logging
import requests

from flasgger import swag_from
from flask import Response, current_app as app, jsonify, request, g
from mosaic_utils.ai.headers.utils import generate_headers

from notebooks_api.notebook.manager import (
    fetch_activity_of_project,
    fetch_notebooks,
    fetch_notebooks_count_for_projects,
)
from notebooks_api.version_control.views import View
from notebooks_api.utils.project import create_repo_name, rename_repo
from notebooks_api.version_control.views import View

from . import project_api


# pylint: disable=invalid-name
# log = logging.getLogger("notebooks_api")


@project_api.route("/v1/project/<string:project_name>/<string:project_id>",
                   methods=["POST"])
@swag_from("swags/create.yaml")
def create_new_repo_for_project(project_name, project_id):
    """ Create new repo method"""

    # entry log to add project id to log hander
    #app.logger.add_attr({Constants.PROJECT_ID_KEY: str(project_id)})

    # git_server_url = app.config["VCS_BASE_URL"]

    print("inside repo creation")
    app.logger.debug("inside repo creation")
    app.logger.error("inside repo creation")

    app.logger.error(g.user)
    app.logger.debug(g.user)
    print(g.user)

    # create repo
    repo_name = create_repo_name(project_name, project_id)
    # request_url = "{}/repo/{}".format(git_server_url, repo_name)
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"]
    # )

    # print(headers)
    # app.logger.debug(headers)
    # app.logger.error(headers)
    # response = requests.post(request_url, headers=headers)
    try:
        response = View(project_id=g.user["project_id"]).create_repo(repo=repo_name)
    except Exception as ex:
        print("ex is ", ex)
        return Response(status=400)
    # response.raise_for_status()

    # exit log
    app.logger.debug("Exiting create_new_repo_for_project")

    return Response(status=200)


# pylint: disable=line-too-long
@project_api.route(
    "/v1/project/<string:project_name>/<string:project_id>/<string:new_project_name>",
    methods=["GET"])
@swag_from("swags/rename.yaml")
def rename_repo_for_project(project_name, new_project_name, project_id):
    """ Rename repo method"""
    # entry log to add project id to log hander
    # app.logger.add_attr({Constants.PROJECT_ID_KEY: str(project_id)})

    git_server_url = app.config["VCS_BASE_URL"]

    # rename repo
    # repo_name = rename_repo(project_name, new_project_name, project_id)
    # repo_name = repo_name.replace(" ", "/")
    View(project_id=project_id).rename_repo(project_name, new_project_name, project_id)
    # request_url = "{}/repo/{}".format(git_server_url, repo_name)
    # print(request_url)
    #
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"]
    # )
    # response = requests.put(request_url, headers=headers)
    # response.raise_for_status()

    # exit log
    app.logger.debug("Exiting rename_repo_for_project")

    return Response(status=200)


@project_api.route("/v1/project/<string:project_id>/count", methods=["GET"])
@swag_from("swags/count.yaml")
def get_count_of_notebooks_in_project(project_id):
    """ Count of notebooks method"""

    # entry log to add project id to log hander
    #app.logger.add_attr({Constants.PROJECT_ID_KEY: str(project_id)})

    tags = []
    tag = 'project={}'.format(project_id)
    tags.append(tag)
    notebooks_list = fetch_notebooks(tags)

    # exit log
    app.logger.debug("Exiting get_count_of_notebooks_in_project")

    return '{}'.format(len(notebooks_list))


@project_api.route("/v1/project/bulk/count", methods=["POST"])
@swag_from("swags/bulk-count.yaml")
def get_count_of_notebooks_for_list_of_projects():
    """
    API to get count of notebooks in the projects
    """

    data = request.get_json()
    project_ids = data.get("project_ids")

    return jsonify(fetch_notebooks_count_for_projects(project_ids))


@project_api.route("/v1/project/activity", methods=["POST"])
@swag_from("swags/activity.yaml")
def retrieve_activity_of_project():
    """ Api to fetch the activity related to the project"""

    # process input
    data = request.get_json()
    project_id = data.get("project_id")
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    return jsonify(
        fetch_activity_of_project(
            project_id,
            datetime.fromtimestamp(
                start_time / 1000),
            datetime.fromtimestamp(
                end_time / 1000)))
