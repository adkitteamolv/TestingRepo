#! -*- coding: utf-8 -*-

""" Celery tasks associated with notebook module """
import json
import os

import logging
import nbformat
import requests
from flask import g, current_app

from mosaic_utils.ai.headers.utils import generate_headers
from mosaic_utils.ai.headers.constants import Headers

from notebooks_api import make_celery
from notebooks_api.notebook.manager import archive_notebook_pod
from notebooks_api.utils.project import create_repo_name
from notebooks_api.utils.mosaicnotebook_template import create_mosaicnotebook
# from notebooks_api import get_config
# from notebooks_api import get_application
from notebooks_api.spawner.manager import delete_pod
from notebooks_api.version_control.views import View
from .constants import VcsURL, SchedulerURL
from ..constants import MonitorStatus
from .job import ExecuteNotebook

# pylint: disable=invalid-name
# app = get_application()
# celery = make_celery(app=app)
# app_config = get_config()

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.notebook")


# pylint: disable=too-many-arguments
def create_notebook_in_git(
        name,
        project_id,
        label,
        notebook_id,
        notebook_type,
        notebook_content=None):
    """Method to create notebook in git"""
    # fetch params
    # git_server_url = current_app.config["VCS_BASE_URL"]
    if notebook_type == "jupyter":
        if not notebook_content:
            # create ipython notebook
            notebook_content = nbformat.v4.new_notebook()

    # Push notebook to git repo
    repo_name = create_repo_name(label, project_id)
    # request_url = git_server_url + VcsURL.UPLOAD_FOLDER_URL.format(repo_name)
    temp = open(name, 'w')
    json.dump(notebook_content, temp)
    temp.close()
    View(project_id=g.user["project_id"]).upload_folder(repo=repo_name, file=open(name, 'rb'), upload_path="", notebook_id=notebook_id, commit_message="Folder/File upload")
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"])
    # log.debug(headers)
    # log.error(headers)
    # files = {'file1': (name, open(name, 'rb'))}
    # response = requests.post(
    #     request_url,
    #     data=data,
    #     headers=headers,
    #     files=files)
    os.unlink(name)
    # response.raise_for_status()


# pylint: disable=unused-argument
def stop_notebook_pod(user, notebook, notebook_pod, project_id):
    """
    :param user:
    :param notebook:
    :param notebook_pod:
    :param project_id:
    :return:
    """

    # prepare url
    user_id = user["mosaicId"]
    hub_base_url = current_app.config["HUB_BASE_URL"]
    hub_auth_token = current_app.config["HUB_AUTH_TOKEN"]
    template_project = notebook_pod["id"]
    request_url = "{}/users/{}/servers/{}".format(
        hub_base_url, user_id, template_project)

    # prepare headers
    request_headers = {
        "Authorization": "Token {}".format(hub_auth_token),
        Headers.x_auth_username: user["first_name"],
        Headers.x_auth_email: user["email_address"],
        Headers.x_auth_userid: user["mosaicId"],
        Headers.x_project_id: project_id
    }

    # stop the container
    log.debug(f"Stopping the notebooks pod, by calling delete method on HUB_BASE_URL")
    response = requests.delete(request_url, headers=request_headers)
    # if the pod is in pending state and user clicks on stop pod from UI
    # response status code will be 400 so
    # Delete the pod from k8s cluster
    if response.status_code == 400 and notebook_pod['pod_name']:
        delete_pod(notebook_pod['pod_name'], current_app.config['KUBERNETES_NAMESPACE'])
    archive_notebook_pod(notebook_pod, project_id)

# pylint: disable=unused-argument
def async_execute_notebook(user, product_id, ex_data, async_strategy):
    """
    """
    try:
        # ctx.push()
        g.user = user
        g.product_id = product_id
        log.info("Setting G Variables %s, %s", user, product_id)
        execute_notebook = ExecuteNotebook(user, ex_data, async_strategy)
        response = execute_notebook.execute_notebook()
        log.info("Execute Notebook - Response %s", response)
    except Exception as ex:
        log.exception(ex)
        update_job_status(ex_data["instance_id"], user, MonitorStatus.FAILED)
        raise


def update_job_status(job_instance_id, user, status=MonitorStatus.FAILED):
    """
    To update run status in monitor service
    :param user:
    :param job_instance_id:
    :param status: MonitorStatus - Use Constants from this class
    :return:
    """
    try:
        log.info("Updating job-id %s to %s", job_instance_id, status)
        headers = generate_headers(
            userid=user["mosaicId"],
            email=user["email_address"],
            username=user["first_name"],
            project_id=user["project_id"]
        )
        querystring = {
            "jobInstanceId": str(job_instance_id),
            "jobStatus": str(status),
        }
        url = current_app.config["MONITOR_URL"] + "/monitor/jobinstance-status"
        resp = requests.put(url, data=querystring, headers=headers)
        log.info("Response Text - %s - Code %s", resp.text, resp.status_code)
        resp.raise_for_status()
    except Exception as ex:
        log.exception(ex)
        raise
