#! -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
""" Controllers associated with the notebook module """

import json
import os
import tempfile
import shutil
import logging
import urllib
from uuid import uuid4
import requests

from flasgger import swag_from
from flask import (
    Response,
    current_app as app,
    g,
    jsonify,
    request,
    stream_with_context,
    send_from_directory,
)
from mosaic_utils.ai.git_repo import utils as git_details
from mosaic_utils.ai.headers.utils import generate_headers
from mosaic_utils.ai.audit_log.utils import audit_logging
from mosaic_utils.ai.data_files.utils import convert_into_bytes
from mosaic_utils.ai.headers.constants import Headers
from mosaic_utils.ai.k8 import pod_metrics_summary
from mosaic_utils.ai.k8.utils import create_job_name
from notebooks_api import metrics
from notebooks_api.notebook.exceptions import QuotaExceed
from notebooks_api.utils.data import clean_data
from notebooks_api.utils.defaults import register_metrics
from notebooks_api.utils.exceptions import ErrorCodes, MosaicException, ExperimentWithSameNameException,FileWithSameNameExists, QuotaExceedException, CreateK8ResourceBYOCException, SpawningError, NoRepoException
from notebooks_api.utils.jupyter_hub import (
    create_pod_name,
    handle_anonymous_user,
)
from notebooks_api.utils.tags import get_tag, get_tag_val
from notebooks_api.utils.project import create_repo_name
from notebooks_api.data_files.manager import filter_for_regex, get_base_path, check_and_create_directory, remove_log_dir, check_and_create_log_directory, get_project_resource_quota, get_list_of_files, remove_file_folder
from notebooks_api.spawner.manager import create_k8_pod, clean_env_variables, get_pod_metrics_max, delete_k8_resources, delete_k8_resources_byoc
from notebooks_api.version_control.views import View

from .models import (
    DockerImage,
    Notebook,
    NotebookPod,
    Resource,
    db,
    TemplateStatus,
)
from .tasks import stop_notebook_pod, create_notebook_in_git, async_execute_notebook
from . import notebook_api
from .constants import (
    PodStatus,
    SchedulerURL,
    SpawnerURL,
    StringConstants,
    VcsURL,
    KernelType,
    NotebookPath,
    ExperimentStyles,
    RepoStatus,
    RepoAccessCategory
)
from .job import ExecuteNotebook
from .manager import (
    archive_notebook_pod,
    change_the_updated_time_for_notebook,
    create_notebook,
    delete_notebook,
    delete_notebook_pod,
    fetch_notebooks,
    fetch_pod,
    fetch_running_notebooks,
    fetch_running_notebooks_for_metrics,
    fetch_spcs_data_by_query,
    read_notebook,
    read_notebook_by_name,
    register_notebook_pod,
    update_notebook,
    update_notebook_in_db,
    update_pod_status,
    create_token,
    get_envs,
    base_version_tag,
    validate_upload_json,
    fetch_init_script,
    fetch_pod_project_id,
    fetch_running_template,
    register_template_status,
    update_template_status,
    read_template,
    fetch_pod_template,
    create_template_tag,
    validate_delete_template,
    fetch_running_template_by_user,
    prepare_node_affinity_options,
    fetch_extra_attribute_docker_image,
    get_execute_command_ipynb_to_py, add_git_repo, list_git_repo, delete_git_repo, update_git_repo,
    switch_git_repo,
    fetch_base_image_details_for_custom_build,
    list_data_snapshots,
    register_snapshot,
    get_git_repo,
    delete_snapshot,
    fetch_resource_info,
    get_subscriber_info,
    validate_subscriber_info,
    validate_repo,
    create_jupyter_command,
    update_branch_metadata,
    get_user_impersonation_details,
    create_pod_metrics,
    download_report, init_empty_git_repo,
    fetch_git_branches,
    hash_username,
    get_resource_details,
    get_all_branches,
    get_base_image_os,
    get_project_details,
    fetch_pod_usage,
    trigger_cpu_alerts,
    trigger_memory_alerts,
    get_running_pods,
    delete_active_repo_on_access_revoke,
    list_snowflake_connections,
    spcs_connection_params,
    create_spcs_service,
    stop_spcs_service
)
from .constants import Headers
from ..docker_image.manager import delete_template
from .html_generator.html_generator import HtmlGenerator

# Register metrics if not registered at with Flask create_app()
if metrics is None:
    # pylint: disable=assignment-from-no-return, invalid-name
    metrics = register_metrics()

# pylint: disable=invalid-name

log = logging.getLogger("notebooks_api")


@notebook_api.route("/v1/fetch-spcs-connections", methods=["GET"])
@swag_from("swags/fetch_spcs_connection.yaml")
def list_sonwflake_connection():
    """
    Api to list snowflake connections created by user
    """
    try:
        connection_list = list_snowflake_connections(g.user["mosaicId"])
        return jsonify(connection_list), 200
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0014.format(error=ex), 500


@notebook_api.route("/v1/fetch-spcs-data", methods=["GET"])
@swag_from("swags/fetch_spcs_data.yaml")
def fetch_spcs_data():
    """
    Api to run snowsql query and fetch data from SPCS
    """
    try:
        if request.args.get('connection_id'):
            connection_params = spcs_connection_params(connection_id=request.args['connection_id'])
            if request.args.get('database'):
                connection_params['database'] = request.args['database']
            if request.args.get('schema'):
                connection_params['schema'] = request.args['schema']
            data = fetch_spcs_data_by_query(query_details=request.args, connection_params=connection_params)
        else:
            notebook_pod = fetch_pod_template(request.args['template_id'], g.user["mosaicId"], g.user["project_id"],
                                              status=[PodStatus.RUNNING, PodStatus.STARTING]).as_dict()
            connection_params = spcs_connection_params(connection_id=notebook_pod['spcs_data']['connection_id'])
            connection_params['database'] = notebook_pod['spcs_data']['database']
            connection_params['schema'] = notebook_pod['spcs_data']['schema']
            data = fetch_spcs_data_by_query(query_details=request.args, connection_params=connection_params,
                                            service_name=notebook_pod['pod_name'])
        return jsonify(data), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0013.format(error=ex), 500


@notebook_api.route("/v1/snapshot", methods=["GET"])
@swag_from("swags/list_snapshot.yaml")
def list_snapshot():
    """
    Api to list snapshots
    """
    try:
        snapshot_set = list_data_snapshots(request.headers["X-Project-Id"])
        # send response
        return jsonify(snapshot_set), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0005, 500


@notebook_api.route("/v1/snapshot", methods=["POST"])
@swag_from("swags/create_snapshot.yaml", schema_id="create_snapshot")
def create_snapshot():
    """
    Api to post snapshots
    """
    try:
        snapshots, enabled_repo = dict(), dict()

        _payload = request.json

        snapshots["input"] = _payload.get("input", "NA")
        snapshots["output"] = _payload["output"]
        snapshots["container_object"] = {"name": 'NA'}

        enabled_repo['repo_name'] = _payload.get("repo_name", "NA")
        enabled_repo['branch'] = _payload.get("branch", "NA")
        snapshot_set = register_snapshot(snapshots,
                                         g.user["mosaicId"],
                                         request.headers["X-Project-Id"],
                                         enabled_repo)

        # committing to database as entire execution has completed successfully
        db.session.commit()

        return jsonify(dict(id=snapshot_set.id)), 201
    # pylint: disable=broad-except
    except Exception as ex:
        # rolling back the transaction on failure
        db.session.rollback()
        log.debug(ex)
        return ErrorCodes.ERROR_0005, 500


@notebook_api.route("/v1/snapshot/<snapshot_id>", methods=["GET"])
@swag_from("swags/read_snapshot.yaml")
def read_snapshot(snapshot_id):
    """
    Api to read a snapshot
    """
    try:
        snapshot_set = list_data_snapshots(request.headers["X-Project-Id"], str(snapshot_id))
        # send response
        return jsonify(snapshot_set), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0005, 500


@notebook_api.route("/v1/snapshot/list/<snapshot_name>", methods=["GET"])
@swag_from("swags/list_file_snapshot.yaml")
def list_files_snapshot(snapshot_name):
    """
    API to list data files
    """
    try:
        # fetch data files
        data_files = get_list_of_files("", f'{request.headers["X-Project-Id"]}/{request.headers["X-Project-Id"]}-Snapshot/{snapshot_name}')
        filtered_files = filter_for_regex(data_files, "")
        # send response
        return jsonify({"data_files": filtered_files}), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0005, 500

@notebook_api.route("/v1/delete-snapshot", methods=["DELETE"])
@swag_from("swags/delete_snapshot.yaml")
def delete_snapshot_api():
    """
    API to delete snapshot
    """
    try:
        snapshotname = request.args.get("snapshotname")
        delete_snapshot(snapshotname, request.headers["X-Project-Id"])
        remove_file_folder(f'{request.headers["X-Project-Id"]}/{request.headers["X-Project-Id"]}-Snapshot/{snapshotname}', "")
        # send response
        return snapshotname, 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0005, 500

@notebook_api.route("/v1/notebooks", methods=["GET"])
@swag_from("swags/list.yaml")
def list_api():
    """
    API to list notebooks
    """

    # parse data
    tags = request.args.getlist("tags")

    # entry log
    log.debug("Fetching notebooks with tags=%s", tags)

    # fetch notebooks
    notebooks = fetch_notebooks(tags)

    # send response
    return jsonify(notebooks)


@notebook_api.route("/v1/notebooks", methods=["POST"])
@swag_from("swags/create.yaml", validation=True, schema_id="create_notebook")
def create_api():
    """
    API to create notebook
    """
    # parse data
    data = request.get_json()
    data = clean_data(data)
    path = data.pop("path", "/")
    user = g.user["mosaicId"]
    project_tag = get_tag("project", data.get("tags", []))

    # check quota of the user
    # validating user running container
    log.info("Validating user user running container")
    try:
        check_quota_for_user(project_tag, user)
    except QuotaExceed:
        log.error("Quota exceeded for user=%s", user)
        return ErrorCodes.MOSAIC_0001, 429

    # create notebook object
    notebook = create_notebook(data)
    _, project = get_tag("project", notebook["tags"], split=True)
    _, label = get_tag("label", notebook["tags"], split=True)
    _, notebook_type = get_tag("type", notebook["tags"], split=True)
    notebook_id = notebook["id"]

    name = (path + "/" + notebook["name"]) if path != "/" else notebook["name"]
    # entry log to add project id to log hander
    # log.add_attr({Constants.PROJECT_ID_KEY: str(project)})

    create_notebook_in_git(name, project, label, notebook_id, notebook_type)
    # start notebook
    try:
        notebook_url, progress_url, terminal_url = start(notebook)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0002, 429

    log.debug("Container start, sending response back to UI")

    # send response
    return jsonify(
        {
            "url": notebook_url,
            "progress": progress_url,
            "name": notebook["name"],
            "id": notebook["id"],
            "terminal": terminal_url,
        }
    )


