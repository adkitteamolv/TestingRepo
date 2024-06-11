# -*- coding: utf-8 -*-

"""Init module."""

import os
import logging
from logging.handlers import RotatingFileHandler
from uuid import uuid4
import tempfile
import sys
import random
from urllib.parse import quote
import json
from distutils.dir_util import copy_tree
import shutil
from urllib.parse import urlparse
import urllib
import requests
import git
from git import *
from gitlab import Gitlab
from flasgger import Swagger
from flask_deprecate import deprecate_route
from flask import Flask, Response, jsonify, make_response, redirect, request, g, Blueprint, current_app
from mosaic_utils.ai.headers.constants import Headers
from mosaic_utils.ai.git_repo import utils as git_details
from flasgger import swag_from
from mosaic_utils.ai.headers.utils import generate_headers
from mosaic_utils.ai.logger.utils import log_decorator
from .constants import GitProvider, MessageConstants, ConfigKeyNames, RepoType

from .clients.generic_client import GenericClient
# from mosaic_utils.ai.headers.utils import check_project_access, generate_headers

from .clients import get_client
from .clients.constants import GenericConstants
from notebooks_api.utils.file_utils import extract_tar, extract_zip, git_clone, \
    git_push_file, replace_special_chars_with_ascii, decode_base64_to_string, \
    checkout_new_branch
from notebooks_api.utils.exceptions import (
    RepoAuthentiactionException,
    ErrorCodes, VCSException,
    ApiAuthorizationException,
    RepoAccessException,
    InvalidRepoUrlException,
    InvalidBranchORBaseDirException, NoRepoException
)
from distutils.dir_util import copy_tree
from flasgger import swag_from
import shutil
from urllib.parse import urlparse
import urllib
from .models import Version as Version, db
from .manager import (create_version, get_versions, get_version, create_new_version_record, get_max_version_number,
                      get_next_version_number, get_version_with_data)
from .clients.base import GitClient
from .views import View, check_duplicate_name, if_not_delete_nb, if_delete_nb, when_response_is_blank
from . import version_control_api

# log = logging.getLogger("mosaic_version_control")
# flask_log_file = os.path.join(current_app.config["LOG_FILE_DIR"], "flask.app.log")
# _handler = RotatingFileHandler(flask_log_file)
# log.setLevel(current_app.config["LOG_LEVEL"])
# log.addHandler(_handler)
# stream_handler = logging.StreamHandler(sys.stdout)
# stream_handler.setLevel(logging.DEBUG)
# log.addHandler(stream_handler)

# setting the application logging mechanism


# get git client
# CLIENT = get_client(current_app.config)
# global CLIENT


# @mosaic_version_control.before_request
# def authorization():
#     """ Check user privileges """
#     # skip in case of test cases
#     if current_app.config["TESTING"]:
#         return
#
#     # skip auth
#     if skip_authentication():
#         return
#
#     """ Authorization middleware """
#     # authorize all incoming requests
#     if all(
#             [
#                 Headers.x_project_id in request.headers,
#             ]
#     ):
#         g.user['project_id'] = request.headers[Headers.x_project_id]
#         if Headers.x_project_id in request.headers:
#             return check_project_access(current_app.config["CONSOLE_BACKEND_URL"],g.user['mosaicId'], g.user['email_address'], g.user['first_name'],
#                                         g.user['project_id']
#                                         )
#
#     return Response("Access denied", status=403)


# Every request will filter here before hit actual rest end point URL
# @version_control_api.before_request
# # @log_decorator
# def before_request():
#     """ Middleware to inject request and validate attribute in request headers"""
#     # parse headers to get request id and project id
#     request_id = request.headers.get('Request-Id', str(uuid4()))
#     project_id = request.headers.get('Project-id', '')