# pylint: disable=line-too-long, too-many-statements
# pylint: disable=too-many-locals, too-many-return-statements
@notebook_api.route("/v1/templates", methods=["POST"])
@swag_from("swags/create.yaml", validation=True, schema_id="create_notebook")
def create_template():
    """
    API to create notebook
    """
    try:
        # parse data
        data = request.get_json()
        data = clean_data(data)
        path = data.pop("path", "/")

        user = g.user["mosaicId"]
        project_tag = get_tag("project", data.get("tags", []))
        docker_id = data.get("docker_image_id")
        _, project = get_tag("project", data.get("tags", []), split=True)
        register_condition = data.get("register_condition")
        if register_condition is None:
            register_condition = True
        if data.get('input') is None:
            data["input"] = KernelType.default
        if data.get('output') is None:
            data["output"] = KernelType.default
        log.debug("validating template already running by user")
        fetch_running_template_by_user(docker_id, user, project)
        # check quota of the user
        # validating user running container
        log.info("Validating user user running container")
        check_quota_for_user_template(project_tag, project, user)
        enabled_repo = list_git_repo(g.user["project_id"], RepoStatus.Enabled)
        if not enabled_repo:
            raise NoRepoException

        log.debug("audit_logging start notebook :%s", docker_id)
        docker_image = DockerImage.query.get(docker_id)
        if docker_image.type == 'CUSTOM_BUILD_SPCS':
            data.update({"spcs_data": docker_image.spcs_data})
        if 'SPCS' in docker_image.type:
            launch_docker_image = docker_image.docker_url if data['spcs_data']['compute_pool_type'] == "cpu" else docker_image.gpu_docker_url
        else:
            if data.get('spcs_data'):
                data.pop('spcs_data')
            launch_docker_image = docker_image.docker_url if docker_image.resource.extra == "cpu" else docker_image.gpu_docker_url

        audit_logging(
            console_url=app.config["CONSOLE_BACKEND_URL"],
            action_type="RUN",
            object_id=docker_id,
            object_name=docker_image.as_dict().get("name"),
            object_type="NOTEBOOK",
            object_json=json.dumps(data),
            headers=request.headers,
        )

        # start notebook

        create_template_tag(project_tag, user, docker_id)
        # TODO_ is this needed? duplicate
        docker_image = DockerImage.query.get(docker_id)
        data.update({"docker_image": docker_image.as_dict()})
        data.update({"tags": data.get("tags", [])})
        data.update({"resource": docker_image.resource.as_dict()})
        data.update({"executor_resource": docker_image.executor_resource.as_dict() if docker_image.executor_resource else {}})
        data.update({"path": path})
        data.update({"launch_docker_image": launch_docker_image})
        if docker_image.as_dict().get('auto_commit'):
            data.update({"auto_commit": 'true'})
        else:
            data.update({"auto_commit": 'false'})

        message = ""
        notebook_url, progress_url, terminal_url, pod_name, port, success = start_template_new(data, enabled_repo, register_condition)

        if not success:
            raise SpawningError
        log.debug("Container start, sending response back to UI")

        # send response
        return jsonify(
            {
                "url": notebook_url,
                "progress": progress_url,
                "name": data["docker_image"]["name"],
                "id": data["docker_image"]["id"],
                "terminal": terminal_url,
                "template_pod_name": pod_name,
                "port": port,
                "message": message
            }
        )

    # pylint: disable=broad-except
    except MosaicException as ex:
        log.error(ex)
        return jsonify(ex.message_dict()), ex.code
    except Exception as e:
        log.error(e)
        ex = SpawningError()
        return jsonify(ex.message_dict()), ex.code




@notebook_api.route("/v1/notebooks/<uuid:notebook_id>", methods=["GET"])
@swag_from("swags/read.yaml")
def read_api(notebook_id):
    """
    API to read notebook

    Args:
         notebook_id (UUID): UUID of the notebook
    """
    log.debug("Test")
    log.error("Test")

    log.debug(g.user)
    log.error(g.user)

    # parse data
    notebook_id = str(notebook_id)

    log.debug("Reading notebook=%s", notebook_id)

    # fetch notebook
    notebook = read_notebook(notebook_id)

    log.debug("Fetched notebook=%s", notebook)

    # send response
    return jsonify(notebook)


@notebook_api.route("/v1/notebooks/<uuid:notebook_id>", methods=["PUT"])
@swag_from("swags/update.yaml", validation=True, schema_id="update_notebook")
def update_api(notebook_id):
    """
    API to update notebook

    Args:
         notebook_id (UUID): UUID of the notebook
    """
    # parse data
    data = request.get_json()
    data = clean_data(data, update=True)
    notebook_id = str(notebook_id)

    # updating notebook using id
    log.debug("Update notebook=%s", notebook_id)
    notebook_pod = (
        NotebookPod.query.filter(NotebookPod.notebook_id == notebook_id)
        .filter(NotebookPod.status == "RUNNING")
        .all()
    )
    if notebook_pod:
        return jsonify("please stop Running Notebook"), 400
    update_notebook(notebook_id, data)
    log.debug("audit_logging update notebook : %s", notebook_id)
    audit_logging(
        console_url=app.config["CONSOLE_BACKEND_URL"],
        action_type="UPDATE",
        object_id=notebook_id,
        object_name=data["name"],
        object_type="NOTEBOOK",
        object_json=json.dumps(data),
        headers=request.headers,
    )
    # send response
    return Response(status=200)


@notebook_api.route("/v2/notebooks/<uuid:notebook_id>", methods=["PUT"])
@swag_from("swags/update_v2.yaml", validation=True, schema_id="update_notebook_v2")
def update_api_v2(notebook_id):
    """
    API to update notebook

    Args:
         notebook_id (UUID): UUID of the notebook
    """

    # parse data
    data = request.get_json()
    notebook_id = str(notebook_id)

    # updating notebook using id
    log.debug("Update notebook=%s", notebook_id)

    update_notebook_in_db(notebook_id, data)

    # send response
    return Response(status=200)


@notebook_api.route("/v1/notebooks/<uuid:notebook_id>", methods=["DELETE"])
@swag_from("swags/delete.yaml")
def delete_api(notebook_id):
    """
    API to delete notebook

    Args:
         notebook_id (UUID): UUID of the notebook
    """
    user = g.user

    # parse data
    notebook_id = str(notebook_id)

    # delete notebook
    log.debug("Delete notebook=%s ", notebook_id)
    delete_notebook(user, notebook_id)

    log.debug("Notebook deleted successfully")

    # send response
    return Response(status=204)


def check_quota_for_user(project_tag, user, running_notebooks=None):
    """
    :param project_tag:
    :param user:
    :param running_notebooks:
    :return:
    """
    if running_notebooks is None:
        running_notebooks = fetch_running_notebooks(project_tag, user)

    servers = running_notebooks["servers"].values()
    limit = app.config["CONTAINER_LIMIT"]

    if len(servers) >= limit:
        raise QuotaExceedException(msg_code="QUOTA_EXCEED_ERROR_001")


def check_quota_for_user_template(project_tag, project_id, user, running_notebooks=None):
    """
    :param project_tag:
    :param user:
    :param running_notebooks:
    :return:
    """
    log.debug("checking quota for template")
    if running_notebooks is None:
        running_notebooks = fetch_running_template(project_tag, project_id, user)

    servers = running_notebooks["servers"].values()
    limit = app.config["CONTAINER_LIMIT"]

    if len(servers) >= limit:
        raise QuotaExceedException(msg_code="QUOTA_EXCEED_ERROR_001")


# pylint: disable=too-many-locals
def start(notebook):
    """ Method to start notebook """
    # prepare url
    log.debug("in start_api")
    user_id = g.user["mosaicId"]
    notebook_id = notebook["id"]
    hub_base_url = app.config["HUB_BASE_URL"]
    hub_auth_token = app.config["HUB_AUTH_TOKEN"]
    request_url = SpawnerURL.HUB_BASE_URL.format(hub_base_url, user_id, notebook_id)

    log.debug("values")

    # prepare headers
    request_headers = {
        "Authorization": StringConstants.TOKEN.format(hub_auth_token),
        Headers.x_auth_username: g.user["first_name"],
        Headers.x_auth_email: g.user["email_address"],
        Headers.x_auth_userid: g.user["mosaicId"],
    }

    log.debug("after request header generate")
    # backend call to create token
    jwt = create_token()

    # create pod name
    log.debug("Creating pod for notebook=%s", notebook_id)

    project_tag = get_tag("project", notebook["tags"])
    _, label = get_tag("label", notebook["tags"], split=True)
    _, project = get_tag("project", notebook["tags"], split=True)
    _, notebook_type = get_tag("type", notebook["tags"], split=True)
    git_repo = create_repo_name(label, project)
    pod_name = create_pod_name(project, user_id, notebook_id, notebook_type)

    env=get_envs(notebook["id"], jwt, request_headers, project_id=project)
    env["NOTEBOOK_NAME"] = notebook["name"]

    init_script = fetch_init_script(notebook["docker_image"]["id"])

    # pylint: disable=literal-comparison
    if init_script == "":
        init_script = "ls"
    log.debug(init_script)
    log.error(init_script)

    # prepare spawner options
    options = {
        "pod_name": pod_name,
        "git_repo": git_repo,
        "notebook": jsonify(notebook).get_json(),
        "user": g.user,
        "environment_variables": env,
        "init_script": init_script,
    }

    # fetch the running notebooks for user
    running_notebooks = fetch_running_notebooks(project_tag, user_id)

    # check whether the notebook server is running
    if notebook_id not in [x["id"] for x in running_notebooks["servers"].values()]:

        # check qouta
        check_quota_for_user(project_tag, user_id, running_notebooks)

        # create pod in db
        notebook_pod = register_notebook_pod(
            notebook, user_id, pod_name, PodStatus.STARTING
        )

        # start the notebook server
        try:
            log.debug("Trying to spawn a notebook, calling %s", request_url)
            response = handle_anonymous_user(requests.post)(
                request_url, headers=request_headers, json=options
            )
            response.raise_for_status()
        # pylint: disable=broad-except
        except Exception as e:
            log.error(e)
            delete_notebook_pod(notebook_pod)
            raise e

        # update pod status in db
        update_pod_status(notebook_pod, PodStatus.RUNNING)

    # calculate the urls
    url_prefix = app.config["URL_PREFIX"]
    proxy_prefix = app.config["PROXY_PREFIX"]
    notebook_url = SpawnerURL.PROXY_PREFIX_URL.format(
        proxy_prefix, user_id, notebook_id
    )
    progress_url = SpawnerURL.URL_PREFIX.format(url_prefix, user_id, notebook_id)

    terminal_url = ""

    # add notebook name as suffix
    # this is done to open notebook directly rather than showing list of
    # notebooks
    if notebook_type == "jupyter":
        terminal_url = SpawnerURL.TERMINAL_URL.format(notebook_url)
        notebook_url = VcsURL.NOTEBOOK_URL.format(notebook_url, notebook["name"])

    log.debug("Notebook server start and response return")
    return notebook_url, progress_url, terminal_url


# def kubespawner_knights_watch_k8_resource_creation(project_id, pod_name, template_id):
#     """ Method to delete k8 resources uing kubespawner """
#     # call kubespawer for knights watch to create k8 objects for pod created
#     log.debug("inside kubespawner_knights_watch_k8_resource_creation")
#     kubespawner_base_url = app.config["MOSAIC_KUBESPAWNER_BASE_URL"]
#     create_k8_api_for_knights_watch = "create_k8_objects_knights_watch"
#     kubespawner_create_url_knights_watch = (
#         kubespawner_base_url + create_k8_api_for_knights_watch
#     )
#     headers = generate_headers(
#         userid=g.user["mosaicId"],
#         email=g.user["email_address"],
#         username=g.user["first_name"],
#         project_id=project_id,
#     )
#     payload = {"pod_name": pod_name, "template_id": template_id}
#     try:
#         # pylint: disable=W1202
#         log.debug(
#             " url : {0}, payload : {1} , headers : {2}".format(
#                 kubespawner_create_url_knights_watch, payload, headers
#             )
#         )
#         resp = requests.post(
#             kubespawner_create_url_knights_watch, json=payload, headers=headers
#         )
#         log.debug(
#             "completion kubespawner_knights_watch_k8_resource_creation : status {0} ".format(
#                 resp.status_code
#             )
#         )
#     except Exception as e: # pylint: disable=W0703
#         log.debug("kubespawner_knights_watch_k8_resource_creation failed")
#         log.error(e)
#
#
# # pylint: disable=too-many-statements
# def start_template(notebook):
#     """ Method to start notebook """
#     # prepare url
#     log.debug("in start_api")
#     user_id = g.user["mosaicId"]
#     notebook_id = notebook["docker_image"]["id"]
#     nb_path = notebook["path"]
#     _, project = get_tag("project", notebook["tags"], split=True)
#     hub_base_url = app.config["HUB_BASE_URL"]
#     hub_auth_token = app.config["HUB_AUTH_TOKEN"]
#     node_affinity_options = prepare_node_affinity_options()
#
#     log.debug("values")
#
#     # prepare headers
#     request_headers = {
#         "Authorization": StringConstants.TOKEN.format(hub_auth_token),
#         Headers.x_auth_username: g.user["first_name"],
#         Headers.x_auth_email: g.user["email_address"],
#         Headers.x_auth_userid: g.user["mosaicId"],
#     }
#
#     log.debug("after request header generate")
#     # backend call to create token
#     jwt = create_token(request_headers)
#     # create pod name
#     log.debug("Creating pod for notebook=%s", notebook_id)
#     project_tag = get_tag("project", notebook["tags"])
#     _, notebook_type = get_tag("type", notebook["tags"], split=True)
#
#     env = get_input_params(notebook["docker_image"]["id"], jwt, request_headers)
#     env["NOTEBOOK_NAME"] = notebook["docker_image"]["name"]
#
#     init_script = fetch_init_script(notebook["docker_image"]["id"])
#     # pylint: disable=literal-comparison
#     if init_script is "":
#         init_script = "ls"
#     log.debug(init_script)
#     log.error(init_script)
#     log.debug(jsonify(notebook).get_json())
#     # prepare spawner options
#     options = {
#         "git_repo": project,
#         "notebook": jsonify(notebook).get_json(),
#         "user": g.user,
#         "environment_variables": env,
#         "init_script": init_script,
#         "node_affinity_options": node_affinity_options
#     }
#
#     # fetch the running notebooks for user
#     running_notebooks = fetch_running_template(project_tag, project, user_id)
#     # check whether the notebook server is running
#     if notebook_id not in [x["id"] for x in running_notebooks["servers"].values()]:
#
#         # check qouta
#         check_quota_for_user_template(project_tag, project, user_id, running_notebooks)
#
#         # create pod in db
#         notebook_pod = register_template_status(
#             notebook, user_id, PodStatus.STARTING, project
#         )
#
#         # create pod name with template status id instead of template id
#         template_project = notebook_pod.id
#         pod_name = create_pod_name(project, user_id, template_project, notebook_type)
#         # changing the template project id with id from template status
#         request_url = SpawnerURL.HUB_BASE_URL.format(
#             hub_base_url, user_id, template_project
#         )
#         options.update(pod_name=pod_name, template_project=template_project)
#
#         # start the notebook server
#         try:
#             log.debug("Trying to spawn a notebook, calling %s", request_url)
#             response = handle_anonymous_user(requests.post)(
#                 request_url, headers=request_headers, json=options
#             )
#             status_code = response.status_code
#             response.raise_for_status()
#         # pylint: disable=broad-except
#         except Exception as e:
#             log.error(e)
#             update_template_status(notebook_pod, PodStatus.STOPPING)
#             if status_code == 400:
#                 raise SpawningError()
#             raise e
#         # removing @ as after spawning the notebook in k8s, @ is automatically removed
#         # syncing pod name in db with spawned notebook
#         revised_pod_name = pod_name.replace("@", "")
#         # update pod status in db
#         update_template_status(notebook_pod, PodStatus.RUNNING, revised_pod_name)
#
#         # call kubespawner to create k8 resources for knights-watch
#         log.debug("calling kubespawner_knights_watch_k8_resource_creation")
#         kubespawner_knights_watch_k8_resource_creation(
#             project, pod_name, notebook_pod.as_dict().get("id")
#         )
#
#     # calculate the urls
#     url_prefix = app.config["URL_PREFIX"]
#     proxy_prefix = app.config["PROXY_PREFIX"]
#     notebook_url = SpawnerURL.PROXY_PREFIX_URL.format(
#         proxy_prefix, user_id, template_project
#     )
#     progress_url = SpawnerURL.URL_PREFIX.format(url_prefix, user_id, template_project)
#
#     terminal_url = ""
#
#     # add notebook name as suffix
#     # this is done to open notebook directly rather than showing list of
#     # notebooks
#     if notebook_type == "jupyter":
#         terminal_url = SpawnerURL.TERMINAL_URL.format(notebook_url)
#         notebook_url = VcsURL.NOTEBOOK_URL.format(notebook_url)
#         notebook_url = (
#             notebook_url if nb_path == "/" else "{}{}".format(notebook_url, nb_path)
#         )
#
#     # Notebook url for Zeppelin Notebook
#     if notebook_type == ZeppelinNotebook.TYPE:
#         notebook_url = "{}/#/notebook/{}".format(notebook_url, template_project)
#
#     if notebook_type == "rstudio":
#         notebook_url = "{}/user/{}/{}/".format(proxy_prefix, user_id, template_project)
#
#     log.debug("Notebook server start and response return")
#     return notebook_url, progress_url, terminal_url, revised_pod_name


@notebook_api.route("/v1/notebooks/<uuid:notebook_id>/start", methods=["POST"])
@swag_from("swags/start.yaml")
def start_by_id_api(notebook_id):
    """
    API to start notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook
    """

    # parse data
    notebook_id = str(notebook_id)

    # fetch notebook by id
    log.debug("Fetching notebook by notebook_id=%s", notebook_id)
    notebook = read_notebook(notebook_id)

    # start notebook
    try:
        notebook_url, progress_url, terminal_url = start(notebook)
    except QuotaExceed:
        log.debug("Quota exceeded for user=%s", g.user["mosaicId"])
        return ErrorCodes.MOSAIC_0001, 429
    except Exception as ex:  # pylint: disable=broad-except
        log.debug(ex.args)
        log.error(ex)
        return ErrorCodes.MOSAIC_0002, 429

    # prepare response
    response = {
        "url": notebook_url,
        "progress": progress_url,
        "name": notebook["name"],
        "terminal": terminal_url,
    }

    # send response
    return jsonify(response)


def stop(notebook):
    """
    Stop running notebook container
    :param notebook:
    :return:
    """
    user = g.user

    # update pod status
    notebook_pod = fetch_pod(notebook["id"], user["mosaicId"], status=PodStatus.RUNNING)
    update_pod_status(notebook_pod, PodStatus.STOPPING)

    # update pod status
    update_pod_status(notebook_pod, PodStatus.STOPPING)

    # delete pod from kubernetes
    stop_notebook_pod(user, notebook, notebook_pod.as_dict())


def stop_template(notebook, project_id):
    """
    Stop running notebook container
    :param notebook:
    :param project_id:
    :return:
    """
    user = g.user
    # First find pod details for Running or STARTING Template
    notebook_pod = fetch_pod_template(
        notebook["id"], user["mosaicId"], project_id, status=[PodStatus.RUNNING, PodStatus.STARTING]
    )
    if notebook_pod.as_dict()['spcs_data']:
        if stop_spcs_service(notebook_pod.as_dict()['spcs_data'], notebook_pod.as_dict()['pod_name']):
            update_template_status(notebook_pod, PodStatus.STOPPING)
        else:
            raise ValueError("Failed to stop container")

    try:
        pod_name = notebook_pod.as_dict().get('pod_name')
        log.debug(f"this is pod name {pod_name}")
        log.info("Fetching pod_metrics_max")
        metrics = get_pod_metrics_max(pod_name, app.config["PROMETHEUS_URL"])
        if ('max_cpu_utilization' in metrics) and ('max_memory_utilization' in metrics):
            # save to database

            notebook_pod_metrics = {
                'max_memory': metrics['max_memory_utilization']['memory'],
                'max_cpu': metrics['max_cpu_utilization']['cpu'],
                'template_id': notebook["id"],
                'project_id': project_id,
                'template_status': TemplateStatus.query.filter_by(pod_name=pod_name).first()
            }
            log.debug(TemplateStatus.query.filter_by(pod_name=pod_name).first())

            create_pod_metrics(notebook_pod_metrics)
            log.info('metrics added to the databases successfully')
        else:
            log.error(metrics)
    except Exception as e:
        log.error(e)

    # call kubespawner to create k8 resources for knights-watch
    log.debug("calling spawner_knights_watch_k8_resource_deletion")
    knight_watch_delete_status = delete_k8_resources(notebook_pod.as_dict().get("id"))

    # call kubespawner to delete pod & BYOC k8 resources
    byoc_delete_status = delete_k8_resources_byoc(notebook_pod.as_dict().get("pod_name")) if (
        notebook_pod.as_dict().get("pod_name")) else True

    # for removing package installation files created for template run
    remove_log_dir(notebook_pod.as_dict().get("pod_name"), project_id)

    if knight_watch_delete_status and byoc_delete_status:
        update_template_status(notebook_pod, PodStatus.STOPPING)
    else:
        raise ValueError("Failed to stop container")


def stop_using_project_id(notebook):
    """
    Stop running notebook container
    :param notebook:
    :return:
    """
    user = g.user

    # update pod status
    notebook_pod = fetch_pod_project_id(notebook["id"], status=PodStatus.RUNNING)
    update_pod_status(notebook_pod, PodStatus.STOPPING)

    # delete pod from kubernetes
    stop_notebook_pod(user, notebook, notebook_pod.as_dict())


@notebook_api.route("/v1/templates/<uuid:template_id>/stop-db", methods=["DELETE"])
@swag_from("swags/stop_db.yaml")
def update_template_stop_status(template_id):
    """
    API to update template status as STOPPING on pod delete

    Args:
        template_id (UUID): UUID of the template
    """

    log.debug("Inside update_template_stop_status")
    # parse data
    template_id = str(template_id)
    user = g.user
    project_id = g.user["project_id"]
    notebook_pod = fetch_pod_template(
        template_id, user["mosaicId"], project_id, status=[PodStatus.RUNNING, PodStatus.STARTING]
    )
    log.debug("template_id")
    log.debug(notebook_pod.template_id)
    update_template_status(notebook_pod, PodStatus.STOPPING)
    return Response(status=204)