@version_control_api.before_request
# @log_decorator
def get_repo_details():
    from notebooks_api.notebook.manager import get_git_repo, list_git_repo, add_git_repo
    """ Method to get enabled repository for the project by calling notebooks-api service"""
    if skip_authentication():
        return
    g.repo_details = None
    g.CLIENT = None
    if Headers.x_enabled_repo in request.headers:
        g.repo_details = json.loads(request.headers.get(Headers.x_enabled_repo))
        g.CLIENT = get_client(g.repo_details)
        return

    if len(request.headers.get(Headers.x_project_id, '')) == 0:
        project_id = request.view_args.get("repo")
    else:
        project_id = request.headers.get(Headers.x_project_id)
    g.user["project_id"] = project_id

    default_branch = current_app.config.get("DEFAULT_GIT_BRANCH", GenericConstants.DEFAULT_BRANCH)
    repo_payload = {
        "base_folder": "notebooks",
        "branch": default_branch if default_branch else GenericConstants.DEFAULT_BRANCH,
        "password": current_app.config["GIT_TOKEN"],
        "project_id": project_id,
        "repo_name": "Default",
        "repo_status": "Enabled",
        "repo_type": current_app.config["GIT_PROVIDER"].title(),
        "repo_url": current_app.config["GIT_URL"] + "/" + current_app.config["GIT_NAMESPACE"] + "/" + str(project_id) + ".git",
        "username": current_app.config["GIT_NAMESPACE"],
    }

    if current_app.config["GIT_PROVIDER"] == "bitbucket":
        repo_payload["repo_url"] = current_app.config["REMOTE_URL"] + "/" + str(project_id) + ".git"

    if current_app.config["TESTING"]:
        g.repo_details = repo_payload
        g.CLIENT = get_client(g.repo_details)
        return

    x_repo_id = request.headers.get(Headers.x_repo_id, '')
    try:
        g.repo_details = get_git_repo(x_repo_id) if x_repo_id else list_git_repo(project_id=project_id,
                                                                                 repo_status="Enabled")
        g.repo_details["branch"] = request.headers.get(Headers.x_branch_name, g.repo_details["branch"])
        g.CLIENT = get_client(g.repo_details)
    except Exception as ex:
        if "resolving git repo credentials" in ex.args[0]:
            return Response(ex.args[0], status=400)

    x_default_repo_flag = str(request.headers.get(Headers.x_default_repo_flag, "false")).lower() == "true"
    if x_default_repo_flag:
        # Payload for adding entry for Default in case of existing repos
        g.repo_details = repo_payload
        payload = git_details.decode_password(repo_payload, RepoType.PRIVATE_REPO)
        try:
            add_git_repo(payload, project_id)
        except Exception as ex:
            current_app.logger.exception(ex)
        g.CLIENT = get_client(g.repo_details)
    if current_app.config["GIT_STORAGE_TYPE"] != 'DB':
        if not g.repo_details:
            return Response(ErrorCodes.VCS_0002, status=400)
    return


@log_decorator
@version_control_api.route("/v1/version_control/ping")
@swag_from("swags/ping.yaml")
def pong():
    """ Endpoint used to check the health of the service """
    return Response("pong")


# @version_control_api.route("/v1/version_control/repo", defaults={"branch": None}, methods=["POST"]) no use, to be deprecated
@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>", methods=["POST"])
@swag_from("swags/create_repo.yaml")
def create_repo(repo):
    """
    Create git repo
    Args:
        repo (str): name of the git repository
    Returns:
        JSON of the git repo
    """
    response = View().create_repo(repo=repo)
    return make_response(jsonify({'url': response}), 201)
    # repo = repo if repo else uuid4()
    # proxy_details = g.repo_details.get("proxy_details", None)
    # provider = g.CLIENT.provider
    # repo1 = g.CLIENT.create_repo(repo)
    # if proxy_details:
    #     initial_commit(repo, branch=g.repo_details["branch"], proxy_details=proxy_details, git_provider=provider)
    # else:
    #     initial_commit(repo, branch=g.repo_details["branch"], git_provider=provider)
    # return make_response(jsonify({'url': g.repo_details['repo_url']}), 201)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:project_name>/<string:new_project_name>/<string:project_id>",
                              methods=["PUT"])
@deprecate_route("DeprecationWarning: rename_repo is deprecated")
def rename_repo(project_name, new_project_name, project_id):
    """
    Rename git repo
    """
    resp = View().rename_repo(project_name, new_project_name, project_id)
    return Response(resp)


# to be Deprecated

@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/branch", methods=["GET"])
# @deprecate_route("DeprecationWarning: create_branch is deprecated")
@swag_from("swags/list_branch.yaml")
def list_branches(repo):
    """
    List the different branches available for the given repo

    Args:
        repo (str): name of the git repository

    Returns:
        JSON of the git branches
    """
    # proxy_details = request.args.get("proxy_details")
    proxy_details = request.headers.get("proxy_details")
    response, code = View().list_branches(proxy_details, repo)
    if code == 200:
        return Response(response)
    return jsonify(response), code


@log_decorator
@version_control_api.route("/v1/version_control/repo/branch", methods=["POST"])
@swag_from("swags/create_branch.yaml")
def create_branch():
    """
    Create a new branch of the repo
    """
    payload = request.get_json(silent=False)
    response, code = View().create_branch(payload)
    if code == 201:
        return Response(status=code)
    return Response(response, status=code)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/branch/<string:branch>", methods=["DELETE"])