@notebook_api.route("/v1/notebooks/<uuid:notebook_id>/stop", methods=["DELETE"])
@swag_from("swags/stop.yaml")
def stop_by_id_api(notebook_id):
    """
    API to stop notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook server
    """

    # parse data
    notebook_id = str(notebook_id)

    # fetch notebook
    notebook = read_notebook(notebook_id)

    # stop notebook
    try:
        stop(notebook)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500
    # send response
    return Response(status=204)


@notebook_api.route("/v1/templates/<uuid:notebook_id>/stop", methods=["DELETE"])
@swag_from("swags/stop.yaml")
def stop_by_id_template(notebook_id):
    """
    API to stop notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook server
    """
    # parse data
    notebook_id = str(notebook_id)
    project = g.user["project_id"]

    # fetch notebook
    notebook = read_template(notebook_id)

    # stop notebook
    try:
        stop_template(notebook, project)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500
    log.debug("audit_logging stop notebook : %s", notebook_id)
    docker_image = DockerImage.query.get(notebook_id)
    log.debug(docker_image.as_dict())
    headers = generate_headers(
        userid=g.user["mosaicId"],
        email=g.user["email_address"],
        username=g.user["first_name"],
        project_id=project,
    )
    audit_logging(
        console_url=app.config["CONSOLE_BACKEND_URL"],
        action_type="DELETE",
        object_id=notebook_id,
        object_name=docker_image.as_dict().get("name"),
        object_type="NOTEBOOK",
        object_json=json.dumps({"notebook_id": notebook_id}),
        headers=headers,
    )

    # send response
    return Response(status=204)


@notebook_api.route("/v1/templates/<uuid:template_id>", methods=["DELETE"])
@swag_from("swags/delete_template.yaml")
def delete_by_template_id(template_id):
    """
    API to delete template by id

    Args:
        template_id (UUID): UUID of the template_id server
    """
    log.debug("deleting template by id")
    # parse data
    template_id = str(template_id)
    try:
        # stop_template
        validate_delete_template(template_id)
        delete_template(template_id)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return Response(e.args[0], status=400)

    # send response
    return Response(status=204)


def stop_by_id_using_project_id(notebook_id):
    """
    API to stop notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook server
    """

    # parse data
    notebook_id = str(notebook_id)

    # fetch notebook
    notebook = read_notebook(notebook_id)

    # stop notebook
    try:
        stop_using_project_id(notebook)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500

    # send response
    return Response(status=204)


# pylint: disable=inconsistent-return-statements
def update_notebook_for_culling(notebook_id, user_id):
    """
    Updating notebook pod details after culling
    :param notebook:
    :return:
    """
    try:
        # update pod status
        notebook_pod = fetch_pod(notebook_id, user_id, status=PodStatus.RUNNING)
        update_pod_status(notebook_pod, PodStatus.STOPPING)
        archive_notebook_pod(notebook_pod.as_dict(), None)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500


def update_template_for_culling(template_id, user_id):
    """
    Updating notebook pod details after culling
    :param template_id:
    :param user_id:
    :return:
    """
    try:
        # update pod status
        template_pod = TemplateStatus.query \
            .filter(TemplateStatus.created_by == user_id) \
            .filter(TemplateStatus.id == template_id) \
            .filter(TemplateStatus.status == PodStatus.RUNNING) \
            .first()
        update_template_status(template_pod, PodStatus.STOPPING)
        # archive_notebook_pod(notebook_pod.as_dict())
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500


@notebook_api.route(
    "/v1/notebooks/<uuid:notebook_id>/<string:user_id>/cull", methods=["DELETE"]
)
# @swag_from("swags/stop.yaml")
def cull_server_update_db(notebook_id, user_id):
    """
    API to stop notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook server
    """

    # parse data
    notebook_id = str(notebook_id)

    # stop notebook
    try:
        update_notebook_for_culling(notebook_id, user_id)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500

    # send response
    return Response(status=204)


@notebook_api.route(
    "/v1/templates/<string:template_id>/<string:user_id>/cull", methods=["DELETE"]
)
# @swag_from("swags/stop.yaml")
def cull_server_update_template_db(template_id, user_id):
    """
    API to stop notebook server by id

    Args:
        notebook_id (UUID): UUID of the notebook server
    """

    # parse data
    template_id = str(template_id)
    # stop notebook
    try:
        update_template_for_culling(template_id, user_id)
    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return ErrorCodes.MOSAIC_0003, 500

    # send response
    return Response(status=204)


@notebook_api.route(
    "/v1/notebooks/<string:user_id>/<string:notebook_id>/progress", methods=["GET"]
)
@swag_from("swags/progress.yaml")
def progress_api(user_id, notebook_id):
    """
    API to check the progress of notebook server

    Args:
        user_id (string): user id from keycloak
        notebook_id (uuid): id of the notebook
    """

    # cast to string
    notebook_id = str(notebook_id)

    # prepare url
    hub_base_url = app.config["HUB_BASE_URL"]
    hub_auth_token = app.config["HUB_AUTH_TOKEN"]
    request_url = VcsURL.PROGRESS.format(hub_base_url, user_id, notebook_id)

    # prepare headers
    request_headers = {
        "Authorization": StringConstants.TOKEN.format(hub_auth_token),
        Headers.x_auth_username: g.user["first_name"],
        Headers.x_auth_email: g.user["email_address"],
        Headers.x_auth_userid: g.user["mosaicId"],
    }

    # wait until the notebook is spawned
    log.debug("Waiting for response notebook is spawned....")

    response = requests.get(request_url, headers=request_headers, stream=True)

    # send response
    return Response(
        stream_with_context(response.iter_content()), content_type="text/event-stream"
    )


# pylint: disable=line-too-long
@notebook_api.route(
    "/v1/notebooks/<project>/<project_id>/tree/",
    defaults={"path": "notebooks"},
    methods=["GET"],
)
@notebook_api.route(
    "/v1/notebooks/<project>/<project_id>/tree/<path:path>", methods=["GET"]
)
@swag_from("swags/tree.yaml")
def tree_api(project, project_id, path):
    """
    API to fetch the list of files from the git repo

    Args:
         project (str): Name of the project
         project_id (str) Project Id
         path (str): Path to lookup
    """
    # entry log to add project id to log hander
    # #log.add_attr({Constants.PROJECT_ID_KEY: str(project_id)})

    # parse data
    # git_server_url = app.config["VCS_BASE_URL"]
    path = path if path else ""

    # read repo
    log.debug("Reading repository for project_id=%s", project_id)
    repo_name = create_repo_name(project, project_id)
    # request_url = VcsURL.GIT_URL.format(git_server_url, repo_name, path)
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"],
    # )
    # response = requests.get(request_url, headers=headers)
    # log.debug(response.json())

    # fetch notebooks
    tags = [StringConstants.PROJECT.format(project_id)]
    all_notebooks = fetch_notebooks(tags)

    # fetch scheduled notebooks
    response_json = []

    list_of_files, code = View(project_id=project_id).list_repo(repo=repo_name, file_path=path)
    log.debug("List of all files from git repo=%s", list_of_files)
    if code == 200:
        for component in list_of_files:

            # iterate over files returned by vcs
            nb_path = f"notebooks/{component['name']}"
            # pylint: disable=C0330
            if (
                component["name"].endswith(".ipynb")
                and ("notebooks" in path)
                and nb_path == component["path"]
            ):

                # placeholders
                is_in_db = False
                component["scheduled"] = False
                component["job_id"] = ""
                component["cron_expression"] = ""

                for notebook in all_notebooks:

                    # verify whether the file is present in database
                    if component["name"] == notebook["name"]:
                        is_in_db = True
                        component["id"] = notebook["id"]
                        component["last_updated_on"] = notebook["updated_on"]
                        component["icon"] = notebook["icon"]
                        component["kernel_type"] = notebook["kernel_type"]
                        component["image_tag"] = get_tag(
                            "type", notebook["tags"], split=True
                        )[1]
                        break

                # include file in response, if present in the database
                if is_in_db:
                    response_json.append(component)

            # process others
            elif component["name"] not in (".gitignore", "README.md", ".placeholder"):
                response_json.append(component)

    return jsonify(response_json)


@notebook_api.route("/v1/notebooks/running", methods=["GET"])
@swag_from("swags/running_v2.yaml")
def running_api():
    """ Get list of running notebooks per project per user"""

    # parse data

    tags = request.args.getlist("tags")
    project_tag = get_tag("project", tags)
    user = g.user["mosaicId"]

    # fetch notebooks
    log.debug(
        "Fetching running notebook with project_tag=%s user=%s", project_tag, user
    )
    notebooks = fetch_running_notebooks(project_tag, user)

    return jsonify(notebooks)


@notebook_api.route("/v1/templates/running", methods=["GET"])
@swag_from("swags/running_v2.yaml")
def running_api_template():
    """ Get list of running notebooks per project per user"""

    # parse data
    tags = request.args.getlist("tags")
    project_tag = get_tag("project", tags)
    user = g.user["mosaicId"]
    _, project = get_tag("project", tags, split=True)
    # fetch notebooks
    log.debug(
        "Fetching running notebook with project_tag=%s user=%s", project_tag, user
    )
    notebooks = fetch_running_template(project_tag, project, user)

    return jsonify(notebooks)


# pylint: disable=line-too-long
@notebook_api.route(
    "/v1/notebooks/<string:project_name>/<string:project_id>/<string:notebook_name>/history",
    methods=["GET"],
)
@swag_from("swags/history.yaml")
def get_history_link(project_name, project_id, notebook_name):
    """
    Fetch the history link for given notebook
    :param project_name:
    :param project_id:
    :param notebook_name:
    :return:
    """
    # entry log to add project id to log hander
    # log.add_attr({Constants.PROJECT_ID_KEY: str(project_id)})

    # git_server_url = app.config["VCS_BASE_URL"]
    repo_name = create_repo_name(project_name, project_id)
    # request_url = VcsURL.INFO_URL.format(git_server_url)
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"],
    # )
    # response = requests.get(request_url, headers=headers)

    # Get notebook type from notebook tags
    notebook = read_notebook_by_name(notebook_name)
    _, notebook_type = get_tag("type", notebook["tags"], split=True)
    return SchedulerURL.RESPONSE.format('{}/{}'.format(app.config["GIT_PUBLIC_URL"], app.config["GIT_NAMESPACE"]),
                                        repo_name, notebook_name)


@notebook_api.route(
    "/v1/notebooks/execute-schedule", defaults={"path": "notebooks"}, methods=["POST"]
)
@swag_from("swags/execute_scheduled_jobs.yaml")
# pylint: disable=unused-argument
def execute_scheduled_notebook(path):
    """
      API to execute scheduled notebook
      :return:
    """
    try:
        kc_access = request.cookies.get("kc-access")
        ex_data = request.get_json()
        log.debug("request args %s", request.args)
        log.debug("request json %s", ex_data)

        # Get active repo if repo and branch id is not present in the payload
        repo_id = ex_data.get('repo_id', None)
        branch_name = ex_data.get('branch_name', None)
        if repo_id:
            enabled_repo = get_git_repo(repo_id)
            enabled_repo['branch'] = branch_name if branch_name else enabled_repo['branch']
        else:
            # get enabled repo
            enabled_repo = list_git_repo(g.user["project_id"], RepoStatus.Enabled)
        if not enabled_repo:
            return ErrorCodes.ERROR_0011, 403
        # Escape sequence spaces in case space present in file path
        ex_data['file_path'] = ex_data['file_path'].replace(" ", r"\ ")
        ex_data["bearer_token"] = kc_access
        ex_data["enabled_repo"] = enabled_repo

        job_name = create_job_name(ex_data['file_path'], ex_data.get('instance_id', None))
        ex_data["job_name"] = job_name
        docker_image_details = DockerImage.query.get(ex_data["docker_image_id"])
        async_strategy = ExecuteNotebook.get_async_strategy(request, ex_data)
        async_execute_notebook(g.user, g.product_id, ex_data, async_strategy)

        response = {
            "jobName": job_name + '-driver' if docker_image_details.kernel_type == KernelType.spark_distributed else job_name,
            "applicationName": None,
            "message": "Success"
        }
        log.info("Response from execute_notebook %s", response)
        return jsonify(response), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.ERROR_0002, 500


@notebook_api.route(
    "/v1/notebooks/<uuid:notebook_id>/execschedule",
    defaults={"path": "notebooks"},
    methods=["GET", "POST"],
)
@swag_from("swags/create_schedule.yaml")
# pylint: disable=unused-argument
def execute_schedule(notebook_id, path):
    """
      API to schedule notebook
      :param notebook_id: UUID of the notebook
      :return:
    """
    # Fetching data
    notebook_id = str(notebook_id)
    log.error(notebook_id)
    data = request.get_json(silent=True)
    if data is None:
        data = {}

    if "async" not in request.args:
        async_strategy = False
    else:
        async_strategy = request.args["async"]
        if async_strategy in ["True", "true"]:
            async_strategy = True
        elif async_strategy in ["False", "false"]:
            async_strategy = False
        else:
            raise ValueError("Parameter async need to be boolean !")

    notebook_details = Notebook.query.get(notebook_id)
    docker_image_details = DockerImage.query.get(notebook_details.docker_image_id)
    log.error(docker_image_details.kernel_type)

    # Fetching PIP packages and Init-Script for installing in the Scheduled
    # container
    pip_packages_list = docker_image_details.pip_packages
    init_script = docker_image_details.init_script
    docker_url = docker_image_details.docker_url
    resource_id = docker_image_details.resource_id

    # Fetching Resource details for the fetched docker image
    resources = Resource.query.get(resource_id)

    # Fetching Project Name and Id
    notebook_tags = []
    for tag in notebook_details.tags:
        notebook_tags.append(tag.tag)

    _, project_id = get_tag_val("project", notebook_tags)
    _, project_name = get_tag_val("label", notebook_tags)

    # Creating repo name
    repo_name = create_repo_name(project_name, project_id)

    log.error(repo_name)
    log.debug(repo_name)

    payload = {
        "notebook_id": notebook_id,
        "notebook_name": notebook_details.name,
        "pip_packages": pip_packages_list,
        "repo_name": project_id,
        "init_script": init_script,
        "kernel_type": docker_image_details.kernel_type,
        "async": async_strategy,
        "docker_url": docker_url,
        "cpu": resources.cpu,
        "memory": resources.mem,
    }
    # Preparing URL
    url = app.config["MOSAIC_KUBESPAWNER_URL"]
    headers = generate_headers(
        userid=g.user["mosaicId"],
        email=g.user["email_address"],
        username=g.user["first_name"],
        project_id=project_id,
    )
    # call to create token
    log.debug("Call to create token")
    jwt = create_token()
    env_variables=get_envs(notebook_id, jwt, headers, project_id=project_id)
    env_variables["PROJECT_ID"] = project_id
    env_variables["PROJECT_NAME"] = project_name
    # for scheduler backend url is different because scheduler is in
    # different namespace
    env_variables["MOSAIC_AI_SERVER"] = app.config["MOSAIC_AI_SERVER_SCHEDULER"]
    env_variables["MOSAIC_ID"] = g.user["mosaicId"]
    env_variables["REPO_NAME"] = repo_name
    env_variables.update(data)
    payload["env"] = env_variables
    response = requests.post(url, json=payload, headers=headers)
    log.debug(response)
    response_job = response.text
    log.debug(response_job)
    return response_job


@notebook_api.route(
    "/v1/notebooks/update/content/<string:notebook_name>", methods=["PUT"]
)
@swag_from("swags/update.yaml")
def update_content_api(notebook_name):
    """
    API to change the updated_on of notebook
    :param notebook_name:
    :return:
    """

    # parse data
    tags = request.args.getlist("tags")
    _, project_tag = get_tag_val("repo-name", tags)

    # update notebook
    log.debug("Updating exiting notebook name")
    change_the_updated_time_for_notebook(notebook_name, project_tag)
    return Response(status=200)


@notebook_api.route("/v1/notebooks/summary/<string:project_id>", methods=["GET"])
def notebooks_metrics_summary(project_id):
    """ Notebooks metrics summary method """
    project_tag = "project=" + project_id
    servers = fetch_running_notebooks_for_metrics(project_tag)
    pod_metrics = []
    # pylint: disable=unused-variable
    for key, value in servers.items():
        for pod, data in value.items():
            fetched_pod_metrics = pod_metrics_summary.fetch_pod_metrics(
                data["pod_name"], app.config["NAMESPACE"], data["user_name"]
            )
            pod_metrics.append({data["pod_name"]: fetched_pod_metrics})
    return jsonify(pod_metrics)


@notebook_api.route("/v1/notebooks/running/all", methods=["GET"])
@swag_from("swags/running_v2.yaml")
def list_running_api():
    """ Get list of running notebooks per project per project"""

    # parse data
    tags = request.args.getlist("tags")
    project_tag = get_tag("project", tags)

    # fetch notebooks
    log.debug("Fetching running notbook with project_tag=%s", project_tag)
    notebooks = fetch_running_notebooks(project_tag)

    return jsonify(notebooks)


@notebook_api.route("/v1/templates/running/all", methods=["GET"])
@swag_from("swags/running_templates.yaml")
def list_running_templates():
    """ Get list of running notebooks per project per project"""

    # parse data
    tags = request.args.getlist("tags")
    project_tag = get_tag("project", tags)
    _, project = get_tag("project", tags, split=True)
    # fetch notebooks
    log.debug("Fetching running notbook with project_tag=%s", project_tag)
    notebooks = fetch_running_template(project_tag, project)

    return jsonify(notebooks)


@notebook_api.route("/v1/stop/notebooks/<string:project_id>", methods=["DELETE"])
@swag_from("swags/stop_notebooks_by_project_id.yaml")
def stop_notebooks_by_project_id(project_id):
    """Stop notebooks by project id method"""
    project_id = "project=" + str(project_id)
    list_of_running_notebooks = fetch_running_notebooks(project_id)["Notebooks"]
    # pylint: disable=unused-variable
    for idx, val in enumerate(list_of_running_notebooks):
        stop_by_id_using_project_id(list_of_running_notebooks[idx])

    # send response
    return Response(status=200)


@notebook_api.route("/v1/stop/templates/<string:project_id>", methods=["DELETE"])
@swag_from("swags/stop_templates_by_project_id.yaml")
def stop_templates_by_project_id(project_id):
    """Stop template by project id"""
    project_tag = "project=" + str(project_id)
    list_of_running_templates = fetch_running_template(project_tag, project_id)[
        "templates"
    ]

    for i in list_of_running_templates:
        stop_by_id_template(i)

    # send response
    return Response(status=200)


@notebook_api.route("/v1/notebooks/upload", methods=["POST"])
@swag_from("swags/upload.yaml")
def upload_api():
    """
    API to upload folder or file
    """
    try:
        temp_dir = (
            request.form["temp_dir"].strip() if "temp_dir" in request.form else None
        )
        if "tar_file" not in request.files and not temp_dir:
            raise Exception("Please upload a valid file/folder")
        file = request.files.get("tar_file")
        upload_path = (
            request.form["path"].strip() if "path" in request.form else ""
        )
        tags = (
            json.loads(request.form["tags"].strip()) if "tags" in request.form else None
        )
        commit_message = (
            request.form["commit_message"].strip()
            if "commit_message" in request.form
            else "Folder/File upload"
        )
        _, project = get_tag("project", tags, split=True)

        response, temp_dir = vcs_upload(temp_dir, file, project, commit_message, upload_path)
        return jsonify(message=response, temp_path=temp_dir)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


def vcs_upload(temp_dir, file, project, commit_message, upload_path):
    """
    :param temp_dir:
    :param file:
    :param project:
    :param commit_message:
    :param upload_path
    :return:
    """
    try:
        # headers = generate_headers(
        #     userid=g.user["mosaicId"],
        #     email=g.user["email_address"],
        #     username=g.user["first_name"],
        # )

        commit_message_payload = {}
        if commit_message:
            commit_message_payload = {"commit_message": commit_message}

        data = {"upload_path": upload_path}
        data.update(commit_message_payload)
        if not temp_dir:
            temp_file = tempfile.mkdtemp()
            response, temp_dir = View(project_id=g.user["project_id"]).upload_folder(repo=project, file=file, upload_path=upload_path, notebook_id=None, commit_message=commit_message)
            if os.path.isdir(temp_file):
                shutil.rmtree(temp_file)
        else:
            payload = {"temp_dir": temp_dir}
            payload.update(commit_message_payload)
            response, temp_dir = View(project_id=g.user["project_id"])._git_upload(repo=project, temp_dir=temp_dir, ignore_duplicate=True, path=None, commit_message=commit_message, upload_path="", data=payload)
        return response, temp_dir
    # pylint: disable=broad-except
    except MosaicException as ex:
        log.exception(ex)
        temp_dir_final = g.temp_dir if hasattr(g, 'temp_dir') else temp_dir
        return ex.message_dict().get("message"), temp_dir_final
    except Exception as ex:
        log.exception(ex)
        temp_dir_final = g.temp_dir if hasattr(g, 'temp_dir') else temp_dir
        return ex.args[0], temp_dir_final


@notebook_api.route("/v1/read-file/<path:file_path>", methods=["GET"])
@swag_from("swags/convert_git_file_to_html.yaml")
def read_git_file(file_path):
    """
    :param file_path:
    :input ref
    ref (str): branch to be checked or commit_id
    if commit_id is provided use commit_id else use branch as master default ref value
    :return: it will return the html file of request file content at particular commit_id
    if ref is master , it will return the html file of request file content at latest commit
    """

    try:
        enabled_repo = list_git_repo(g.user["project_id"], RepoStatus.Enabled)
        if not enabled_repo:
            return ErrorCodes.ERROR_0011, 403
        ref = request.args.get("commit_id", enabled_repo['branch'])
        commit_type = request.args.get("commit_id", False)
        if commit_type:
            commit_type = True
        response, code = View(repo_details=enabled_repo).read_file(repo=g.user["project_id"], file_path=file_path, branch=ref, commit=None, raw_content=False, commit_type=commit_type)
        if code == 403:
            return jsonify({"message": "Repository authentication failed"}), 403, {'Content-Type': 'application/json'}
        if code != 200:
            raise Exception(response)
        html_exporter = HtmlGenerator(
            response["content"], os.path.splitext(file_path)[-1].lower()
        )
        value = html_exporter.convert_file_to_html()
        return value
    except Exception as ex:
        raise Exception(ex.args[0] + "file not found in git")