@deprecate_route("DeprecationWarning: delete_branch is deprecated")
def delete_branch(repo, branch):
    """
    Delete specific branch of the repo

    Args:
        repo (str): name of the git repository
        branch (str): name of the git branch
    """
    g.CLIENT.delete_branch(repo, branch)
    return Response(status=204)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/branch/<string:branch>/file/<path:file_path>", methods=["POST"])
@deprecate_route("DeprecationWarning: create_file is deprecated")
def create_file(repo, branch, file_path):
    """
    Create file in the git repo

    Args:
        repo (str): name of the git repository
        branch (str): name of the git branch

    JSON payload:
        {
          "file_content": ""
        }
    """
    payload = request.get_json(silent=False)
    file_content = payload["file_content"]
    response = g.CLIENT.create_file(repo, file_path, file_content, branch)
    return Response(json.dumps(response), status=201)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/<path:file_path>/branch/", defaults={"branch": 'master'},
                              methods=["GET"])
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/<path:file_path>/branch/<path:branch>", methods=["GET"])
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/<path:file_path>/commit/<string:commit>", methods=["GET"])
@swag_from("swags/read_file.yaml")
def read_file(repo, file_path, branch=None, commit=None):
    """
    Read file from the git repo
    Args:
        repo (str): name of the git repository
        branch (str): name of the git branch
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter
    """
    raw_content = True if request.args.get('raw_content') and request.args.get(
        'raw_content').lower() == 'true' else False
    commit_type = True if request.args.get('commit_type') and request.args.get(
        'commit_type').lower() == 'true' else False
    response, code = View().read_file(repo, file_path, branch, commit, raw_content, commit_type)
    if code == 200:
        return Response(json.dumps(response), status=200)
    return response, code


@log_decorator
@version_control_api.route(
    "/v1/version_control/download/repo/<string:repo>/file/<path:file_path>/branch/<path:branch>/isfolder/<path:isfolder>",
    methods=["GET"])
@swag_from("swags/download_file.yaml")
def download_file(repo, file_path, isfolder, branch=None):
    """
    Download file
    """
    try:
        if isfolder == "true":
            response, file_name, directory = g.CLIENT.download_folder(g.repo_details["repo_url"], file_path, branch)
        else:
            response = g.CLIENT.download_file(g.repo_details["repo_url"], file_path, branch)
            file_name = file_path.split('/')[-1]

        return Response(response,
                        mimetype='application/octet-stream',
                        headers={"Content-Disposition": f"attachment;filename={file_name}"},
                        status=200)
    except RepoAuthentiactionException as e:
        current_app.logger.exception(e)
        return e.message, 500
    except Exception as ex:
        return ex.args[0], 500


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/<path:file_path>",
                              methods=["PUT"])
@swag_from("swags/update_file.yaml")
def update_file(repo, file_path):
    """
    Update file in the git repo

    Args:
        repo (str): name of the git repository
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter

    JSON payload:
        {
          "file_content": "base64 encoded file"
        }
    """
    payload = request.get_json(silent=False)
    file_content = payload["file_content"]

    if file_path.endswith(".ipynb") and isinstance(file_content, str):
        # ipynb is json
        file_content = json.loads(file_content)

    commit_message = payload.get("commit_message", "file updated")
    enabled_repo = git_details.get_repo(
        repo,
        g.user["email_address"],
        g.user["mosaicId"],
        g.user["first_name"]
    )
    response = g.CLIENT.update_file(file_path, file_content, enabled_repo, message=commit_message)
    return Response(json.dumps(response), status=200)


# pylint: disable=line-too-long
@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/branch/<string:branch>/file/<path:file_path>", methods=["DELETE"])
@deprecate_route("DeprecationWarning: delete_file is deprecated")
def delete_file(repo, branch, file_path):
    """
    Delete file in the git repo

    Args:
        repo (str): name of the git repository
        branch (str): name of the git branch
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter
    """
    g.CLIENT.delete_file(repo, file_path, branch)
    return Response(status=204)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/", defaults={"file_path": None}, methods=["GET"])
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/<path:file_path>", methods=["GET"])
@swag_from("swags/list_repo.yaml")
def list_repo(repo, file_path):
    """
    list the repo

    Args:
        repo(str): name of the git repository
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter
    """
    response, code = View().list_repo(repo, file_path)
    if code == 200:
        return make_response(jsonify(response), 200)
    if code == 400:
        return Response(response, status=400)
    return jsonify({"message": response}), 500


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/content/", defaults={"file_path": None}, methods=["GET"])
@version_control_api.route("/v1/version_control/repo/<string:repo>/file/content/<path:file_path>", methods=["GET"])
@deprecate_route("DeprecationWarning: list_repo_content is deprecated")
def list_repo_content(repo, file_path):
    """
    list the repo

    Args:
        repo(str): name of the git repository
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter
    """
    response = g.CLIENT.list_files_with_content(repo, file_path)
    return Response(json.dumps(response), status=200)