@notebook_api.route("/v1/read-html",methods=["GET"])
@swag_from("swags/read_html_file.yaml")
def get_html_file():
    """Get html file method"""
    try:
        file_path = request.args.get('file_path')
        complete_path = f'{get_base_path("")}{file_path}'
        if os.path.exists(f"{complete_path}"):
            with open(complete_path, "r") as html_file:
                return html_file.read()
        else:
            return "No such file found ! Kindly try again with a valid file path.", 400
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/trigger_recipe", methods=["POST"])
def trigger_recipe():
    """ Method to receive call from Automl worker to trigger recipes"""
    try:
        payload = request.get_json()
        recipe_project_id = app.config["RECIPE_PROJECT_ID"]
        enabled_repo = list_git_repo(recipe_project_id, RepoStatus.Enabled)
        if not enabled_repo:
            return ErrorCodes.ERROR_0011, 403
        # Temporary code to test. Remove once new Automl backend is ready
        #if "project_id" in payload.keys():
        #    recipe_project_id = payload["project_id"]

        # For given recipe collect details like execution command , file path
        recipe_param = payload["recipe_param"]
        file_path = NotebookPath.nb_base_path + recipe_param["recipe_nb_name"]
        execution_command = get_execute_command_ipynb_to_py(kernel_type=KernelType.python, file_path=file_path)

        # creating payload for calling execute schedule
        execute_schedule_payload = {
            "docker_image_id": recipe_param["recipe_template_id"],
            "execution_command": execution_command,
            "file_path": file_path,
            "recipe_project_id": recipe_project_id,
            "project_id": g.user['project_id'],
            "resource_id": payload["resource_id"],
            "async": True,
            "enabled_repo": enabled_repo,
            "input": "default",
            "output": "default",
            "job_name": create_job_name(file_path)
        }

        # creating input params that will be set as environment variable in NB
        # adding a flag automl with true value to differentiate the flow
        input_params = {
            "experiment_id": payload["id"],
            "experiment_recipe_id": payload["experiment_recipe_id"],
            "dataset_name": payload["base_dataset_name"],
            "additional_dataset_params": json.dumps(payload["additional_dataset_params"]),
            "upload_from_catalog": str(payload["upload_from_catalog"]),
            "feature_column": payload["feature_column"],
            "target_column": payload["target_column"],
            "experiment_style": payload["experiment_style"],
            "experiment_type": payload["experiment_type"],
            "experiment_name": payload["experiment_name"],
            #"experiment_description": payload["experiment_description"],
            "auto_ml_trigger": True  # actual Recipe_id
        }

        # creating recipe params to be passed in input params if experiment style is manual
        if payload["experiment_style"] == ExperimentStyles.manual:
            input_params["recipe_param"] = payload["recipe_param"]["params"]

        # creating recipe params to be passed in input params if experiment style is quick
        if payload["experiment_style"] == ExperimentStyles.quick:
            input_params["recipe_param"] = payload["recipe_param"]["recipe_quick_run_params"]

        # update execute_schedule_payload with input params created
        execute_schedule_payload["input_params"] = input_params

        # Call execute schedule for recipe

        execute_schedule_payload.update({"bearer_token": payload["bearer_token"]})
        async_strategy = ExecuteNotebook.get_async_strategy(request, execute_schedule_payload)

        execute_notebook = ExecuteNotebook(g.user, execute_schedule_payload, async_strategy)
        response = execute_notebook.execute_notebook()
        if response["message"] == "Failed":
            job_status = "failed"
            return jsonify({
                "job_name": response["jobName"],
                "job_status": job_status,
                "snapshot_name": response["snapshot_name"]
            }), 201

        return jsonify({
                        "job_name": response["jobName"],
                        "snapshot_name": response["snapshot_name"]
        }), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return ErrorCodes.MOSAIC_0009, 500


#pylint: disable=too-many-arguments
def create_k8_resources_byoc(project_id, pod_name, docker_url, port, cmd, argument,
                             pod_resources, env, ingress_url, commit_type,
                             kernel_type, cran_packages, pip_packages, conda_packages, init_script,
                             node_affinity_options, enabled_repo, snapshots, metering_info, git_macros_config, user_imp_data, project_details, version
                             ):
    """ Method to create k8 resources using kubespawner """
    # creating empty folder if it doesnot exist on nfs drive
    try:
        headers = {
            'X-Auth-Userid': g.user["mosaicId"],
            'X-Auth-Email': g.user["email_address"],
            'X-Auth-Username': g.user["first_name"],
            'X-Project-Id': g.user["project_id"],
            'access': "True"
        }

        project_quota = convert_into_bytes(project_details['resourceQuota'])
        consumed_quota = get_project_resource_quota \
            (project_id, app.config["CONSOLE_BACKEND_URL"], headers, False)

        resource_quota_full = bool(project_quota < consumed_quota)

        pod_name = pod_name.replace("@", "")
        envs = []
        if env:
            for key, val in clean_env_variables(env).items():
                env_dict = {"name": key, "value": val}
                envs.append(env_dict)
        create_k8_pod(pod_name, docker_url, port, pod_resources, cmd, argument, envs, project_id, commit_type,
                      kernel_type, cran_packages, pip_packages, conda_packages, init_script, node_affinity_options,
                      enabled_repo, snapshots, metering_info, git_macros_config, resource_quota_full, env,
                      user_imp_data, version)
        return True
    except MosaicException as ex:
        log.exception(ex)
        raise ex
    except Exception as ex:
        log.exception(ex)
        raise CreateK8ResourceBYOCException

# pylint: disable=too-many-branches
def start_template_new(notebook, enabled_repo, register_condition):

    """ Method to start notebook """
    # prepare url
    try:
        user_id = g.user["mosaicId"]
        commit_type = notebook.get('auto_commit')
        notebook_id = notebook["docker_image"]["id"]
        _, project = get_tag("project", notebook["tags"], split=True)
        hub_auth_token = app.config["HUB_AUTH_TOKEN"]
        node_affinity_options = prepare_node_affinity_options()
        kernel_type = notebook.get("docker_image").get("kernel_type")
        cran_packages = notebook.get("docker_image").get("cran_packages")
        pip_packages = notebook.get("docker_image").get("pip_packages")
        conda_packages = notebook.get("docker_image").get("conda_packages")
        init_script = notebook.get("docker_image").get("init_script")
        git_macros_config = notebook.get("docker_image").get("git_macros_config")
        # prepare headers
        request_headers = {
                "Authorization": StringConstants.TOKEN.format(hub_auth_token),
                Headers.x_auth_username: g.user["first_name"],
                Headers.x_auth_email: g.user["email_address"],
                Headers.x_auth_userid: g.user["mosaicId"],
        }
        jwt = create_token()
        log.debug("Creating pod for notebook=%s", notebook_id)
        project_tag = get_tag("project", notebook["tags"])
        _, notebook_type = get_tag("type", notebook["tags"], split=True)

        base_image_id = notebook["docker_image"].get("base_image_id") or notebook["docker_image"]["id"]
        version = base_version_tag(base_image_id)
        env = get_envs(notebook["docker_image"]["id"], jwt, request_headers, project_id=project_tag.split("=")[1])
        env["NOTEBOOK_NAME"] = notebook["docker_image"]["name"]
        env["knights_watch_commit_message"] = notebook.get("commit_message") if notebook.get("commit_message") else None
        env["knights_watch_jira_id"] = notebook.get("jira_id", None)
        env["cull_idle_in_minutes"] = notebook.get("cull_idle_in_minutes", None)
        # pylint: disable=literal-comparison

        log.debug(jsonify(notebook).get_json())
        # prepare spawner options
        options = {
            "git_repo": project,
            "notebook": jsonify(notebook).get_json(),
            "user": g.user,
            "environment_variables": env,
            "init_script": init_script,
            "node_affinity_options": node_affinity_options
        }
        # fetch the running notebooks for user
        running_notebooks = fetch_running_template(project_tag, project, user_id)
        # check whether the notebook server is running
        if notebook_id not in [x["id"] for x in running_notebooks["servers"].values()]:
            # check qouta
            check_quota_for_user_template(project_tag, project, user_id, running_notebooks)
            # create pod in db
            notebook_pod = register_template_status(
                notebook, user_id, PodStatus.STARTING, project, enabled_repo
            )
            # create pod name with template status id instead of template id
            template_project = notebook_pod.id
            # fetch subscriber info
            template_status_id = notebook_pod.id
            log.error("Subscription Resource Request")
            resource_key, resource_request = fetch_resource_info(notebook.get('resource').get('extra'), notebook.get('resource').get('cpu'))
            log.error(resource_key)
            log.error(resource_request)
            requested_usage = {resource_key: resource_request}
            log.error(g.product_id)
            try:
                pod_name = create_pod_name(project, user_id, template_project, notebook_type, notebook.get('spcs_data'))
                # removing @ as after spawning the notebook in k8s, @ is automatically removed
                # syncing pod name in db with spawned notebook
                revised_pod_name = pod_name.replace("@", "")
                subscriber_info = get_subscriber_info(user_id, resource_key, g.product_id)
                log.error(subscriber_info)
                # create new entry for resource requested for metering
                log.error(requested_usage)
                validate_subscriber_info(subscriber_info)
                notebook_name = notebook["docker_image"]["name"]
                log.error(notebook_name)
                metering_info = {"user_id": user_id, "resource_key": resource_key,
                                 "resource_request": resource_request, "pod_id": template_status_id,
                                 "description": notebook_name, "project_id": project,
                                 "subscriber_id": subscriber_info["subscriber_id"]}
                # Save pod name in DB
                update_template_status(notebook_pod, PodStatus.STARTING, revised_pod_name)
                options.update(pod_name=pod_name, template_project=template_project)
                # use base_image_id always in case base_image_id is None use did from nb_docker_image table
                docker_id = notebook.get('docker_image_id') if notebook.get("docker_image").get("base_image_id") is None else notebook.get("docker_image").get("base_image_id")

                # Get base image name for custom template
                if notebook.get("docker_image").get("type") in ["PRE_BUILD", "PRE_BUILD_SPCS"]:
                    docker_image_name = notebook.get('docker_image').get('name')
                    base_image_details = None
                elif notebook.get("docker_image").get("type") in ["CUSTOM_BUILD", "CUSTOM_BUILD_SPCS"]:
                    base_image_details = fetch_base_image_details_for_custom_build(notebook.get("docker_image").get("base_image_id"))
                    docker_image_name = base_image_details.get('name')
                port, cmd, argument, base_url_env_key, base_url_env_value, ingress_url, container_uid = fetch_extra_attribute_docker_image(
                    docker_id,
                    g.user.get('email_address'),
                    docker_image_name,
                    project,
                    template_project
                )
                env["user_id"] = container_uid

                #Set Base Image Operating System
                env["os"] = get_base_image_os(docker_id)
                # tags = fetch_tags(docker_id)
                # os_key, os_val = get_tag_val("os", tags)
                # log.debug('#THE OS IS : %s', os_val)
                # env["os"] = os_val if os_val else ""

                if base_url_env_value:
                    env[base_url_env_key] = base_url_env_value

                if docker_image_name and docker_image_name.lower() == "sas":
                    env['SERVER_CONTEXT_PATH'] = base_url_env_value
                    env[base_url_env_key] = base_url_env_value
                    env['SERVER_PORT'] = app.config["SAS_SERVER_PORT"]
                    env['DEPLOYMENT_NAME'] = app.config["DEPLOYMENT_NAME"]
                    env['RUN_MODE'] = app.config['RUN_MODE']
                    env['java_global_option_sas_commons_web_security_cors_allowedOrigins'] = "-Dsas.commons.web.security.cors.allowedOrigins=https://{0}".format(app.config["DEFAULT_HOST"])
                    env['java_global_option_server_servlet_session_timeout'] = "-Dserver.servlet.session.timeout={0}".format(app.config["SAS_SESSION_TIMEOUT_IN_MINUTES"])
                    env['SASDEMO_HOME'] = NotebookPath.nb_base_path
                    # sas working directory to save temporary session files
                    env['SAS_WORDIR'] = app.config.get("SAS_TMP_WORDIR", "/output") + "/sas_tmp/" + notebook["docker_image"]["id"]

                user_imp_data = None
                query_set = db.session \
                    .query(DockerImage) \
                    .filter(DockerImage.type == 'PRE_BUILD') \
                    .all()
                template_name_list = []
                for result in query_set:
                    base_temp_name = result.as_dict().get("name", "")
                    template_name_list.append(base_temp_name)
                if docker_image_name and docker_image_name.lower() in map(str.lower, template_name_list):
                    # Disable user personification for spark 36 and spark 38
                    # get user_impersonation flag from config
                    user_impersonation = app.config['USER_IMPERSONATION_FLAG']
                    if user_impersonation:

                        env['USER_IMPERSONATION'] = "true"
                        env["NB_UMASK"] = app.config.get("USER_IMPERSONATION_UMASK", "0022")
                        env["READ_ONLY_ENV"] = app.config.get("READ_ONLY_ENV", "false")
                        env, user_imp_data = get_user_impersonation_details(g.user["mosaicId"], env)

                env["pod_name"] = pod_name.replace("@", "")
                env["template_id"] = notebook['docker_image']["id"]
                env["base_docker_image_name"] = docker_image_name if docker_image_name != "Spark Distributed" else "Python-3.6"
                env["DOCKER_REGISTRY"] = app.config.get("GIT_REGISTRY", "registry.lti-aiq.in:443")

                env["PROJECT_ID"] = project
                project_details = get_project_details(project)
                env["project_name"] = project_details.get("projectName")

                env["MOSAIC_AI_SERVER"] = app.config["MOSAIC_AI_SERVER"]
                env["R_PACKAGE_REPO"] = app.config["R_PACKAGE_REPO"]
                env["PYPI_PACKAGE_REPO"] = app.config["PYPI_URL"]
                env["CONDA_PACKAGE_REPO"] = app.config["CONDA_PYTHON_URL"]
                env["CONDA_R_PACKAGE_REPO"] = app.config["CONDA_R_URL"]

                if app.config['ARTIFACTORY']:
                    env["ARTIFACTORY"] = "true"

                env["NOTEBOOKS_API_SERVER"] = app.config["NOTEBOOKS_API_SERVER_URL"]
                env["MOSAIC_ID"] = g.user["mosaicId"]

                env["repo_id"] = enabled_repo['repo_id']
                env["repo_name"] = enabled_repo['repo_name']
                env["branch_name"] = enabled_repo['branch']
                env["EXPERIMENT_NAME"] = notebook.get("experiment_name")
                env["EXPERIMENT_DETAILS"] = json.dumps(notebook.get("experiment_details"))
                env["MLFLOW_TRACKING_URL"] = app.config.get("MLFLOW_TRACKING_URL", "http://mlflow-server")

                env["BASE_URL"] = ingress_url
                if register_condition:
                    if notebook['output'] == KernelType.default:
                        notebook["output"] = KernelType.snapshot + notebook_pod.id
                    if notebook['input'] == KernelType.slash:
                        notebook["input"] = KernelType.input
                    if notebook['input'] == KernelType.default:
                        notebook["input"] = KernelType.snapshot + notebook_pod.id
                    snapshots = {}
                    snapshots["input"] = notebook['input']
                    snapshots["output"] = notebook['output']
                else:
                    snapshots = None

                if docker_image_name and docker_image_name.lower() == "rstudio-4":
                    env["DISABLE_AUTH"] = "true"

                pod_limit_resources, pod_request_resource, docker_url = get_resource_details(notebook, "resource")
                log.info(f"pod_limit_resources: {pod_limit_resources} pod_request_resource: {pod_request_resource}"
                         f" docker_url: {docker_url}")

                if kernel_type == KernelType.spark_distributed:
                    # Getting resource details for spark executor pod.
                    exec_pod_limit_resources, exec_pod_request_resource, _ = get_resource_details(
                        notebook, "executor_resource")
                    log.info(f"exec_pod_limit_resources: {exec_pod_limit_resources} "
                             f"exec_pod_request_resource: {exec_pod_request_resource}")
                    log.info(f"Adding environment variable for spark_distributed template")
                    env["executor_request_memory"] = exec_pod_request_resource.get("memory")
                    env["executor_request_cpu"] = exec_pod_request_resource.get("cpu")
                    env["executor_limit_memory"] = exec_pod_limit_resources.get("memory")
                    env["executor_limit_cpu"] = exec_pod_limit_resources.get("cpu")
                    env["executor_pod_image"] = notebook.get('docker_image').get('gpu_docker_url')
                    env["number_of_executors"] = str(notebook.get('docker_image').get('number_of_executors'))
                    env["MINIO_DATA_BUCKET"] = app.config['MINIO_DATA_BUCKET']
                    env["NAMESPACE"] = app.config["NAMESPACE"]

                log.debug("validating if output snapshot exists or not")
                # create data and snapshot path if not present
                data_path = get_base_path(project_id=project, exp_name=notebook.get("experiment_name", None))
                check_and_create_directory(data_path)
                if register_condition:
                    snaphot_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
                        'MINIO_DATA_BUCKET'] + "/" + f'{project}/{project}-Snapshot/{notebook["output"]}/'
                    check_and_create_directory(snaphot_path)

                env["log_id"] = env["pod_name"]
                log_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
                    'MINIO_DATA_BUCKET'] + "/" + "/log/" + f'{project}' + "/" + env["log_id"] + "/"
                check_and_create_log_directory(log_path)
                env["LOG_DIRECTORY"] = app.config["LOG_DIRECTORY"]


                pod_resources = {
                    "limits": pod_limit_resources,
                    "requests": pod_request_resource,
                    "actual":  {"cpu": notebook.get('resource').get("cpu"), "mem": notebook.get('resource').get("mem")},
                }

                if notebook.get('spcs_data'):
                    repo_url = git_details.create_remote_url(enabled_repo)
                    if enabled_repo['branch'] not in ['', None, ' ', "null"]:
                        repo_url = repo_url + f" -b {enabled_repo['branch']}"
                    env['REPO'] = repo_url
                    success = create_spcs_service(notebook['spcs_data'], notebook['launch_docker_image'],
                                                  pod_name, env)
                else:
                    success = create_k8_resources_byoc(project,
                                                       pod_name,
                                                       docker_url,
                                                       port,
                                                       cmd,
                                                       argument,
                                                       pod_resources,
                                                       env,
                                                       ingress_url,
                                                       commit_type,
                                                       kernel_type,
                                                       cran_packages,
                                                       pip_packages,
                                                       conda_packages,
                                                       init_script,
                                                       node_affinity_options,
                                                       enabled_repo,
                                                       snapshots,
                                                       metering_info, git_macros_config, user_imp_data, project_details, version)
                # call kubespawner to create k8 resources for knights-watch
                if success:
                    # update pod status in db
                    update_template_status(notebook_pod, PodStatus.RUNNING, revised_pod_name)
                    notebook["container_object"] = {"name": revised_pod_name}
                    if register_condition:
                        register_snapshot(notebook, user_id, project, enabled_repo)
                        # committing to database as entire execution has completed successfully
                        db.session.commit()
                else:
                    # update pod status in db
                    update_template_status(notebook_pod, PodStatus.STOPPING, revised_pod_name)
                    # pylint: disable=broad-except
            except MosaicException as ex:
                db.session.rollback()
                log.exception(ex)
                update_template_status(notebook_pod, PodStatus.STOPPING, revised_pod_name)
                raise ex
            except Exception as ex:
                # rolling back the transaction on failure
                db.session.rollback()
                log.exception(ex)
                update_template_status(notebook_pod, PodStatus.STOPPING, revised_pod_name)
                raise SpawningError
        if notebook.get('spcs_data'):
            return "", "", "", pod_name, "", success

        progress_url = "/notebooks/api/v1/spawner/progress/pod-name/{0}?port_no={1}&ingress_url={2}&kernel_type={3}".format(
            pod_name, port, ingress_url, kernel_type)
        ingress_url = ingress_url + 'lab' if "Jupyterlab" in ingress_url else ingress_url
        terminal_url = ""
        return ingress_url, progress_url, terminal_url, pod_name, port, success
    except MosaicException as ex:
        log.exception(ex)
        raise ex
    except Exception as e:
        log.exception(e)
        raise SpawningError


@notebook_api.route("/v1/git-repo", methods=["POST"])
@swag_from("swags/add_git_repo.yaml")
def create_repo():
    """
    Method will take Repository details from user and store it in git_repo table
    Returns:

    """
    try:
        payload = git_details.decode_password(request.get_json(), RepoAccessCategory.PRIVATE)
        response, resp_code = add_git_repo(payload, g.user["project_id"])
        return response, resp_code
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo", methods=["GET"])
@swag_from("swags/list_git_repo.yaml")
def get_repo():
    """
    Method will list all repository based on project id
    Returns: list

    """
    try:
        if "branches" not in request.args:
            remote_branches = True
        else:
            remote_branches = request.args.get("branches", True)
            if remote_branches in ["True", "true"]:
                remote_branches = True
            elif remote_branches in ["False", "false"]:
                remote_branches = False
            else:
                raise ValueError("Parameter branches need to be boolean !")

        response = list_git_repo(g.user["project_id"], remote_branches=remote_branches)
        return jsonify(response)
    # pylint: disable=broad-except
    except MosaicException as ex:
        log.exception(ex)
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo/<string:repo_id>", methods=["DELETE"])
@swag_from("swags/delete_git_repo.yaml")
def delete_repo(repo_id):
    """
    Method will delete Git repository which is not enabled.
    Args:
        repo_id: uuid

    Returns:

    """
    try:
        response = delete_git_repo(repo_id)
        return jsonify(response)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo/<string:repo_id>", methods=["PUT"])
@swag_from("swags/update_git_repo.yaml")
def update_repo(repo_id):
    """
    Method will update existing repository details
    Args:
        repo_id: uuid of Repository

    Returns:json

    """
    try:
        payload = git_details.decode_password(request.get_json(), RepoAccessCategory.PRIVATE)
        response, resp_code = update_git_repo(payload, repo_id)
        return response, resp_code
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo/<string:repo_status>", methods=["GET"])
def get_enabled_repo(repo_status):
    """
    Method will list enabled repository based on project id
    Returns: list
    """
    try:
        response = list_git_repo(g.user["project_id"], repo_status)
        return jsonify(response), 200

    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo-switch", methods=["PUT"])