@log_decorator
@version_control_api.route("/v1/version_control/repo/commits/latest", methods=["GET"])
@swag_from("swags/get_latest_commit.yaml")
def get_latest_commit_id():
    """ Method to fetch the recent commit id """
    commits, message, code = View().get_latest_commit_id(request.headers.get('X-Project-Id'))
    # latest_commit_id, project_found, message = g.CLIENT.get_latest_commit(request.headers.get('X-Project-Id'))
    # if project_found:
    #     response = jsonify(commits=latest_commit_id, message=message)
    #     response.status_code = 200
    #     return response
    response = jsonify(commits=commits, message=message)
    response.status_code = code
    return response


@log_decorator
@version_control_api.route("/v1/version_control/repo/commits", methods=["GET"])
@swag_from("swags/get_commits.yaml")
def get_commits():
    """ Method to fetch commit id's for given project_id in request header """
    commits, project_found, message = g.CLIENT.get_commits(g.repo_details["repo_url"], g.repo_details["branch"],
                                                           request.args.get('page_no'), request.args.get('per_page'))
    if project_found:
        response = jsonify(commits=commits, message=message)
        response.status_code = 200
        return response
    response = jsonify(commits=commits, message=message)
    response.status_code = 204
    return response


@log_decorator
@swag_from("swags/get_change_files_in_commit.yaml")
@version_control_api.route("/v1/version_control/repo/commits/<string:commit_id>/file_changed", methods=["GET"])
def get_change_filenames(commit_id):
    """Method to fetch files which are changed in supplied commit id & project id"""
    files, project_found, message = g.CLIENT.get_files(g.repo_details["repo_url"], commit_id)
    if files:
        response = jsonify(files=files, message=message)
        response.status_code = 200
        return response
    response = jsonify(files=files, message=message)
    response.status_code = 204
    return response


@version_control_api.errorhandler(404)
def page_not_found(exception):
    """
    Custom error handler for page not found

    Args:
        exception (Exception): python exception
    """
    return Response(exception, status=404)


@version_control_api.errorhandler(500)
def internal_server_error(exception):
    """
    Custom error handler for internal server error

    Args:
        exception (Exception): python exception
    """
    return Response(exception, status=500)


@log_decorator
@version_control_api.route("/v1/version_control/info", methods=["GET"])
def get_info():
    """
    API to return the URL to git repo
    """
    return '{}/{}'.format(current_app.config["GIT_PUBLIC_URL"], current_app.config["GIT_NAMESPACE"])


@log_decorator
@version_control_api.route("/v1/version_control/genericrepo", methods=["GET"])
# @trace(logger=log)

def list_genericrepo():
    """
    list the repo contents

    Args:
        provider(str): gitlab or github
        url(str): Base URL of the repo
        token(str): Access Token
        namespace(str): Namespace, using only for gitlab
        repo(str): name of the git repository
        file_path (str): path of the file, use urllib.parse.quote_plus to escape path delimiter
    """
    try:
        provider = request.args.get(GenericConstants.PROVIDER)
        url = request.args.get(GenericConstants.URL)
        token = request.args.get(GenericConstants.TOKEN)
        repo_name = request.args.get(GenericConstants.REPO_NAME)
        file_path = request.args.get(GenericConstants.FILE_PATH)
        namespace = request.args.get(GenericConstants.NAMESPACE)

        if provider not in GenericConstants.PROVIDER_LIST:
            return '{\'message\':\'Please provide provider either github or gitlab\'}'
        client = GenericClient(provider, url, token, namespace, repo_name, file_path)
        response = client.generic_list_files()
        current_app.logger.info("Valid response")
        return make_response(jsonify(response), 200)
    except Exception as ex:
        current_app.logger.error("Exception - " + str(ex))


@log_decorator
@version_control_api.route("/v1/version_control/repo/rename/all", methods=["GET"])
def rename_all_repos():
    """
    Get the repo list and rename all repos with project ID

    Args:

    Returns:
        list of git repos renamed and skipped
    """
    repo_list = g.CLIENT.rename_all_repos()
    return make_response(jsonify(repo_list), 200)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/upload", methods=["POST"])
@swag_from("swags/upload_folder.yaml")
def upload_folder(repo):
    """
    git api to receive files from NB backend
    :param repo:
    :return:
    """
    try:
        file = request.files['file1']
        upload_path = request.form["upload_path"] if "upload_path" in request.form else ""
        notebook_id = request.form["notebook_id"] if "notebook_id" in request.form else None
        commit_message = request.form["commit_message"] if "commit_message" in request.form else "Folder/File upload"
        response, _ = View().upload_folder(repo, file, upload_path, notebook_id, commit_message)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args[0], status=400)





@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/gitupload", methods=["POST"])
@swag_from("swags/git_upload.yaml")
def git_upload(repo, temp_dir=None, ignore_duplicate=False, delete_nb=None, path=None,
               commit_message="Folder/File upload", upload_path="", data={}):
    """
    common git api to upload
    :param repo:
    :param temp_dir:
    :param ignore_duplicate:
    :param delete_nb:
    :param commit_message:
    :return:
    """
    try:
        if not temp_dir:
            data = request.get_json()
            temp_dir = data.get("temp_dir")
        response, temp_dir = View()._git_upload(repo, temp_dir, ignore_duplicate, delete_nb, path, commit_message, upload_path, data=data)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify(ex.args[0], temp_dir), 400


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/uploadflow", methods=["POST"])
@swag_from("swags/upload_flow.yaml")
def upload_flow(repo):
    """
    git api to receive files from dag-backend
    :param repo:
    :return:
    """
    try:
        file = request.files['flow']
        username = current_app.config["GIT_NAMESPACE"]
        password = replace_special_chars_with_ascii(str(current_app.config["GIT_PASSWORD"]))
        git_temp_dir = tempfile.mkdtemp()
        url = "{0}/{1}.git".format(current_app.config["REMOTE_URL"], repo)
        url_parts = url.split("//")
        remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])
        proxy_details = g.repo_details.get("proxy_details", {})
        if proxy_details:
            git_clone(git_temp_dir, remote_url, g.repo_details['branch'],
                      proxy_details)
        else:
            git_clone(git_temp_dir, remote_url, g.repo_details['branch'])
        file.save(os.path.join(git_temp_dir, "flows", file.filename))
        if proxy_details:
            response = git_push_file(git_temp_dir, g.repo_details['branch'], proxy_details)
        else:
            response = git_push_file(git_temp_dir, g.repo_details['branch'])
        if response != '' and os.path.isdir(git_temp_dir):
            shutil.rmtree(git_temp_dir)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args[0], status=400)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/upload/temp_dir", methods=["POST"])