@swag_from("swags/switch_git_repo.yaml")
def switch_repo():
    """
    Method will switch between users enabled repo
    """
    try:
        payload = request.get_json()
        response = switch_git_repo(g.user["project_id"], payload)
        return jsonify(response)
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-repo-by-id/<string:repo_id>", methods=["GET"])
#@swag_from("swags/get_git_repo.yaml")
def get_repo_by_id(repo_id):
    """
    Method Fetches the requested git repo by id.
    Args:
        repo_id: uuid
    Returns:
    """
    try:
        response = get_git_repo(repo_id)
        return jsonify(response), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/ingress-auth/<string:pod_name>/<string:hashed_user_id>", methods=["GET"])
@swag_from("swags/ingress_url_auth.yaml")
def validate_ingress_url_user(pod_name, hashed_user_id):
    """
    API to validate user against ingress url
    """
    try:
        log.debug("Ingress URL Authentication Started")
        user_id_header = request.headers.get(Headers.x_auth_userid, None)
        hashed_user_id_header = hash_username(user_id_header)
        if hashed_user_id_header == hashed_user_id:
            log.debug("Ingress validation passed for user:%s and pod:%s", user_id_header, pod_name)
            return Response("Authorized"), 200
        log.exception("Ingress validation failed for user:%s and pod:%s", user_id_header, pod_name)
        return Response("UnAuthorized"), 401
    except Exception as ex:
        log.exception(ex)
        # In case of exception do we need to show internal error or unauthorized
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/git-branches", methods=["PUT"])
@swag_from("swags/update_branches.yaml")
def update_branches():
    """
    Method will take the list of branch objects to be updated in database
    Returns:
    """
    try:
        payload = request.get_json()
        update_branch_metadata(payload)
        return "SUCCESS"
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args, status=400)


@notebook_api.route("/v1/git-enabled-repo", methods=["GET"])
@swag_from("swags/get_enabled_git_repo.yaml")
def get_enabled_git_repo():
    """
    Method will list enabled repository based on project id
    Returns: list
    """
    try:
        response = list_git_repo(g.user["project_id"], "Enabled")
        if response:
            response["password"] = ""
        return jsonify(response), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/notebooks-report", methods=["POST"])
@swag_from("swags/notebooks_report.yaml")
def notebooks_report():
    """
    Method will download the report for notebooks utilisation
    Returns: file
    """
    try:
        payload = request.get_json()
        temp_dir, file_name = download_report(payload)

        return send_from_directory(temp_dir, file_name, as_attachment=True)
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/init-git-repo", methods=["POST"])
@swag_from("swags/init_git_repo.yaml")
def init_git_repo():
    """
    API Initializes a git repository with default method
    """
    try:
        payload = git_details.decode_password(request.get_json(), RepoAccessCategory.PRIVATE)
        response, resp_code = init_empty_git_repo(payload)
        return response, resp_code
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/list-git-branches", methods=["POST"])
@swag_from("swags/list_git_branches.yaml")
def list_branches():
    """
    This API fetches the active list of git branches
    """
    try:
        payload = git_details.decode_password(request.get_json(), RepoAccessCategory.PRIVATE)
        res = fetch_git_branches(payload)
        return jsonify(res)
    # pylint: disable=broad-except
    except MosaicException as ex:
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/list-repo-branches/<string:repo_id>", methods=["GET"])
def list_all_branches(repo_id):
    """
    API to fetch all branches of a repository
    Args:
        repo_id (str): repo id saved in database

    Returns: list of all branches

    """
    try:
        branch_list = get_all_branches(repo_id)
        response = {"branches": branch_list}
        return jsonify(response)
    except Exception as ex:
        log.exception(ex)
        return jsonify(ex.args[0]), 500


@notebook_api.route("/v1/pods/trigger_alerts", methods=["POST"])
@swag_from("swags/trigger_alerts.yaml")
def trigger_alerts():
    """
    This api recives the alerts payload coming from the alert manager and it
    parses the alerts data and seggregates alerts based on type of the resource
    If the alert is for cpu then it will be sent to trigger_cpu alerts or if the
    alerts are for the memory then it go to trigger_memory_alerts function
    This api returns the list of pod names to which cpu and memory will be sent
    """
    request_payload = request.get_json()
    alerts_received = request_payload.get("alerts", [])
    # List to store pods with utilization percentage
    cpu_pods_with_resource_details = [] 
    memory_pods_with_resource_details = []
    # List containing the pod names which are in running state
    running_pod_list = [x[0] for x in get_running_pods()]
    # List to store the pod names for cpu alerts
    cpu_pod_names = [] 
    memory_pod_names = []
    try:
        if alerts_received:
            for each_alert in alerts_received:
                pod_name = each_alert["labels"]["pod"]
                if pod_name not in running_pod_list:
                    continue
                utilization = each_alert["annotations"]["summary"]
                utilization_summary = utilization.split()
                usage_percent = round(float(utilization_summary[-1]), 2)
                if utilization_summary[0].lower() == 'cpu':
                    resource_type = 'cpu'
                    cpu_pod_names.append(pod_name)
                    cpu_pods_with_resource_details.append([pod_name, usage_percent, resource_type])
                else:
                    resource_type = 'memory'
                    memory_pod_names.append(pod_name)
                    memory_pods_with_resource_details.append([pod_name, usage_percent, resource_type])
            # calling CPU alerts function
            cpu_response = trigger_cpu_alerts(cpu_pod_names, cpu_pods_with_resource_details)
            # calling Memory alert function
            memory_response = trigger_memory_alerts(memory_pod_names, memory_pods_with_resource_details)
            return jsonify({'cpu_response': cpu_response , 'memory_response': memory_response}), 200
        else:
            return jsonify({'status':'No pods found in alert'}), 200
    except Exception as err:
        log.error(str(err))
        error_dict = {"status": "error", "message": str(err)}
        return jsonify(error_dict), 500


@notebook_api.route("v1/pods/get_pod_usage_details/<pod_name>")
@swag_from("swags/pod_usage_details.yaml")
def get_pod_usage_details(pod_name):
    """
    This api takes pod_name from the url and returns the resource
    usage details for the given pod from database table 
    """
    try:
        pod_data = fetch_pod_usage(pod_name)
        status = {"pod_name": pod_name, "cpu": 0, "memory": 0, "message": {'cpu':'', 'memory':''}}
        if len(pod_data) > 0:
            for pod_info in pod_data:
                if pod_info[0] == 'cpu':
                    status['cpu'] = pod_info[1]
                    if app.config["CPU_PERCENT_HIGH_THRESHOLD1"] <= float(pod_info[1]) < app.config["CPU_PERCENT_HIGH_THRESHOLD2"]:
                        status['message']['cpu'] =f'{app.config["CPU_MORE_THAN_80_PERCENT"]} {pod_info[2]} in {pod_info[3]} project'
                    elif float(pod_info[1]) >= app.config["CPU_PERCENT_HIGH_THRESHOLD2"]:
                        status['message']['cpu'] = f'{app.config["CPU_MORE_THAN_100_PERCENT"]} {pod_info[2]} in {pod_info[3]} project'
                elif pod_info[0] == 'memory':
                    status['memory'] = pod_info[1]
                    if app.config["MEMORY_PERCENT_HIGH_THRESHOLD1"] <= float(pod_info[1]) < app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]:
                        status['message']['memory'] = f'{app.config["MEMORY_PERCENT_HIGH_THRESHOLD1_MESSAGE"]} {pod_info[2]} in {pod_info[3]} project'
                    elif float(pod_info[1]) >= app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]:
                        status['message']['memory'] = f'{app.config["MEMORY_PERCENT_HIGH_THRESHOLD2_MESSAGE"]} {pod_info[2]} in {pod_info[3]} project'
        return jsonify(status)
    except Exception as err:
        log.error(err)
        return jsonify({"status": "fail", "message": err}, 500)


@notebook_api.route("/v1/notebooks/sample_exp_upload", methods=["POST"])
@swag_from("swags/sample_exp_upload.yaml")
def sample_exp_upload():
    """
    API to pick/create sample experiment notebook and upload it on repo.
    """
    try:
        request_payload = request.get_json()
        log.info(f"inside sample_exp_upload, request_payload: {request_payload}")

        exp_name = request_payload.get("experiment_name")
        exp_algo = request_payload.get('experiment_algorithm').lower()
        # headers = generate_headers(
        #     userid=g.user["mosaicId"],
        #     email=g.user["email_address"],
        #     username=g.user["first_name"],
        # )
        file_path = os.getcwd() + f"/notebooks_api/sample_experiments/{exp_algo}.ipynb"
        if os.path.exists(file_path):
            temp_file_dir = tempfile.mkdtemp()
            temp_file = shutil.copyfile(file_path, f"{temp_file_dir}/sample_{exp_name}.ipynb")
        else:
            log.error(f"{file_path} not found")
            raise Exception(f"sample experiment file not found for the selected algorithm {exp_algo}")
        commit_message = f"sample_{exp_name}.ipynb template upload"
        # git_server_url = app.config["VCS_BASE_URL"]
        # request_url = git_server_url + VcsURL.UPLOAD_FOLDER_URL.format(request_payload.get("project_id"))
        # files = {"file1": open(temp_file, "rb")}

        # response = requests.post(request_url, files=files, data=data, headers=headers)
        response, _ = View(project_id=g.user["project_id"])._git_upload(repo=request_payload.get("project_id"), temp_dir=temp_file_dir, commit_message=commit_message)

        if os.path.exists(temp_file):
            log.info(f"{exp_algo}.ipynb uploaded!")
            shutil.rmtree(temp_file_dir)
        return response
    except FileWithSameNameExists as ex:
        log.exception(ex)
        return jsonify(ExperimentWithSameNameException().message_dict()), ex.code
    except MosaicException as ex:
        log.exception(ex)
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        log.exception(ex)
        return Response(ex.args[0], status=400)


@notebook_api.route("/v1/notebooks/ml_algo_listing/<string:algo_type>", methods=["GET"])
@swag_from("swags/ml_algo_listing.yaml")
def ml_algo_listing(algo_type):
    """
    API to list mlflow supported algorithms
    Args:
        algo_type (str): TPOTRegressor or TPOTClassifier
    Returns: dict of all the supported algorithms along with hyper parameters
    """
    try:
        log.info(f"inside ml_algo_listing, algo_type: {algo_type}")
        if algo_type == "regressor":
            return jsonify(json.loads(app.config["REGRESSION_ALGO"]))
        elif algo_type == "classifier":
            return jsonify(json.loads(app.config["CLASSIFICATION_ALGO"]))
    # pylint: disable=broad-except
    except Exception as ex:
        log.exception(ex)
        return Response(ex, status=400)


@notebook_api.route("/v1/notebooks/remove_active_branch", methods=["DELETE"])
@swag_from("swags/delete_active_branch.yaml")
def delete():
    """Remove an active branch when changing users Project access from Owner to Validator"""
    data = request.get_json()
    if 'username' not in data or 'project_id' not in data:
        return jsonify({'message': 'Missing username or project_id in request'}), 400
    username = data['username']
    project_id = data['project_id']
    response = delete_active_repo_on_access_revoke(project_id, username)
    return jsonify(response)