@swag_from("swags/git_upload_continue.yaml")
def git_upload_continue(repo):
    """
    git api to continue after duplicate file/folder error
    :param repo:
    :return:
    """
    try:
        data = request.get_json()
        temp_dir = data.get("temp_dir")
        commit_message = data.get("commit_message", "Folder/File upload")
        ignore_duplicate = True
        response = git_upload(repo, temp_dir, ignore_duplicate, commit_message=commit_message, data=data)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify(ex.args[0]), 400


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/delete/notebook", defaults={'path': None}, methods=["DELETE"])
@version_control_api.route("/v1/version_control/repo/<string:repo>/delete/notebook/<path:path>", methods=["DELETE"])
@swag_from("swags/delete_notebook.yaml")
def delete_notebook(repo, path):
    """
    api to delete notebooks
    :param repo:
    :return:
    """
    if path is None:
        path = g.repo_details["base_folder"]

    try:
        data = request.get_json()
        name = data.get("name")
        commit_message = data.get("commit_message", "Delete File/Folder")
        View()._git_upload(repo, temp_dir=None, ignore_duplicate=True, delete_nb=name, path=path,
                           commit_message=commit_message, data=data)
        return Response(status=204)
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify({"message": ex}), 400


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/<string:entity_type>/upload", methods=["POST"])
@swag_from("swags/upload_custom_folder.yaml")
def upload_folder_per_type(repo, entity_type):
    """
    git api to upload files to git repo
    :param repo:
    :param entity_type:
    :return:
    """
    try:
        file = request.files['file1']
        notebook_id = request.form["notebook_id"] if "notebook_id" in request.form else None
        temp_file_dir = tempfile.mkdtemp()
        file.save(os.path.join(temp_file_dir, file.filename))
        tmp_file_path = os.path.join(temp_file_dir, file.filename)
        if file.filename.endswith(".tar.gz"):
            extract_tar(tmp_file_path, temp_file_dir)
            os.unlink(tmp_file_path)
            response = git_upload_per_type(repo, temp_file_dir, entity_type)
        elif file.filename.endswith(".zip"):
            extract_zip(tmp_file_path, temp_file_dir)
            os.unlink(tmp_file_path)
            response = git_upload_per_type(repo, temp_file_dir, entity_type)
        elif file.filename.endswith("note.json"):
            if notebook_id:
                tmpfile = tempfile.mkdtemp()
                os.makedirs(os.path.join(tmpfile, "Zeppelin-Notebooks", notebook_id))
                dir_tmp = os.path.join(tmpfile, "Zeppelin-Notebooks", notebook_id)
                copy_tree(temp_file_dir, dir_tmp)
                response = git_upload_per_type(repo, temp_file_dir, entity_type)
                when_response_is_blank(tmpfile, None)
            else:
                response = git_upload_per_type(repo, temp_file_dir, entity_type)
        else:
            response = git_upload_per_type(repo, temp_file_dir, entity_type)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args[0], status=400)
    finally:
        when_response_is_blank(temp_file_dir, None)


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/<string:entity_type>/gitupload", methods=["POST"])
@swag_from("swags/git_upload_per_type.yaml")
def git_upload_per_type(repo, temp_dir=None, entity_type=None, ignore_duplicate=False, delete_nb=None, path=None):
    """
    common git api to upload
    :param repo:
    :param temp_dir:
    :param entity_type:
    :param ignore_duplicate:
    :param delete_nb:
    :return:
    """
    try:
        if not temp_dir:
            data = request.get_json()
            temp_dir = data.get("temp_dir")
        if "workflow".lower() in entity_type.lower():
            entity_type = "workflows"
        elif "notebook".lower() in entity_type.lower():
            entity_type = "notebooks"
        elif "preposthook".lower() in entity_type.lower():
            entity_type = "preposthooks"
        username = current_app.config["GIT_NAMESPACE"]
        password = replace_special_chars_with_ascii(str(current_app.config["GIT_PASSWORD"]))
        git_temp_dir = tempfile.mkdtemp()
        url = "{0}/{1}.git".format(current_app.config["REMOTE_URL"], repo)
        url_parts = url.split("//")
        remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])
        proxy_details = g.repo_details.get("proxy_details", {})
        if proxy_details:
            git_clone(git_temp_dir, remote_url, proxy_details)
        else:
            git_clone(git_temp_dir, remote_url)
        if not ignore_duplicate:
            check_duplicate_name(git_temp_dir, temp_dir)
        if not delete_nb:
            if_not_delete_nb(ignore_duplicate, temp_dir, git_temp_dir, entity_type)
        else:
            if_delete_nb(data, git_temp_dir, path, delete_nb)
        if proxy_details:
            response = git_push_file(git_temp_dir, proxy_details)
        else:
            response = git_push_file(git_temp_dir)
        if response != '':
            when_response_is_blank(git_temp_dir, temp_dir)
        return response
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify(ex.args[0], temp_dir), 400


# @log_decorator
def skip_authentication():
    skip_auth = current_app.config["SKIP_AUTH"]
    url = request.url
    if [auth_url for auth_url in skip_auth if auth_url in url]:
        return True


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/branch/<string:branch>/file-path/<path:file_path>",
                              methods=["GET"])
@swag_from("swags/get_file_url.yaml")
def get_file_url(repo, branch, file_path):
    """

    :param repo: git repo
    :param branch: git branch
    :param file_path: git file path
    :return: url
    """
    try:
        if current_app.config["GIT_PROVIDER"] == GitProvider.github or current_app.config["GIT_PROVIDER"] == GitProvider.gitlab:
            url = f'{current_app.config["REMOTE_URL"]}/{repo}/blob/{branch}/{file_path}'
        elif current_app.config["GIT_PROVIDER"] == GitProvider.bitbucket:
            url = f'{current_app.config["REMOTE_URL"]}/{repo}/src/{branch}/{file_path}'
        elif current_app.config["GIT_PROVIDER"] == GitProvider.azuredevops:
            url = f'{current_app.config["REMOTE_URL"]}/_git/{repo}?path=/{file_path}&version=GB{branch}'
        else:
            raise ValueError("Not a valid git provider")
        return url
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify(e.args[0]), 400


@log_decorator
@version_control_api.route("/v2/version_control/components", methods=["POST"])
@swag_from("swags/save_version.yaml")
def save_version():
    """
    Creates new version of a component
    :return: Version number in JSON Object {"version_number" : "V1"}
    """
    try:
        project_id = request.headers.get(Headers.x_project_id)
        req_obj = request.get_json()
        data = req_obj.get("data")
        commit_message = req_obj.get("commit_message")
        component_id = req_obj.get("component_id")
        component_type = req_obj.get("component_type")
        version_number = get_next_version_number(component_id, component_type, project_id)

        if current_app.config["GIT_STORAGE_TYPE"] == "GIT":
            file_name = component_id + ".json"
            username = current_app.config["GIT_NAMESPACE"]
            password = replace_special_chars_with_ascii(str(current_app.config["GIT_PASSWORD"]))
            git_temp_dir = tempfile.mkdtemp()
            url = "{0}/{1}.git".format(current_app.config["REMOTE_URL"], project_id)
            url_parts = url.split("//")
            remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])
            git_clone(git_temp_dir, remote_url, current_app.config["DEFAULT_GIT_BRANCH"])

            path = git_temp_dir + "/" + component_type + "s"
            if not os.path.exists(path):
                os.makedirs(path)

            with open(os.path.join(path, file_name), 'w+') as temp_file:
                temp_file.write(json.dumps(data, indent=4))

            commit_id = git_push_file(git_temp_dir, current_app.config["DEFAULT_GIT_BRANCH"], commit_message)

            if commit_id != '':
                if os.path.isdir(git_temp_dir):
                    shutil.rmtree(git_temp_dir)
                version_number = create_new_version_record(
                    component_id=component_id,
                    component_type=component_type,
                    project_id=project_id,
                    commit_id=commit_id,
                    version_number=version_number,
                    commit_message=commit_message,
                    data=None)
            return Response("{\"version_number\":\"" + version_number + "\"}", status=201, mimetype="application/json")
        version_number = create_new_version_record(
            component_id=component_id,
            component_type=component_type,
            project_id=project_id,
            commit_id=random.randint(100000, 1000000),
            version_number=version_number,
            commit_message=commit_message,
            data=data)
        return Response("{\"version_number\":\"" + version_number + "\"}", status=201, mimetype="application/json")
    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args, status=500)


@log_decorator
@version_control_api.route("/v2/version_control/components", methods=["GET"])
@swag_from("swags/search_versions.yaml")
def search_versions():
    """
    Search API for versions metadata
    :return: version objects when version_number = all else single version object will be return
    """
    try:
        project_id = request.headers.get(Headers.x_project_id)
        req_args = request.args
        component_type = req_args.get("component_type")
        component_id = req_args.get("component_id")
        version_number = req_args.get("version_number")
        offset = req_args.get("offset")
        limit = req_args.get("limit")

        if version_number == 'all':
            return Response(get_versions(project_id, component_type, component_id, offset, limit),
                            status=200,
                            mimetype="application/json")

        return Response(get_version_with_data(project_id, component_type, component_id, version_number,
                                                     current_app.config["DEFAULT_GIT_BRANCH"]),
                        status=200,
                        mimetype="application/json")
    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args[0], status=500, mimetype="application/json")


@log_decorator
@version_control_api.route("/v3/version_control/components", methods=["GET"])
@swag_from("swags/search_versions.yaml")
def get_file_for_version():
    """
    Search API for versions metadata
    :return: version objects when version_number = all else single version object will be return
    """
    try:
        project_id = request.headers.get(Headers.x_project_id)
        req_args = request.args
        component_type = req_args.get("component_type")
        component_id = req_args.get("component_id")
        version_number = req_args.get("version_number")
        offset = req_args.get("offset")
        limit = req_args.get("limit")
        version = get_version(
            project_id=project_id,
            component_type=component_type,
            component_id=component_id,
            version_number=version_number)

        if version_number == 'all':
            return Response(get_versions(project_id, component_type, component_id, offset, limit),
                            status=200,
                            mimetype="application/json")

        if current_app.config["GIT_STORAGE_TYPE"] == "GIT":
            commit_id = version.__getattribute__("commit_id")
            repo_name = g.repo_details["repo_url"]
            file_path = component_type + "s/" + component_id + ".json"
            file_path = quote(file_path)
            data = g.CLIENT.read_file(repo_name, file_path, commit_id, True)
            response = {
                'data': json.loads(data['content'])
            }
            json_merged = {**json.loads(json.dumps(version.as_dict())), **json.loads(json.dumps(response))}

            return Response(json.dumps(json_merged), status=200, mimetype="application/json")

        json_merged = {**json.loads(json.dumps(version.as_dict()))}
        return Response(json.dumps(json_merged), status=200, mimetype="application/json")

    except Exception as ex:
        current_app.logger.exception(ex)
        return Response(ex.args[0], status=500, mimetype="application/json")


@log_decorator
@version_control_api.route("/v1/version_control/repo/<string:repo>/<string:version_id>/gittag", methods=["POST"])
@swag_from("swags/git_tag.yaml")
def git_tag(repo, version_id):
    """
    common git api to upload
    :param repo:
    :param version_id:
    :return:
    """
    try:
        repo_id = request.args.get('repo_id')
        branch = request.args.get('branch')
        git_temp_dir = tempfile.mkdtemp()
        enabled_repo = git_details.get_repo(
            repo,
            g.user["email_address"],
            g.user["mosaicId"],
            g.user["first_name"],
            repo_id=repo_id if repo_id else None
        )
        remote_url = enabled_repo['url']
        branch = branch if branch else enabled_repo['branch']
        import git
        proxy_details = enabled_repo.get("proxy_details", None)
        if proxy_details:
            proxy_details = json.loads(proxy_details)
            proxy_ip = proxy_details.get("IPaddress", None)
            verify_ssl = proxy_details.get('SSLVerify', True)
            proxy_type = proxy_details.get("Protocol", 'http')
            proxy_type = "http"  # Currently kept it to http for SCB use case
            # When proxy type was set to https the git clone did not work
            proxy_username = proxy_details.get('UsernameOrProxy', None)
            proxy_password = proxy_details.get('PasswordOrProxy', None)
            if proxy_username and proxy_password:
                if verify_ssl:
                    cloned_repo = git.Repo.clone_from(remote_url, git_temp_dir, branch=branch,
                                                      config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}",
                                                      allow_unsafe_options=True)
                else:
                    cloned_repo = git.Repo.clone_from(remote_url, git_temp_dir, branch=branch,
                                                      config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}",
                                                      allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'})
            else:
                if verify_ssl:
                    cloned_repo = git.Repo.clone_from(remote_url, git_temp_dir, branch=branch,
                                                      config=f"http.proxy={proxy_type}://{proxy_ip}",
                                                      allow_unsafe_options=True)
                else:
                    cloned_repo = git.Repo.clone_from(remote_url, git_temp_dir, branch=branch,
                                                      config=f"http.proxy={proxy_type}://{proxy_ip}",
                                                      allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'})
        else:
            cloned_repo = git.Repo.clone_from(remote_url, git_temp_dir, branch=branch)
        cloned_repo.config_writer().set_value("user", "name", request.headers[Headers.x_auth_userid]).release()
        cloned_repo.config_writer().set_value("user", "email", request.headers[Headers.x_auth_email]).release()
        new_tag = cloned_repo.create_tag(version_id, ref=branch, message='model version tag')
        cloned_repo.remotes.origin.push(new_tag)
        if os.path.isdir(git_temp_dir):
            shutil.rmtree(git_temp_dir)
        return jsonify("Tag created successfully"), 200
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify("Exception while creating tag"), 500


@log_decorator
@version_control_api.route("/v1/version_control/repo/validate", methods=["POST"])
@swag_from("swags/git_validate.yaml")
def validate_git():
    """
    This API validates the git repository in terms of URL, Credentials,
    Branch, Access and Base folder.
    :return: It returns the message
    """
    # VALIDATE CREDENTIALS AND ACCESS
    payload = request.get_json()
    response, code = View().validate_git(payload)
    return jsonify(response), code


@log_decorator
@version_control_api.route("/v1/version_control/repo/validate-macro", methods=["POST"])
@swag_from("swags/git_validate_macro.yaml")
def validate_git_macro_credentials():
    try:
        data = request.get_json()
        if data.get('repo_type', '') in current_app.config.get(ConfigKeyNames.PROXY_ENABLED_GIT_PROVIDER, []):
            data['proxy_details'] = current_app.config.get(ConfigKeyNames.PROXY_DETAILS, {})
        g.CLIENT = get_client(data)
        g.CLIENT.list_files(data["repo_url"], data["base_folder"],
                            data.get("branch", ""), limit=1)
        return Response("Validated successfully", 200)
    except VCSException as ex:
        current_app.logger.exception(ex)
        # As UI breaks with 401 status code hence updated it with 400 status as temoprary fix
        ex.code = 400 if ex.code == 401 else ex.code
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        return jsonify({"error": "Validation Failed", "description": str(ex)}), 400
