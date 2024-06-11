#! -*- Coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Notebooks manager module"""
import hashlib
import os
import jwt
import re
import copy
import logging
from ast import literal_eval
from datetime import date, datetime
import json
import shutil
import tempfile
from uuid import uuid4
import yaml
import requests
from requests.exceptions import ConnectionError
from flask import current_app as app, g, jsonify, after_this_request
from sqlalchemy import desc, func
from sqlalchemy.sql import label
import pandas as pd
from sqlalchemy import or_
from marshmallow import ValidationError
from mosaic_utils.ai.audit_log.utils import audit_logging
from mosaic_utils.ai.headers.constants import Headers
from mosaic_utils.ai.headers.utils import generate_headers
from mosaic_utils.ai.input_params.utils import get_all_input_params
from mosaic_utils.ai.input_params.contants import InputParamReferenceType
from mosaic_utils.ai.k8 import pod_metrics_summary
from notebooks_api.notebook.exceptions import QuotaExceed
from mosaic_utils.ai.data_files.utils import convert_into_bytes
from notebooks_api.utils.exceptions import (
    ErrorCodes,
    NoSubscriptionException,
    SubscriptionExpiredException,
    SubscriptionExceededException,
    UserQuotaExceededException,
    ProjectQuotaExceededException,
    MosaicException,
    UserRoleException,
    QuotaExceedException,
    NoRepoException,
    FetchProjectDetailException,
    ServiceConnectionError
)
from notebooks_api.utils.defaults import default_resource
from notebooks_api.utils.tags import get_tag
from notebooks_api.utils.project import create_repo_name
from ..constants import PasswordStore
from ..utils.encryption import PasswordStoreFactory, VaultEncrypter
from ..data_files.manager import check_and_create_directory
from . import schemas
from . import spcs
from notebooks_api.resource.models import Resource
from notebooks_api.utils.tags import get_tag_val
from notebooks_api.version_control.views import View
from .constants import (
    PodStatus,
    VcsURL,
    MosaicAI,
    KernelType,
    FileExtension,
    RepoStatus,
    Accesstype,
    RepoAccessCategory,
    ReportFiles,
    RepoMessages,
    NotebookPath,
    RepoType,
)
from .models import (
    DockerImage,
    Notebook,
    NotebookPod,
    NotebookPodArchive,
    NotebookTag,
    DockerImageTag,
    TemplateStatus,
    DataSnapshot,
    DockerImageExtraAttribute,
    db, GitRepo,
    GitRepoActive,
    GitRepoBranches,
    AdUser,
    AdGroup,
    AdMapping,
    NotebookPodMetrics,
    NotebookPodResources,
)

# pylint: disable=invalid-name

log = logging.getLogger("notebooks_api.notebook")


def spcs_connection_params(connection_id):
    """ fetch connection params for spcs """
    headers = generate_headers(userid=g.user["mosaicId"], email=g.user["email_address"], username=g.user["first_name"])
    connection_data = requests.get(f"{app.config['CONNECTION_MANAGER_URL']}/ConnectionManager/v1/connection/{connection_id}",
                                   headers=headers)
    if connection_data.status_code == 200:
        connection_data = connection_data.json()
        return {'user': connection_data['dbUserName'], 'password': connection_data['dbPassword'],
                'account': f"{connection_data['accountName']}.{connection_data['region']}", 'role': connection_data['role'],
                'warehouse': connection_data['wareHouse']}
    raise Exception(f"connection-manager for connection_data returned {connection_data.status_code}")


def list_snowflake_connections(account_id):
    """ list snowflake connections for user """
    headers = generate_headers(userid=g.user["mosaicId"], email=g.user["email_address"], username=g.user["first_name"])
    sources = requests.get(f"{app.config['CONNECTION_MANAGER_URL']}/ConnectionSources/v1/source/", headers=headers)
    if sources.status_code == 200:
        source_id = None
        for source in sources.json():
            if source['displayName'] == spcs.SpcsConstants.snowflake:
                source_id = source['sourceId']
                break
        if source_id:
            headers['content-type'] = 'application/json'
            params = {
                'projectId': g.user["project_id"],
                'accountId': account_id,
                'sourceTypeId': source_id
            }
            connection_list = requests.get(f"{app.config['CONNECTION_MANAGER_URL']}/ConnectionManager/v1/allConnections",
                                            headers=headers, params=params)
            if connection_list.status_code == 200:
                return connection_list.json()
            raise Exception(f"connection-manager for source_id returned {connection_list.status_code}")
        raise Exception("No source id found for Snowflake connection")
    raise Exception(f"connection-manager for connections returned {sources.status_code}")


def create_spcs_spec(query_details, template_file):
    with open(os.path.join(os.path.dirname(__file__), 'manifest', template_file)) as yaml_file:
        service = yaml_file.read().format(image=query_details['image'], stage=query_details.get('stage', ""))
        if query_details.get('env') and type(query_details['env'] == dict):
            service = yaml.safe_load(service)
            service['spec']['container'][0]['env'] = query_details['env']
            file_name = str(uuid4()) + ".yaml"
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, file_name)
            with open(temp_file, 'w') as temp_yaml:
                yaml.dump(service, temp_yaml)
            with open(temp_file) as temp_yaml:
                spec = temp_yaml.read()
            shutil.rmtree(temp_dir)
            return spec
        else:
            return service


def fetch_spcs_data_by_query(query_details, connection_params, service_name=None):
    """Fetch data from SPCS"""
    status = "success"
    message = ""
    if not service_name and query_details.get('service_name'):
        service_name = query_details['service_name']
    with spcs.SnowflakeConnection(connection_params=connection_params) as session:
        if query_details['query'] == spcs.SpcsConstants.create_service:
            template_file = spcs.SpcsConstants.service_stage_yaml if query_details.get("stage") else spcs.SpcsConstants.service_yaml
            spec = create_spcs_spec(query_details=query_details, template_file=template_file)
            service_status = session.sql(spcs.SpcsQuery.create_service.format(service_name=service_name, compute_pool=query_details['compute_pool'], spec=spec)).collect()
            if "success" not in service_status[0].as_dict()['status']:
                status = "fail"
            message = str(service_status[0].as_dict())
            data = [item.as_dict() for item in service_status]
        elif query_details['query'] == spcs.SpcsConstants.list_database:
            databases = session.sql(spcs.SpcsQuery.list_database).collect()
            data = [database.as_dict() for database in databases]
        elif query_details['query'] == spcs.SpcsConstants.list_schema:
            schemas = session.sql(spcs.SpcsQuery.list_schema).collect()
            data = [schema.as_dict() for schema in schemas]
        elif query_details['query'] == spcs.SpcsConstants.list_stage:
            stages = session.sql(spcs.SpcsQuery.list_stage).collect()
            data = [stage.as_dict() for stage in stages if spcs.SpcsConstants.mountable_stage in stage.as_dict()['type']]
        elif query_details['query'] == spcs.SpcsConstants.list_compute_pool:
            compute_pools = session.sql(spcs.SpcsQuery.list_compute_pool).collect()
            data = [compute_pool.as_dict() for compute_pool in compute_pools]
        elif query_details['query'] == spcs.SpcsConstants.get_uri:
            service_detail = session.sql(spcs.SpcsQuery.show_endpoints.format(service_name=f"{connection_params['database']}.{connection_params['schema']}.{service_name}")).collect()[0].as_dict()
            if spcs.SpcsConstants.provisioning in service_detail['ingress_url']:
                status = "fail"
                data = [{"endpoint": service_detail['ingress_url']}]
                message = service_detail['ingress_url']
            else:
                end_point = service_detail['ingress_url']
                data = [{"endpoint": end_point}]
                message = str({"endpoint": end_point})
            service_status = session.sql(spcs.SpcsQuery.service_status.format(service_name=f"{connection_params['database']}.{connection_params['schema']}.{service_name}")).collect()[0].as_dict()
            service_status = service_status[list(service_status.keys())[0]]
            for pod in literal_eval(service_status):
                if pod['status'] != spcs.SpcsConstants.ready:
                    status = "fail"
                    message = message + ", " + str({pod['containerName']: pod['message']})
        elif query_details['query'] == spcs.SpcsConstants.stop_service:
            stop_response = session.sql(
                spcs.SpcsQuery.stop_servie.format(service_name=service_name)).collect()
            data = [{"response": stop_response[0].as_dict()}]
        else:
            data = []
            status = "fail"
            message = "Invalid Query!"
    return {"data": data, "status": status, "message": message}


def create_spcs_service(spcs_data, image, service_name, env):
    query_details = {"service_name": service_name, 'query': spcs.SpcsConstants.create_service, 'image': image,
                     'stage': spcs_data.get('stage', False), 'env': env, 'compute_pool': spcs_data['compute_pool']}
    connection_params = spcs_connection_params(spcs_data['connection_id'])
    connection_params['database'] = spcs_data['database']
    connection_params['schema'] = spcs_data['schema']
    response = fetch_spcs_data_by_query(query_details, connection_params)
    if response['status'] == "success":
        return True
    return False


def stop_spcs_service(spcs_data, service_name):
    query_details = {"service_name": service_name, 'query': spcs.SpcsConstants.stop_service}
    connection_params = spcs_connection_params(spcs_data['connection_id'])
    connection_params['database'] = spcs_data['database']
    connection_params['schema'] = spcs_data['schema']
    response = fetch_spcs_data_by_query(query_details, connection_params)
    if response['status'] == "success":
        return True
    return False


def generate_name(tags):
    """ Generate random name for notebook """

    name = "untitled-1"
    project = get_tag("project", tags)

    notebooks = db.session \
        .query(Notebook) \
        .join(NotebookTag, Notebook.id == NotebookTag.notebook_id) \
        .filter(NotebookTag.tag.in_([project])) \
        .all()
    list_nb = []
    if notebooks:
        for notebook in notebooks:
            notebook_name = re.sub(r"\s+", "", notebook.name)
            if notebook_name.startswith(
                    "untitled-") and re.search(r"untitled-(\d+)", notebook_name) is not None:
                m = re.search(r"untitled-(\d+)", notebook_name)
                list_nb.append(int(m.group(1)))
        if len(list_nb) != 0:
            count = max(list_nb) + 1
            name = "untitled-{}".format(count)
    return name

def list_data_snapshots(project_id, snapshot_id=None):
    """Provides list of snapshots"""

    if snapshot_id:
        result_set = db.session.query(DataSnapshot) \
            .filter((DataSnapshot.id == snapshot_id))
    else:
        result_set = db.session.query(DataSnapshot) \
            .filter((DataSnapshot.project_id == project_id))

    log.debug(
        "Preparing response after fetched from db result_set=%s",
        result_set)

    snapshot_set = []
    for result in result_set:
        snapshot = result.as_dict()
        snapshot_set.append(snapshot)
    return snapshot_set

def fetch_notebooks(tags):
    """
    Fetch notebooks based on tags

    Args:
        tags (list): List of strings
    """

    # query database
    result_set = db.session \
        .query(DockerImage) \
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id) \
        .filter(DockerImage.type == "CUSTOM_BUILD") \
        .filter(DockerImageTag.tag.in_(tags)) \
        .order_by(desc(DockerImage.created_on))

    log.debug("Result fetched successfully from database and preparing response")
    # prepare response
    notebook_set = []
    for result in result_set:
        notebook = result.as_dict()
        notebook.update({"tags": [tag.tag for tag in result.tags]})
        notebook.update({"kernel_type": result.kernel_type})
        notebook_set.append(notebook)

    return notebook_set


def create_notebook(notebook_data):
    """
    Create notebook and tags

    Args:
        notebook_data (dict): Dictionary of data
    """
    data = copy.deepcopy(notebook_data)
    # parse extra data
    user = g.user["mosaicId"]
    tags = data.pop("tags", [])

    # fetch docker image & tags
    docker_image_id = data["docker_image_id"]
    docker_image = DockerImage.query.get(docker_image_id)
    docker_image_tags = [x.tag for x in docker_image.tags]
    docker_image_type = get_tag("type", docker_image_tags)
    tags.append(docker_image_type)

    # generate name
    if "name" not in data:
        name = generate_name(tags)
        if "jupyter" in docker_image_type:
            name = "{}.ipynb".format(name)
        data.update({"name": name})

    # set the icon attribute
    data.update({"icon": docker_image.icon})
    # create notebook object
    log.debug("Creating notebook object")
    notebook = Notebook(**data)

    try:
        # save notebook object
        db.session.add(notebook)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    # create notebook tag object
    notebook_tags = []
    for tag in tags:
        tag = NotebookTag(
            notebook_id=notebook.id,
            tag=tag,
            created_by=user,
            updated_by=user)
        notebook_tags.append(tag)

    # save notebook tag objects
    log.debug("Database operation start to save notebook tag object")
    try:
        db.session.add_all(notebook_tags)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    # override default resource with the one from docker image
    if notebook.resource.id == default_resource():
        notebook.resource_id = notebook.docker_image.resource_id
        try:
            db.session.add(notebook)
            db.session.commit()
        # pylint: disable=broad-except
        except Exception as e:
            log.exception(e)
            db.session.rollback()

    # prepare notebook
    resource = notebook.resource.as_dict()
    docker_image = notebook.docker_image.as_dict()
    notebook = notebook.as_dict()
    notebook.update({
        "tags": tags,
        "resource": resource,
        "docker_image": docker_image,
    })

    return notebook


def create_template_tag(project_tag, user, docker_id):
    """
    Create template tag

    Args:
    """
    log.debug("creating template tag")
    try:
        project_query = DockerImageTag.query\
            .filter(DockerImageTag.tag == project_tag)\
            .filter(DockerImageTag.docker_image_id == docker_id)\
            .all()
        if not project_query:
            log.debug("adding project tag")
            db.session.add(
                DockerImageTag(
                    tag=project_tag,
                    docker_image_id=docker_id,
                    created_by=user,
                    updated_by=user))
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def read_notebook(notebook_id):
    """
    Read notebook

    Args:
        notebook_id (str): UUID of the notebook
    """

    # fetch notebook object
    notebook = Notebook.query.get(notebook_id)

    # fetch notebook tag object
    notebook_tags = []
    for tag in notebook.tags:
        notebook_tags.append(tag.tag)

    # combine notebook and notebook tag
    log.debug("Combining notebook and notebook tag")
    notebook_resource = notebook.resource.as_dict()
    notebook_docker_image = notebook.docker_image.as_dict()
    notebook = notebook.as_dict()
    notebook.update({"tags": notebook_tags})
    notebook.update({"resource": notebook_resource})
    notebook.update({"docker_image": notebook_docker_image})
    # pylint: disable=logging-too-many-args
    log.debug("fetching and creating notebooks", notebook)

    return notebook


def read_template(notebook_id):
    """
    Read notebook

    Args:
        notebook_id (str): UUID of the notebook
    """

    # fetch notebook object
    # notebook = Notebook.query.get(notebook_id)
    notebook = DockerImage.query.get(notebook_id)
    # fetch notebook tag object
    notebook_tags = []
    for tag in notebook.template_tag:
        notebook_tags.append(tag.tag)

    # combine notebook and notebook tag
    log.debug("Combining notebook and notebook tag")
    notebook_resource = notebook.resource.as_dict()
    notebook = notebook.as_dict()
    notebook.update({"tags": notebook_tags})
    notebook.update({"resourcarchive_notebook_pode": notebook_resource})
    # notebook.update({"docker_image": notebook_docker_image})
    # pylint: disable=logging-too-many-args
    log.debug("fetching and creating notebooks", notebook)

    return notebook


def read_notebook_by_name(notebook_name):
    """
    Read notebook by name

    Args:
         notebook_name (str): Name of the notebook
    """

    notebook = Notebook.query.filter(Notebook.name == notebook_name).first()

    # fetch notebook tag object
    notebook_tags = []
    for tag in notebook.tags:
        notebook_tags.append(tag.tag)

    # combine notebook and notebook tag
    log.debug("Combining notebook and notebook tag")
    notebook_resource = notebook.resource.as_dict()
    notebook_docker_image = notebook.docker_image.as_dict()
    notebook = notebook.as_dict()
    notebook.update({"tags": notebook_tags})
    notebook.update({"resource": notebook_resource})
    notebook.update({"docker_image": notebook_docker_image})

    return notebook


def update_notebook(notebook_id, data):
    """
    Update notebook

    Args:
        notebook_id (str): UUID of the notebook
        data (dict): Dictionary of data
    """

    # parse tags
    tags = data.pop("tags", [])
    user = g.user["mosaicId"]

    # fetch notebook object
    notebook = Notebook.query.get(notebook_id)

    # update notebook object
    log.debug("Updating notebook object=%s", data)
    for key, val in data.items():
        setattr(notebook, key, val)

    try:
        # save notebook object
        db.session.add(notebook)
        if tags:
            # remove existing notebook tag object
            log.debug("Deleting existing notebook  tag object=%s", tags)
            for tag in notebook.tags:
                db.session.delete(tag)

            # create new notebook tag object
            log.debug("Creating new notebook tag object=%s", tags)

            notebook_tags = []
            for tag in tags:
                tag = NotebookTag(
                    notebook_id=notebook.id,
                    tag=tag,
                    created_by=user,
                    updated_by=user)
                notebook_tags.append(tag)
            db.session.add_all(notebook_tags)

        # commit to db
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def update_notebook_in_db(notebook_id, data):
    """
    Update notebook

    Args:
        notebook_id (str): UUID of the notebook
        data (dict): Dictionary of data
    """
    try:
        # fetch notebook object
        notebook = Notebook.query.get(notebook_id)
        notebook.updated_on = datetime.now()

        # update notebook object
        log.debug("Updating notebook object=%s", data)
        for key, val in data.items():
            setattr(notebook, key, val)

        # save notebook object
        db.session.add(notebook)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception:
        log.exception("Unable to update notebook content")
        db.session.rollback()


# pylint: disable=too-many-locals
def delete_notebook(user, notebook_id):
    """
    Delete notebook

    Args:
        notebook_id (str): UUID of the notebook
        :user (json): user details
    """
    # pylint: disable=import-outside-toplevel
    from .tasks import stop_notebook_pod
    log.debug("Fetching notebook for notebook_id=%s", notebook_id)

    # fetch notebook based on id
    notebook = Notebook.query.get(notebook_id)

    notebook_tags = []
    for tag in notebook.tags:
        notebook_tags.append(tag.tag)

    project_id = [s for s in notebook_tags if "project=" in s]
    project = [s for s in notebook_tags if "label=" in s]
    split_project_id = project_id[0].replace('project=', '')
    split_project_name = project[0].replace('label=', '')
    repo_name = create_repo_name(split_project_name, split_project_id)
    _, notebook_type = get_tag("type", notebook_tags, split=True)
    log.debug(repo_name)
    log.debug("Removing notebook pod=%s", notebook.pod)
    headers = generate_headers(
        userid=g.user["mosaicId"],
        email=g.user["email_address"],
        username=g.user["first_name"])

    # remove notebook pods
    pods = notebook.pod
    for pod in pods:
        update_pod_status(pod, PodStatus.STOPPING)
        stop_notebook_pod(user, notebook.as_dict(), pod.as_dict())

    try:
        # delete from db
        db.session.delete(notebook)
        db.session.commit()
        # git_server_url = app.config["VCS_BASE_URL"]
        name = notebook.name
        # delete_notebook_url = git_server_url + \
        #     VcsURL.DELETE_NB_URL.format(repo_name)
        # payload = {"name": name}
        # response = requests.delete(
        #     delete_notebook_url,
        #     json=payload,
        #     headers=headers)
        response = View(project_id=g.user["project_id"])._git_upload(repo=repo_name, temp_dir=None, ignore_duplicate=True, delete_nb=name, path=g.repo_details["base_folder"], commit_message="Delete File/Folder")
        log.debug(response)
        audit_logging(
            console_url=app.config['CONSOLE_BACKEND_URL'],
            action_type="DELETE",
            object_id=notebook_id,
            object_name=notebook.name,
            object_type="NOTEBOOK",
            headers={
                Headers.x_auth_username: g.user["first_name"],
                Headers.x_auth_email: g.user["email_address"],
                Headers.x_auth_userid: g.user["mosaicId"],
                Headers.x_project_id: g.user['project_id'],
            },
        )
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def register_notebook_pod(notebook, user_id, pod_name, pod_status):
    """
    inserts the record in db for the notebook container created by the user
    :param notebook:
    :param user_id:
    :param pod_name:
    :param pod_status:
    :return:
    """
    # removing @ as after spawning the notebook in k8s, @ is automatically removed
    # syncing pod name in db with spawned notebook
    revised_pod_name = pod_name.replace("@", "")

    # create notebook pod
    notebook_pod = NotebookPod(
        notebook_id=notebook["id"],
        name=revised_pod_name,
        status=pod_status,
        created_by=user_id,
        updated_by=user_id
    )
    # add to session
    db.session.add(notebook_pod)
    log.debug("Creating notebook pod=%s", notebook_pod)

    try:
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    return notebook_pod


# pylint: disable=unused-variable
def register_template_status(
        notebook,
        user_id,
        pod_status,
        project_id,
        enabled_repo):
    """
    inserts the record in db for the notebook container created by the user
    :param notebook:
    :param user_id:
    :param project_id:
    :param pod_status:
    :param enabled_repo:
    :return:
    """
    # removing @ as after spawning the notebook in k8s, @ is automatically removed
    # syncing pod name in db with spawned notebook
    # create notebook pod
    template_status = TemplateStatus(
        template_id=notebook['docker_image']["id"],
        status=pod_status,
        resource_id=notebook['docker_image']['resource_id'],
        created_by=user_id,
        project_id=project_id,
        repo_id=enabled_repo['repo_id'],
        repo_name=enabled_repo['repo_name'],
        branch_name=enabled_repo['branch'],
        input=notebook['input'],
        output=notebook['output'],
        spcs_data=notebook.get('spcs_data', {}))

    # add to session
    db.session.add(template_status)
    log.debug("Template Status=%s", template_status)

    try:
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    return template_status

def get_latest_commit(project_id, enabled_repo):
    """ Returns latest commit id """
    log.debug(f"Fetching latest commit id")
    commits, message, _ = View(repo_details=enabled_repo).get_latest_commit_id(project_id)
    # git_server_url = app.config["VCS_BASE_URL"]
    # request_url = VcsURL.COMMIT_ID.format(git_server_url)
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"],
    #     project_id=project_id,
    # )
    # headers.update({'enabled_repo': json.dumps(enabled_repo)})
    # response = requests.get(request_url, headers=headers)
    return {'commits': commits, 'message': message}

def delete_snapshot(snapshot_name, project_id):
    """Function to delete snapshot entry from db"""
    try:
        result_set = db.session.query(DataSnapshot) \
            .filter((DataSnapshot.snapshot_name == snapshot_name)) \
            .filter((DataSnapshot.project_id == project_id)).delete()
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

# pylint: disable=unused-variable
def register_snapshot(
        notebook,
        user_id,
        project_id,
        enabled_repo):
    """
    snapshot_name = db.Column(db.String(200), nullable=False)
    container = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.String(100), nullable=False)
    project_name = db.Column(db.String(100), nullable=False)
    git_repo =  db.Column(db.String(100))
    commit_id  = db.Column(db.String(100))
    branch =  db.Column(db.String(100))
    snapshot_path =  db.Column(db.String(200), nullable=False)
    access_type =  db.Column(db.Enum(OWNER, CONTRIBUTOR, VIEWER))
    """
    try:
        commit = get_latest_commit(project_id, enabled_repo)
        commit_id = commit["commits"]["commit_id"]
    # pylint: disable=broad-except
    except Exception:
        commit_id = "NA"
    snap_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/" + f'{project_id}/{project_id}-Snapshot/{notebook["output"]}/'
    check_and_create_directory(snap_path)
    snapshot_status = DataSnapshot(
        snapshot_name=notebook['output'],
        created_by=user_id,
        updated_by=user_id,
        container=notebook['container_object']["name"],
        project_id=project_id,
        project_name=project_id,
        git_repo=enabled_repo['repo_name'],
        commit_id=commit_id,
        branch=enabled_repo['branch'],
        snapshot_input_path=notebook['input'],
        snapshot_path=notebook['output'],
        access_type="OWNER")

    result_set = db.session.query(DataSnapshot) \
            .filter(DataSnapshot.snapshot_name == notebook['output']) \
            .filter(DataSnapshot.project_id == project_id)
    snapshot_set = []
    for result in result_set:
        snapshot = result.as_dict()
        snapshot_set.append(snapshot)
    if notebook['output'] == KernelType.default:
        return snapshot_status
    if not snapshot_set:
        # add to session
        db.session.add(snapshot_status)
        log.debug("Creating snapshot=%s", snapshot_status)

        try:
            db.session.flush()
        # pylint: disable=broad-except
        except Exception as e:
            log.exception(e)
            db.session.rollback()

    return snapshot_status


def delete_notebook_pod(notebook_pod):
    """
    Method to delete notebook pod
    :param notebook_pod:
    :return:
    """
    try:
        db.session.delete(notebook_pod)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


# pylint: disable=too-many-locals
def fetch_running_notebooks(project_tag, user=None):
    """
    Method to fetch the list of running notebook containers per user per Project
    :param project_tag:
    :param user:
    :return:
    """

    # query database
    query_set = db.session.query(NotebookTag, NotebookPod, Notebook)\
        .filter(NotebookTag.tag == project_tag)\
        .join(Notebook, Notebook.id == NotebookTag.notebook_id)\
        .join(NotebookPod, NotebookPod.notebook_id == Notebook.id)\
        .filter(NotebookPod.status.in_([PodStatus.STARTING, PodStatus.RUNNING]))
    if user:
        result_set = query_set.filter(NotebookPod.created_by == user).all()
    else:
        result_set = query_set.all()
        notebooks = []
        for _, _, notebook in result_set:
            notebooks.append(notebook.id)
        return {'Notebooks': list(set(notebooks))}

    servers = {}
    url_prefix = app.config["URL_PREFIX"]
    proxy_prefix = app.config["PROXY_PREFIX"]

    # pylint: disable=unused-variable
    _, project_id = project_tag.split("=")
    scheduled_notebooks = {}

    for _, notebook_pod, notebook in result_set:

        notebook_tags = [x.tag for x in notebook.tags]
        notebook_type = get_tag("type", notebook_tags)

        if notebook_type == "rstudio":
            notebook_url = "{}/user/{}/{}/".format(
                proxy_prefix, user, notebook.id)
            terminal_url = ""
            progress_url = "{}/v1/notebooks/{}/{}/progress".format(
                url_prefix, user, notebook.id)
        else:
            notebook_url = "{}/user/{}/{}/".format(proxy_prefix, user, notebook.id)
            terminal_url = "{}/user/{}/{}/terminals/websocket/1".format(
                proxy_prefix, user, notebook.id)
            progress_url = "{}/v1/notebooks/{}/{}/progress".format(
                url_prefix, user, notebook.id)

        scheduled = False
        job_id = ""
        cron_json = ""
        cron_expr = ""
        if notebook.id in scheduled_notebooks:
            job_info = scheduled_notebooks[notebook.id]
            scheduled = True
            job_id = job_info['id']
            cron_json = job_info['cron_json']
            cron_expr = job_info['cron_expr']

        server = {
            'id': notebook.id,
            'name': notebook.name,
            'icon': notebook.icon,
            'started': notebook_pod.created_on,
            'progress': progress_url,
            'url': notebook_url,
            'terminal': terminal_url,
            'scheduled': scheduled,
            'job_id': job_id,
            'cron_json': cron_json,
            'cron_expr': cron_expr

        }
        servers.update({notebook.name: server})

    return {'servers': servers}


# pylint: disable=too-many-locals
def fetch_running_template(project_tag, project_id=None, user=None):
    """
    Method to fetch the list of running notebook containers per user per Project
    :param project_tag:
    :param project_id:
    :param user:
    :return:
    """
    log.debug("fetching running templates")
    # query database
    query_set = db.session \
        .query(DockerImageTag, TemplateStatus, DockerImage, Resource) \
        .filter(DockerImageTag.tag == project_tag) \
        .join(DockerImage, DockerImage.id == DockerImageTag.docker_image_id) \
        .join(TemplateStatus, TemplateStatus.template_id == DockerImage.id) \
        .join(Resource, Resource.id == DockerImage.resource_id) \
        .filter(TemplateStatus.status.in_([PodStatus.STARTING, PodStatus.RUNNING])) \
        .filter(TemplateStatus.project_id == project_id)

    if user:
        result_set = query_set.filter(TemplateStatus.created_by == user).all()
    else:
        result_set = query_set.all()
        templates = []
        for _, _, template, _ in result_set:
            templates.append(template.id)
        return {'templates': list(set(templates))}

    servers = {}
    scheduled_notebooks = {}

    for _, template_status, docker_image, resource in result_set:
        template_project = template_status.id
        template_pod_name = template_status.pod_name
        repo_id = template_status.repo_id
        repo_name = template_status.repo_name
        branch_name = template_status.branch_name

        image = docker_image.as_dict()
        # Get base image name, id for custom template
        if image.get("base_image_id") is None:
            docker_image_name = image.get('name')
            docker_id = image.get('id')
        else:
            base_image_details = fetch_base_image_details_for_custom_build(
                image.get("base_image_id"))
            docker_image_name = base_image_details.get('name')
            docker_id = image.get("base_image_id")

        port, cmd, argument, base_url_env_key, base_url_env_value, ingress_url, container_uid = \
            fetch_extra_attribute_docker_image(
                docker_id,
                g.user.get('email_address'),
                docker_image_name,
                project_id,
                template_project
            )
        terminal_url = ""
        progress_url = "/notebooks/api/v1/spawner/progress/pod-name/{0}?port_no={1}&ingress_url={2}&kernel_type={3}".format(
            template_pod_name, port, ingress_url, image.get("kernel_type"))
        log.debug(f"\nprogress_url updated: {progress_url}\n")
        ingress_url = ingress_url + 'lab' if "Jupyterlab" in ingress_url else ingress_url
        notebook_url = ingress_url

        scheduled = False
        job_id = ""
        cron_json = ""
        cron_expr = ""
        if docker_image.id in scheduled_notebooks:
            job_info = scheduled_notebooks[docker_image.id]
            scheduled = True
            job_id = job_info['id']
            cron_json = job_info['cron_json']
            cron_expr = job_info['cron_expr']

        server = {
            'id': docker_image.id,
            'name': docker_image.name,
            'icon': docker_image.icon,
            'started': template_status.start_date,
            'progress': progress_url,
            'url': notebook_url,
            'terminal': terminal_url,
            'scheduled': scheduled,
            'job_id': job_id,
            'cron_json': cron_json,
            'cron_expr': cron_expr,
            'template_pod_name': template_pod_name,
            'repo_id': repo_id,
            'repo_name': repo_name,
            'branch_name': branch_name,
            'created_by': docker_image.created_by,
            'resource': resource.as_dict()
        }
        servers.update({docker_image.name: server})

    return {'servers': servers}


def fetch_running_notebooks_for_metrics(project_tag):
    """
    This method will fetch the list of running notebook containers per user for that project
    :param project_tag:
    :param user:
    :return:
    """

    # query database
    result_set = db.session.query(NotebookTag, NotebookPod, Notebook)\
        .filter(NotebookTag.tag == project_tag)\
        .join(Notebook, Notebook.id == NotebookTag.notebook_id)\
        .join(NotebookPod, NotebookPod.notebook_id == Notebook.id)\
        .filter(NotebookPod.status.in_([PodStatus.STARTING, PodStatus.RUNNING]))\
        .all()

    # pylint: disable=unused-variable
    servers = {}
    _, project_id = project_tag.split("=")

    for _, notebook_pod, notebook in result_set:
        server = {
            'id': notebook.id,
            'name': notebook.name,
            'pod_name': notebook_pod.name,
            'icon': notebook.icon,
            'started': notebook_pod.created_on,
            'user_name': notebook_pod.created_by,
        }
        servers.update({notebook_pod.name: server})

    return {'servers': servers}


def fetch_pod(notebook_id, user_id, status=PodStatus.RUNNING):
    """
    :param notebook_id:
    :param user_id:
    :param status
    :return:
    """

    # entry log
    log.debug(
        "Entering fetch_pod with notebook_id=%s user_id=%s",
        notebook_id,
        user_id)

    notebook_pod = NotebookPod.query \
        .filter(NotebookPod.created_by == user_id) \
        .filter(NotebookPod.notebook_id == notebook_id) \
        .filter(NotebookPod.status == status) \
        .first()

    # exit log
    log.debug("Exiting fetch_pod")

    return notebook_pod


def fetch_pod_template(notebook_id, user_id, project_id, status=PodStatus.RUNNING):
    """
    :param notebook_id:
    :param user_id:
    :param project_id:
    :param status
    :return:
    """
    in_status = status if isinstance(status, list) else [status]
    # entry log
    log.debug(
        "Entering fetch_pod with notebook_id=%s user_id=%s project_id=%s",
        notebook_id, user_id, project_id)
    template_pod = TemplateStatus.query \
        .filter(TemplateStatus.created_by == user_id) \
        .filter(TemplateStatus.template_id == notebook_id) \
        .filter(TemplateStatus.status.in_(in_status)) \
        .filter(TemplateStatus.project_id == project_id) \
        .first()
    # exit log
    log.debug("Exiting fetch_pod")
    return template_pod


def fetch_pod_project_id(notebook_id, status=PodStatus.RUNNING):
    """
    :param notebook_id:
    :param status
    :return:
    """
    # entry log
    log.debug("Entering fetch_pod with notebook_id=%s ", notebook_id)
    notebook_pod = NotebookPod.query \
        .filter(NotebookPod.notebook_id == notebook_id) \
        .filter(NotebookPod.status == status) \
        .first()
    # exit log
    log.debug("Exiting fetch_pod")

    return notebook_pod


def archive_notebook_pod(notebook_pod, project_id):
    """
    Archive notebook_pod
    :param notebook_pod:
    :param project_id
    :return:
    """
    # entry log
    log.debug(
        "Entering archive_notebook_pod with notebook_pod=%s",
        notebook_pod)

    notebook_pod = fetch_pod_template(
        notebook_pod["notebook_id"],
        notebook_pod["created_by"],
        project_id,
        PodStatus.STOPPING
    )

    archive = NotebookPodArchive()
    # pylint: disable=invalid-name
    archive.id = notebook_pod.id
    archive.notebook_id = notebook_pod.notebook_id
    archive.name = notebook_pod.name
    archive.status = notebook_pod.status
    archive.created_by = notebook_pod.created_by
    archive.updated_by = notebook_pod.updated_by
    archive.created_on = notebook_pod.created_on
    archive.updated_on = notebook_pod.updated_on
    try:
        db.session.add(archive)
        db.session.delete(notebook_pod)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def update_pod_status(pod, status):
    """
    Update NotebookPod status
    :param pod:
    :param status:
    :return:
    """
    # update pod log
    log.debug("Updating pod status with pod=%s status=%s", pod, status)
    pod.status = status
    try:
        db.session.add(pod)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def update_template_status(pod, status, pod_name=None):
    """
    Update NotebookPod status
    :param pod:
    :param status:
    :param pod_name:
    :return:
    """
    # update pod log
    log.debug("Updating pod status with pod=%s status=%s", pod, status)
    pod.status = status
    if pod_name:
        pod.pod_name = pod_name
    try:
        db.session.add(pod)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def fetch_notebooks_count_for_projects(project_ids):
    """
    Fetch notebooks based on tags
    Args:
        tags (list): List of strings
    """

    # entry log
    log.debug("Fetching result from database with tags=%s", project_ids)
    tags = []
    for project_id in project_ids:
        tag = 'project={}'.format(project_id)
        tags.append(tag)

    # query database
    result_set = db.session \
        .query(NotebookTag.tag, label('count', func.count(NotebookTag.id))) \
        .filter(NotebookTag.tag.in_(tags)) \
        .filter(NotebookTag.notebook_id.isnot(None)) \
        .group_by(NotebookTag.tag) \
        .all()

    # prepare response
    notebook_set = {}
    for result in result_set:
        _, project_id = get_tag("project", [result[0]], True)
        notebook_set[project_id] = result[1]

    for project_id in project_ids:
        if project_id not in notebook_set:
            notebook_set[str(project_id)] = 0

    return notebook_set


def fetch_activity_of_project(project_id, start_time, end_time):
    """
    Fetch the activities related to the project
    Args:
        project_id:
        start_time:
        end_time:
    """
    # entry log
    log.debug(
        "Fetching result from database with project_id=%s start_time=%s end_time=%s",
        project_id,
        start_time,
        end_time)

    tags = ["project={}".format(project_id)]
    # query database
    result_set = db.session \
        .query(Notebook) \
        .filter(((Notebook.created_on <= end_time)
                 & (Notebook.created_on >= start_time))
                | ((Notebook.updated_on <= end_time)
                   & (Notebook.updated_on >= start_time))) \
        .join(NotebookTag, Notebook.id == NotebookTag.notebook_id) \
        .filter(NotebookTag.tag.in_(tags))
    activities = []

    for result in result_set:
        notebook = result.as_dict()
        if start_time <= notebook['created_on'] <= end_time:
            action = 'CREATE'
            time_date = notebook['created_on'].timestamp()

            activity = {
                'ownerProjectId': project_id,
                'objectType': 'NOTEBOOK',
                'timeDate': time_date,
                'action': action,
                'objectName': notebook['name']}
            activities.append(activity)

        if (notebook['updated_on'] != notebook['created_on']) & (
                start_time <= notebook['updated_on'] <= end_time):
            action = 'UPDATE'
            time_date = notebook['updated_on'].timestamp()
            activity = {
                'ownerProjectId': project_id,
                'objectType': 'NOTEBOOK',
                'timeDate': time_date,
                'action': action,
                'objectName': notebook['name']}
            activities.append(activity)

    return activities


def change_the_updated_time_for_notebook(notebook_name, project):
    """
    Rename notebook
    Args:
        notebook_name (str): Name of the notebook
        project (string): project id
    """
    notebook = db.session \
        .query(Notebook) \
        .join(NotebookTag, Notebook.id == NotebookTag.notebook_id) \
        .filter(NotebookTag.tag == "project={}".format(project)) \
        .filter(Notebook.name == notebook_name) \
        .first()

    notebook.updated_on = datetime.now()
    try:
        # save to database
        db.session.add(notebook)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()



def check_if_notebook_name_is_duplicate(name, project):
    """
    Notebook name duplicate check method
    """
    notebook = db.session \
        .query(Notebook) \
        .join(NotebookTag, Notebook.id == NotebookTag.notebook_id) \
        .filter(NotebookTag.tag == "project={}".format(project)) \
        .filter(Notebook.name == name) \
        .first()
    if notebook is not None:
        raise ValueError(
            "Notebook with same name already exist, try with different name"
        )


def validate_notebook_content(notebook_content):
    """Validate notebook content"""
    if not notebook_content["nbformat"] \
            or not notebook_content["nbformat_minor"]:
        raise ValueError("Notebook content is not valid")


def validate_upload_json(data):
    """Function to validate upload json"""
    if not data.get("name"):
        raise ValueError("name is mandatory")
    if not data.get("docker_image_id"):
        raise ValueError("docker image id is mandatory")
    if not data.get("tags"):
        raise ValueError("Please provide tags")


def check_if_name_is_valid(name):
    """Method to validate name"""
    if name.strip() == '':
        raise ValueError("name should not be blank")


def fetch_init_script(docker_image_id):
    """Method to fetch init script"""
    docker_image = db.session \
        .query(DockerImage) \
        .filter(DockerImage.id == docker_image_id) \
        .first()
    return docker_image.init_script


def validate_delete_template(template_id):
    """Method to validate delete template"""
    log.debug("Entering validate delete with template_id=%s", template_id)
    query_set = db.session\
        .query(TemplateStatus)\
        .filter(TemplateStatus.status.in_([PodStatus.STARTING, PodStatus.RUNNING]))\
        .filter(TemplateStatus.template_id == template_id)\
        .all()
    users = []
    for user in query_set:
        users.append(user.created_by)

    if users:
        raise ValueError(
            f"The Following users are still using this template:\n{', '.join(users)}")
    log.debug("Exiting Validate delete")


def fetch_running_template_by_user(template_id, user, project_id):
    """Method to fetch running template by user"""
    query_set = db.session\
        .query(TemplateStatus)\
        .filter(TemplateStatus.status.in_([PodStatus.STARTING, PodStatus.RUNNING]))\
        .filter(TemplateStatus.template_id == template_id)\
        .filter(TemplateStatus.created_by == user)\
        .filter(TemplateStatus.project_id == project_id)\
        .all()

    if query_set:
        raise QuotaExceedException(msg_code="QUOTA_EXCEED_ERROR_002")


# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
def get_execute_command(kernel_type, file_path, project_id, instance_id, enabled_repo=None, user_impersonation=False, arguments=""):
    """Method to get execute command"""
    minio_bucket = app.config["MINIO_BUCKET"]
    log.debug("file_path before: %s", file_path)
    sp_value = 2 if enabled_repo['base_folder'] in [None, ""] else 3 + len(re.findall("/", enabled_repo['base_folder']))
    if not file_path.startswith('/notebooks/notebooks/'):
        file_path = os.path.join("/notebooks/notebooks/", *(file_path.split(os.path.sep)[sp_value:])) \
            if file_path.startswith('/notebooks/') and len(re.findall("/", file_path)) > 2 \
            else file_path.replace("/notebooks/", "/notebooks/notebooks/")
    log.debug("file_path after: %s", file_path)


    html_file_path = "".join((file_path.strip("ipynb"), "html"))
    file_extension = os.path.splitext(file_path)[-1].lower()
    file_path = file_path.replace("\\", "")

    # pylint: disable=anomalous-backslash-in-string
    cp_to_datasnap = 'find /tmp \( -name "output.html"  \) -print | xargs -I {} cp  {} '+f'/output/{instance_id}/; \n'
    terminate_flag = 'if [ $? -ne 0 ]; then Terminate=1; \n fi; \n'
    sas_terminate_flag = 'if [ $? -gt 1 ]; then Terminate=1 \n fi \n'
    argument_string = str(arguments)

    if kernel_type not in [KernelType.spark, KernelType.spark_distributed] and FileExtension.ipynb == file_extension:
        # pylint: disable=line-too-long
        execution_command = f'cd {NotebookPath.nb_base_path}; python /code/run_python_job.py "{file_path}" /tmp/result.ipynb /tmp/output.html ./ 2>&1 \n' \
                            + terminate_flag + cp_to_datasnap

    elif kernel_type in [KernelType.spark, KernelType.spark_distributed]:
        initial_cmd = ""
        if FileExtension.ipynb == file_extension:
            initial_cmd = f"jupyter nbconvert --to=python '{file_path}';"
            file_path = ".".join(file_path.split(".")[:-1]) + ".py"
        execution_command = f"{initial_cmd}" \
                            f"{app.config.get('SPARK_SUBMIT_COMMAND').format(file_path=file_path, instance_id=instance_id)}" \
                            + terminate_flag \
                            + cp_to_datasnap

    elif kernel_type in [KernelType.sas_batch_cli] and FileExtension.sas == file_extension:
        # pylint: disable=line-too-long
        execution_command = f'python /code/run_sas_batch_cli_job.py "{file_path}" /output/ /tmp/output.html ./ 2>&1 \n' \
                            + terminate_flag + cp_to_datasnap

    elif FileExtension.py in file_extension:
        execution_command = f'cd {NotebookPath.nb_base_path}; python "{file_path}" {argument_string} 2>&1; \n' \
                            + terminate_flag \
                            + cp_to_datasnap + \
                            f'cat /output/{instance_id}/central.log > /tmp/output.html; \n'

    elif FileExtension.r in file_extension:
        execution_command = f'Rscript "{file_path}" 2>&1;  \n' \
                            + terminate_flag \
                            + cp_to_datasnap + \
                            f'cat /output/{instance_id}/central.log > /tmp/output.html; \n'

    elif FileExtension.sas in file_extension:
        sas_file_name = file_path.strip(FileExtension.sas)
        sas_file = sas_file_name.split("/")[-1]
        execution_command = f'/opt/sas/spre/home/bin/sas "{file_path}" -log 2>&1 -logparm open=append -PRINT output_code.html -errorcheck strict -errorabend -errorbyabend \n' \
                            + sas_terminate_flag + \
                             f'if test -f output_code.html; then \ncat output_code.html > /tmp/output.html \n' \
                            f'else touch /tmp/output.html \n fi \n' \
                            + cp_to_datasnap

    elif FileExtension.java in file_extension:
        execution_command = create_scala_java_command(file_path, lang="java", arguments=argument_string) + " \n " \
                            + terminate_flag \
                            + cp_to_datasnap + \
                            f'cat /output/{instance_id}/central.log > output.html \n'

    elif FileExtension.scala in file_extension:
        execution_command = create_scala_java_command(file_path, lang="scala") + " \n " \
                            + terminate_flag \
                            + cp_to_datasnap

    if user_impersonation and kernel_type in [KernelType.python, KernelType.r, KernelType.sas, KernelType.jdk11,
                                              KernelType.rstudio, KernelType.sas_batch_cli, KernelType.vscode_python]:
        execution_command = f'umask {app.config.get("USER_IMPERSONATION_UMASK")}; ' + execution_command

    return execution_command


def prepare_node_affinity_options():
    """Method to fetch Node Affinity values from Configmap"""
    return{
        "NODE_AFFINITY_REQUIRED_KEY": app.config["NODE_AFFINITY_REQUIRED_KEY"],
        "NODE_AFFINITY_REQUIRED_VALUES": app.config["NODE_AFFINITY_REQUIRED_VALUES"].split(","),
        "NODE_AFFINITY_REQUIRED_OPERATOR": app.config["NODE_AFFINITY_REQUIRED_OPERATOR"],
        "TOLERATIONS_KEY": app.config["TOLERATIONS_KEY"],
        "TOLERATIONS_VALUE": app.config["TOLERATIONS_VALUE"],
        "TOLERATIONS_OPERATOR": app.config["TOLERATIONS_OPERATOR"],
        "TOLERATIONS_EFFECT": app.config["TOLERATIONS_EFFECT"],
    }


def create_scala_java_command(file_path, lang, arguments=""):
    """
    Create scala command with snowpark in classpath
    :param lang: scala or java
    :param file_path:
    :param arguments
    :return:
    """
    actual_file = os.path.basename(file_path)
    dir_name = os.path.dirname(file_path)
    compiled_file_name = actual_file.split(f".{lang}")[0]
    command = f'cd "{dir_name}" && ' \
              f'{lang}c "{actual_file}" && ' \
              f'{lang}  "{compiled_file_name}" "{arguments}" 2>&1'
    return command


def remove_special_char(var):
    """
    Method to remove spaces & special characters apart from '-' & "_" from var,
    returns only alphanumeric values
    :param var: variable name
    """
    return "".join(e for e in var if e == "-" or e == "_" or e.isalnum())


def get_execute_command_ipynb_to_py(kernel_type, file_path, log_file_name=None):
    """ Create execution command to convert ipynb nb to py"""
    py_file_path = "".join((file_path.strip("ipynb"), "py"))
    terminate_flag = 'if [ $? -ne 0 ]; then Terminate=1 \n fi \n'
    if log_file_name is None:
        log_file_name = "/output/central.log"

    if kernel_type == KernelType.python:
        execution_command = f'jupyter nbconvert --to=python "{file_path}" \n' \
                            f'python "{py_file_path}" >> {log_file_name} 2>&1; \n' \
                            + terminate_flag
    return execution_command


def fetch_extra_attribute_docker_image(base_image_id, user_email_id, docker_image_name,
                                       project, template_project):
    """
    Method to fetch the list of running notebook containers per user per Project
    :param base_image_id
    :return:
    port, cmd, args, base_url_env_key, base_url_env_value
    """
    docker_image_name = "".join(docker_image_name.split())
    log.debug("fetching extra attributes of docker image")
    # query database
    query_set = db.session\
        .query(DockerImageExtraAttribute)\
        .filter(DockerImageExtraAttribute.base_image_id == base_image_id)\
        .limit(1).all()
    cmd = None
    port = None
    args = None
    base_url_env_value = None
    base_url_env_key = None
    container_uid = None
    if query_set:
        for item in query_set:
            ingress_url = '/templates/{}/{}/{}-{}/'.format(hash_username(user_email_id),template_project,
                                                           docker_image_name, project)
            if item.cmd:
                cmd = json.loads(item.cmd)
            if item.port:
                port = int(item.port)
            if item.args:
                args = item.args.replace("BASE_URL_VALUE", ingress_url)
                args = json.loads(args)
            if item.base_url_env_value:
                base_url_env_value = item.base_url_env_value.replace("BASE_URL_VALUE", ingress_url)
                base_url_env_key = item.base_url_env_key

            if item.container_uid:
                container_uid = item.container_uid


            return port, cmd, args, base_url_env_key, base_url_env_value, ingress_url, container_uid
    else:
        log.error("Extra Attribute missing for docker image")
        return  "", "", "", "", "", "", ""

def fetch_tags(base_image_id):
    """
    The function fetches the tags for given image id
    Args:
        base_image_id : Base Docker Image Id of Template
    """
    query_set = db.session \
        .query(DockerImageTag.tag) \
        .filter(DockerImageTag.docker_image_id == base_image_id) \
        .all()
    return [tag for tag, in query_set] if query_set else []

def get_base_image_os(base_image_id):
    """
    The function that returns the base image operating system
    Args:
        base_image_id : Base Docker Image Id of Template
    """
    # Fetch OS of Parent Image
    tags = fetch_tags(base_image_id)
    os_key, os_val = get_tag_val("os", tags)
    log.debug('#THE OS IS : %s', os_val)
    return os_val if os_val else ""


def validate_repo(payload, resolve_pvt_repo=True):
    """
    validate repository access of user
    Args:
        payload: json
        resolve_repo: boolean
    Returns: json
    """
    # url = app.config["VCS_BASE_URL"]
    # headers = generate_headers(
    #     userid=g.user["mosaicId"],
    #     email=g.user["email_address"],
    #     username=g.user["first_name"],
    #     project_id=g.user['project_id']
    # )
    if payload["repo_name"] != "Default":
        try:
            if resolve_pvt_repo:
                # replace username and password from input parameter before validating
                # create a copy to prevent modification of original payload
                payload = _resolve_if_private_repo(copy.deepcopy(payload))
            repo_type = payload.get("repo_type", None)
            if repo_type in app.config.get('PROXY_ENABLED_GIT_PROVIDER', []):
                payload.update({"proxy_details": json.dumps(app.config["PROXY_DETAILS"])})
            # resp = requests.post(f"{url}/repo/validate", headers=headers, json=payload)
            response, code = View(project_id=g.user['project_id']).validate_git(payload)
            return response, code
        # pylint: disable=broad-except
        except Exception as ex:
            log.error(ex)
            raise ex
    return "Success", 200


def resolve_private_repo_creds(headers: dict, payload: dict, only_username=False) -> dict:
    """
    Method to resolve private repository input parameter variables used.
    :param only_username: resolve only the username in the dict
    :param headers: Headers used for api call
    :param payload: Dict Containing "username", and "password" keys
    :return: Updated Payload
    """
    user_params = {}
    _keys = {"username": payload["username"]}
    try:
        user_params = get_all_input_params(user_params, headers, app.config["INPUT_PARAM_BASE_URL"], g.user["mosaicId"],
                                           InputParamReferenceType.ref_type_user)
        if not only_username:
            _keys["password"] = payload["password"]
            payload["password"] = user_params[payload["password"]]
        payload["username"] = user_params[payload["username"]]
        return payload
    except Exception as ex:
        log.exception(ex)
        msg = "An error occurred while resolving git repo credentials. "
        if not isinstance(user_params, list):
            _key_string = ', '.join(_keys.values())
            msg += f"Please configure {_key_string} in the user level parameters."

        _keys["message"] = msg
        _keys = json.dumps(_keys)
        raise Exception(_keys)


def add_git_repo(payload, project_id):
    """
    Add git repo details in database
    Args:
        payload: json
        project_id: string
    Returns:
    """
    payload.update({"project_id": project_id})
    access_category = payload.get(RepoAccessCategory.name, RepoAccessCategory.PUBLIC)
    payload[RepoAccessCategory.name] = access_category
    try:
        resp, resp_code = validate_repo(payload)
        if resp_code == 200:
            # create repo
            repo_type = payload.get("repo_type", None)
            if repo_type == RepoType.AZUREDEVOPS:
                if '@' in payload.get('repo_url', ""):
                    payload['repo_url'] = "https://" + payload['repo_url'].split('@')[1]
            # R20-1107: Restricting duplicate repo name.
            if db.session.query(GitRepo.repo_id).filter_by(project_id=project_id).filter_by(repo_name=payload.get("repo_name")).first():
                log.exception("repo_name should be unique")
                raise ValidationError("repo_name should be unique")
            schema = schemas.GitRepo(strict=True)
            _payload, errors = schema.load(payload)
            if repo_type in app.config.get('PROXY_ENABLED_GIT_PROVIDER', []):
                _payload.update({"proxy_details": json.dumps(app.config["PROXY_DETAILS"])})
            git_repo = GitRepo(**_payload)
            db.session.query(GitRepo)\
                .filter(GitRepo.project_id == project_id)\
                .update(dict(repo_status=RepoStatus.Disabled))
            db.session.add(git_repo)
            db.session.flush()
            #create branch
            git_repo_branches = create_default_branch(git_repo.repo_id, payload["branch"])
            # create active branch for a user for given project
            add_to_active_repo(project_id, git_repo.repo_id, g.user["mosaicId"], git_repo_branches.branch_id)
            db.session.commit()
        return resp, resp_code
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        raise e


def list_git_repo(project_id, repo_status=None, remote_branches=True):
    """list git repo details based on project id."""
    try:
        #FETCH ENABLED REPO
        log.debug(f"Fetching active repos for this project")
        repositories_dict = get_active_repo(project_id)
        log.debug(f"repositories_dict: {repositories_dict}")
        repositories_dict, is_validator = get_user_role(repositories_dict)
        if repo_status:
            if repositories_dict and repositories_dict.get("repo_name", "").lower() == "default":
                repositories_dict["password"] = app.config["GIT_TOKEN"]
            repositories_dict = _resolve_if_private_repo(repositories_dict)
            return repositories_dict
        # FETCH REPO LISTING
        queries = [GitRepo.project_id == project_id]
        if is_validator:
            queries.append(func.lower(GitRepo.repo_name) != 'default')
        log.debug(f"Querying nb_git_repository table")
        repos = db.session\
            .query(GitRepo.repo_id, GitRepo.repo_status,
                   GitRepo.repo_type, GitRepo.repo_url, GitRepo.access_category,GitRepo.proxy_details,
                   GitRepo.repo_name, GitRepo.base_folder, GitRepo.username, GitRepo.password)\
            .filter(*queries)\
            .order_by(GitRepo.last_modified_on.asc())\
            .all()
        client = PasswordStoreFactory(app.config["PASSWORD_STORE"], GitRepo.__tablename__)
        repo_list = []
        for repo in repos:
            repo = repo._asdict()
            repo["password"] = client.retrieve(repo["password"])
            repo = _resolve_if_private_repo(repo)
            repo = prepare_branches(is_validator, repo, repositories_dict, remote_branches)
            repo.pop('password', None)
            repo_list.append(repo)
        return repo_list
    except MosaicException as ex:
        log.exception(ex)
        raise ex
    except Exception as e:
        log.exception(e)
        raise NoRepoException


def prepare_branches(is_validator, repo, repositories_dict, remote_branches, raise_=False):
    "Method prepares the branch list of given repository"
    is_active_repo = False
    active_branch = None
    if repositories_dict and repo['repo_id'] == repositories_dict["repo_id"]:
        is_active_repo = True
        repo['repo_status'] = "Enabled"
        active_branch = repositories_dict['branch']
        repo['branch'] = active_branch
    else:
        repo['repo_status'] = "Disabled"
    branches, branch_names, repo = list_nb_repo_branches(repo, is_validator, is_active_repo, active_branch)
    if remote_branches:
        if not is_validator:
            branches = list_git_branches(repo["repo_id"], branches, repo_details=repo, raise_=raise_)
        repo["branches"] = branches
    return repo


def list_nb_repo_branches(repo, is_validator, is_active_repo, active_branch):
    """List all branches from nb_git_repository_branches table"""
    branches = []
    branch_names = []
    nb_repo_branches = get_nb_git_repo_branches(repo, is_validator)
    for branch in nb_repo_branches:
        branch_names.append(branch.branch_name)
        branch_status = "Disabled"
        if is_active_repo and branch.branch_name == active_branch:
            branch_status = "Enabled"
            repo['branch_id'] = branch.branch_id
        elif not is_active_repo and branch.default_flag:
            repo['branch'] = branch.branch_name
            repo['branch_id'] = branch.branch_id
            branch_status = "Enabled"
        branch_dict = {"branch_name": branch.branch_name,
                       "branch_id": branch.branch_id,
                       "default_flag": branch.default_flag,
                       "freeze_flag": branch.freeze_flag,
                       "share_flag": branch.share_flag,
                       "branch_status": branch_status}
        branches.append(branch_dict)
    return branches, branch_names, repo


def list_git_branches(repo_id, branches, repo_details=None, raise_=False):
    """Fetch all branches from git repo"""
    consolidated_branch_list = []
    git_repo_branches = get_repo_branches(repo_id, repo_details, raise_)
    for git_branch in git_repo_branches:
        local_record = [x for x in branches if x['branch_name'] == git_branch['name']]
        if not local_record:
            local_record = [{"branch_name": git_branch['name'],
                             "branch_id": None,
                             "default_flag": False,
                             "freeze_flag": False,
                             "share_flag": False
                             }]
        consolidated_branch_list.extend(local_record)
    return consolidated_branch_list

def perfect_eval(data):
    if isinstance(data, dict):
        return data
    elif isinstance(data, str):
        data = json.dumps(data)
        if isinstance(data, str):
            data = json.loads(data)
            if isinstance(data, str):
                data = literal_eval(data)
                if isinstance(data, str):
                    raise ValueError(data)
    return data


def get_repo_branches(repo_id, repo_details, raise_) -> list:
    """Fetch all branches from git repo"""
    try:
        proxy_details = None
        repo_type = None
        obj = None
        if repo_details:
            obj = View(repo_details=perfect_eval(repo_details))
            repo_type = repo_details['repo_type']
        else:
            obj = View(repo_id=repo_id)
        if repo_type in app.config.get('PROXY_ENABLED_GIT_PROVIDER', []):
            proxy_details = json.dumps(app.config["PROXY_DETAILS"])
        response, code = obj.list_branches(proxy_details)
        # repo_type = None
        # headers = {"X-Auth-Userid": g.user["mosaicId"],
        #            "X-Auth-Username": g.user["first_name"],
        #            "X-Auth-Email": g.user["email_address"],
        #            "X-Project-Id": g.user.get('project_id', None),
        #            "X-Repo-Id": repo_id}

        # response = None
        # git_server_url = app.config["VCS_BASE_URL"]
        # get_repo_branches_url = git_server_url + \
        #     VcsURL.REPO_BRANCHES.format(repo_id)
        # response = requests.get(
        #     get_repo_branches_url,
        #     headers=headers)
        if code != 200:
            raise Exception(str(response, 'UTF-8'))
        return perfect_eval(response)
    except MosaicException as ex:
        log.exception(ex)
        raise ex
    except Exception as ex:
        log.exception(ex)
        raise ex

def _prepare_error_deatils(raise_, ex, repo_details, message):
    """prepare error details on failure of branch API"""
    log.exception(ex)
    if raise_ and message:
        response = {
            "message": message
        }
        raise Exception(response)
    elif raise_:
        raise ex
    repo_details[RepoMessages.ERROR_DETAILS] = {
        RepoMessages.ERROR_MESSAGE : message
    }
    return []



def get_nb_git_repo_branches(repo, is_validator):
    """Fetch data branches from nb_git_repo_branches"""
    try:
        log.debug("Inside get_nb_git_repo_branches")
        nb_git_repo_branches = db.session\
            .query(GitRepoBranches.branch_name, GitRepoBranches.default_flag,
                   GitRepoBranches.freeze_flag, GitRepoBranches.share_flag,
                   GitRepoBranches.branch_id)\
            .filter(GitRepoBranches.repo_id == repo['repo_id'])\
            .all()
        log.debug(nb_git_repo_branches)
        if is_validator and repo['repo_name'] != "Default":
            log.debug("Is Validator")
            repo_branches = [br for br in nb_git_repo_branches if br.share_flag]
            nb_git_repo_branches = repo_branches
        log.debug(nb_git_repo_branches)
        return nb_git_repo_branches
    except Exception as e:
        log.exception(e)
        raise e


def delete_git_repo(repo_id):
    """
    Delete repo details based on repo id.
    Args:repo_id: String
    Returns:
    """
    try:
        repository = db.session.query(GitRepo).get(repo_id)
        db.session.query(GitRepoBranches).filter(GitRepoBranches.repo_id == repo_id).delete()
        db.session.query(GitRepoActive).filter(GitRepoActive.repo_id == repo_id).delete()
        db.session.delete(repository)
        db.session.commit()
        delete_from_vault(repository.__tablename__, repository._password)# pylint: disable=protected-access
        return "Success"
    except Exception as e:
        log.exception(e)
        raise e


def delete_from_vault(tablename, key):
    """
    Function TO delete key from vault
    :param tablename:
    :param key:
    :return:
    """
    if app.config["PASSWORD_STORE"] == PasswordStore.VAULT:
        VaultEncrypter(prefix_path=tablename).delete(key)

# pylint: disable=singleton-comparison
def update_git_repo(payload, repo_id):
    """update git repository details based on repo id"""
    try:
        access_category = payload.get(RepoAccessCategory.name, RepoAccessCategory.PUBLIC)
        payload[RepoAccessCategory.name] = access_category
        resp, resp_code = validate_repo(payload)
        if resp_code == 200:
            payload.update({"last_modified_by": g.user["mosaicId"],
                            "last_modified_on": datetime.utcnow()})
            #UPDATE GIT REPO DETAILS
            repo = GitRepo.query.filter_by(repo_id=repo_id).first()
            key = repo._password # pylint: disable=protected-access
            tablename = repo.__tablename__
            for key, value in payload.items():
                setattr(repo, key, value)
            delete_from_vault(tablename, key)
            #UPDATE BRANCH DETAILS
            updated_branch_name = payload["branch"] if "branch" in payload.keys() else ""
            if updated_branch_name:
                db.session.query(GitRepoBranches) \
                    .filter(GitRepoBranches.repo_id == repo_id) \
                    .filter(GitRepoBranches.default_flag == True) \
                    .update(dict(default_flag=False))
                record_update_cnt = db.session.query(GitRepoBranches) \
                    .filter(GitRepoBranches.repo_id == repo_id) \
                    .filter(GitRepoBranches.branch_name == updated_branch_name) \
                    .update(dict(default_flag=True))
                if record_update_cnt <= 0:
                    create_default_branch(repo_id, updated_branch_name)
                repo_info = db.session.query(GitRepoBranches.repo_id,
                                             GitRepoBranches.branch_id,
                                             GitRepoBranches.branch_name) \
                    .filter(GitRepoBranches.repo_id == repo_id) \
                    .filter(GitRepoBranches.branch_name == updated_branch_name) \
                    .first()
                updated_repo_info = repo_info._asdict()
                updated_repo_info['new_repo_id'] = updated_repo_info.pop('repo_id')
                switch_git_repo(g.user["project_id"], updated_repo_info)
        db.session.commit()
        return resp, resp_code
    except Exception as e:
        log.exception(e)
        raise e


def switch_git_repo(project_id, payload):
    """update git repository details based on repo id"""
    try:
        new_repo_id = payload['new_repo_id']
        branch_name = payload.get("branch_name", "")
        new_branch_id = payload.get("branch_id", "")
        git_repo_dict = get_git_repo(new_repo_id)
        if branch_name:
            git_repo_dict["branch"] = branch_name
        resp_text, resp_code = validate_repo(git_repo_dict, resolve_pvt_repo=False)
        if resp_code != 200:
            raise Exception(resp_text)
        if branch_name:
            db_record = db.session.query(GitRepoBranches) \
                .filter(GitRepoBranches.repo_id == new_repo_id) \
                .filter(GitRepoBranches.branch_name == branch_name) \
                .first()
            if db_record:
                new_branch_id = db_record.branch_id
            else:
                git_repo_branches = create_default_branch(new_repo_id, branch_name, default_flag=False)
                new_branch_id = git_repo_branches.branch_id
        update_cnt = db.session.query(GitRepoActive) \
            .filter(GitRepoActive.project_id == project_id) \
            .filter(GitRepoActive.username == g.user["mosaicId"]) \
            .update(dict(repo_id=new_repo_id, branch_id=new_branch_id))
        if update_cnt == 0:
            add_to_active_repo(project_id, new_repo_id, g.user["mosaicId"], new_branch_id)
        db.session.commit()
        return "Success"
    except Exception as e:
        log.exception(e)
        raise e


def fetch_base_image_details_for_custom_build(base_image_id):
    """ Returns base image details for custom template"""
    query_set = db.session\
        .query(DockerImage)\
        .filter(DockerImage.id == base_image_id)\
        .limit(1).all()
    if query_set:
        base_image_details = []
        for item in query_set:
            base_image_details.append(item.as_dict())
    return base_image_details[0]


def base_version_tag(base_image_id):
    """ Returns base image details for custom template"""
    query_set = db.session.query(DockerImageTag.tag).filter(DockerImageTag.docker_image_id == base_image_id, DockerImageTag.tag.like('version%')).first()
    version = 'default' if query_set is None else query_set[0].split('=')[1]
    return version


def get_git_repo(repo_id):
    """Get repo details based on repo id."""
    try:
        repository = db.session \
            .query(GitRepo.repo_id,
                   GitRepo.project_id,
                   GitRepo.repo_url,
                   GitRepo.username,
                   GitRepo.password,
                   GitRepo.repo_name,
                   GitRepo.repo_status,
                   GitRepo.base_folder,
                   GitRepo.repo_type,
                   GitRepo.access_category,
                   GitRepo.proxy_details,
                   GitRepoBranches.branch_name.label("branch")) \
            .join(GitRepoBranches, (GitRepoBranches.repo_id == GitRepo.repo_id), isouter=True) \
            .filter((GitRepoBranches.default_flag == True) & (GitRepo.repo_id == repo_id))\
            .first()
        repositories_dict = repository._asdict()
        client = PasswordStoreFactory(app.config["PASSWORD_STORE"], GitRepo.__tablename__)
        repositories_dict["password"] = client.retrieve(repositories_dict["password"])
        repositories_dict, is_validator = get_user_role(repositories_dict)
        repositories_dict = _resolve_if_private_repo(repositories_dict)
        return repositories_dict if repositories_dict else {}
    except Exception as e:
        log.exception(e)
        raise e


def _resolve_if_private_repo(repositories_dict: dict) -> dict:
    """
    :param repositories_dict:
    :return:
    """
    try:
        repo_obj, is_validator = get_user_role()
    except Exception as ex:
        log.exception(ex)
        raise ex
    validator_sa_flag = app.config.get('VALIDATOR_SA_FLAG', False)
    if repositories_dict.get(RepoAccessCategory.name, "") == RepoAccessCategory.PRIVATE\
            and not (validator_sa_flag and is_validator):
        headers = generate_headers(
            userid=g.user["mosaicId"],
            email=g.user["email_address"],
            username=g.user["first_name"],
        )
        repositories_dict = resolve_private_repo_creds(headers, repositories_dict)
    return repositories_dict


def get_subscriber_info(user_id, key, product_id):
    """Fetch subscriber info for the user"""
    try:
        log.debug("Get Subscriber Info")
        request_url = "{}/v1/subscriber/{}/validate".format(app.config["METERING_BACKEND_URL"], user_id)
        log.debug(f"product_id: '{product_id}'")
        if not product_id:
            product_id = "MOSAIC_AI"
        payload = {"key_list": [key], "product_id": product_id}
        log.debug(f"payload: {payload}")
        data = requests.post(request_url, json=payload, headers={"X-Auth-Userid": user_id})
        log.debug(request_url)
        log.debug(data.json())
        return data.json()
    # pylint: disable = broad-except
    except ConnectionError as ex:
        raise ServiceConnectionError(msg_code="SERVICE_CONNECTION_ERROR_002")
    except Exception as ex:
        log.exception(ex)


def validate_subscriber_info(subscriber_info):
    """Validate subscriber info to allow resource usage"""
    if not subscriber_info["subscriber_id"]:
        raise NoSubscriptionException
    # pylint: disable=line-too-long
    if datetime.strptime(subscriber_info["end_date"], '%a, %d %b %Y %H:%M:%S GMT').date() < date.today():
        raise SubscriptionExpiredException
    if not subscriber_info["has_user_resource"]:
        raise UserQuotaExceededException
    if not subscriber_info["has_project_resource"]:
        raise ProjectQuotaExceededException
    if not subscriber_info["has_subscriber_resource"]:
        raise SubscriptionExceededException


def fetch_resource_info(resource_type, resource_value):
    """Fetch type and amount of resource requested"""
    try:
        if resource_type == 'cpu':
            key = "cpu_hours"
        else:
            key = "gpu_hours"
        if resource_value.endswith("m"):
            resource_request = int(resource_value[:-1])/1000
        else:
            resource_request = int(resource_value)
        return key, resource_request
    # pylint: disable = broad-except
    except Exception as ex:
        log.exception(ex)


def get_user_role(git_repo_object=None):
    """ Checks the user role and update git info to SA details if role is validator"""
    try:
        project_ids = app.config.get('PROJECT_LIST', [])
        current_project_id = g.user.get('project_id', None)
        if current_project_id and current_project_id in project_ids:
            return git_repo_object, False
        is_validator = g.user.get("project_access_type", "").upper() == Accesstype.VALIDATOR
        if is_validator and git_repo_object:
            validator_sa_flag = app.config.get('VALIDATOR_SA_FLAG', False)
            log.debug("# THE VALIDATOR SA FLAG IS : %s ", validator_sa_flag)
            if validator_sa_flag:
                log.debug("# FOUND VALIDATOR ROLE FOR PROJECT : %s ", current_project_id)
                git_repo_object['username'] = app.config['GIT_NAMESPACE']
                git_repo_object['password'] = app.config['GIT_TOKEN']
        return git_repo_object, is_validator
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        raise UserRoleException


def get_active_repo(project_id):
    """ Check the active repo for the given project """
    try:
        active_repo = get_currently_active_repo(project_id)
        repositories_dict = active_repo._asdict() if active_repo \
            else get_default_repo_activated(project_id)
        if repositories_dict:
            client = PasswordStoreFactory(app.config["PASSWORD_STORE"], GitRepo.__tablename__)
            repositories_dict["password"] = client.retrieve(repositories_dict["password"])
        return repositories_dict
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        raise NoRepoException


def get_default_repo_activated(project_id):
    """Method returns the default repo of a project for a user"""
    repositories_dict = {}
    repo_obj, is_validator = get_user_role()
    if not is_validator:
        active_repo = db.session \
            .query(GitRepo.repo_id,
                   GitRepo.project_id,
                   GitRepo.repo_url,
                   GitRepo.username,
                   GitRepo.password,
                   GitRepo.repo_name,
                   GitRepo.repo_status,
                   GitRepo.base_folder,
                   GitRepo.repo_type,
                   GitRepo.access_category,
                   GitRepo.proxy_details,
                   GitRepoBranches.branch_id,
                   GitRepoBranches.branch_name.label("branch"),
                   GitRepoBranches.freeze_flag) \
            .join(GitRepoBranches, GitRepo.repo_id == GitRepoBranches.repo_id) \
            .filter(GitRepo.project_id == project_id) \
            .filter(func.lower(GitRepo.repo_name) == "default") \
            .filter(GitRepoBranches.default_flag == True) \
            .order_by(GitRepo.last_modified_on.asc()) \
            .first()
        repositories_dict = active_repo._asdict() if active_repo else {}
        if repositories_dict:
            add_to_active_repo(project_id, repositories_dict["repo_id"],
                               g.user["mosaicId"], repositories_dict["branch_id"])
    return repositories_dict


def get_currently_active_repo(project_id):
    """Method returns currently active repo of a project for a user"""
    # NOTE : Removed username filter from below filter, 
    # changed order_by to 'created_on' for FDC release 
    queries = [GitRepoActive.project_id == project_id]
    repo_obj, is_validator = get_user_role()
    if is_validator:
        queries.append(func.lower(GitRepo.repo_name) != 'default')
    active_repo = db.session \
        .query(GitRepo.repo_id,
               GitRepo.project_id,
               GitRepo.repo_url,
               GitRepo.username,
               GitRepo.password,
               GitRepo.repo_name,
               GitRepo.repo_status,
               GitRepo.base_folder,
               GitRepo.repo_type,
               GitRepo.access_category,
               GitRepo.proxy_details,
               GitRepoActive.branch_id,
               GitRepoBranches.branch_name.label("branch"),
               GitRepoBranches.freeze_flag) \
        .join(GitRepoActive, GitRepoActive.repo_id == GitRepo.repo_id) \
        .join(GitRepoBranches, GitRepoBranches.branch_id == GitRepoActive.branch_id) \
        .filter(*queries) \
        .order_by(GitRepo.created_on.asc()) \
        .first()
    return active_repo


def get_branch_by_repo_id(repo_id, project_id):
    """Fetch nb_branch info based on repo and project"""
    # pylint: disable=singleton-comparison
    branches = db.session \
        .query(GitRepo.repo_id,
               GitRepo.project_id,
               GitRepo.username,
               GitRepoBranches.branch_name,
               GitRepoBranches.default_flag,
               GitRepoBranches.freeze_flag,
               GitRepoBranches.share_flag,
               GitRepoBranches.branch_id) \
        .join(GitRepoBranches, GitRepoBranches.repo_id == GitRepo.repo_id) \
        .filter(GitRepo.repo_id == repo_id) \
        .filter(GitRepo.project_id == project_id) \
        .order_by(GitRepo.last_modified_on.asc()) \
        .all()
    return branches


def get_ad_user_groups(mosaic_user):
    """
    Get list of groups of a user
    Args:mosaic_user: mosaic user_id
    Returns:list of group dict
    """
    users = db.session \
        .query(AdMapping) \
        .join(AdUser, AdMapping.user_id == AdUser.user_id) \
        .join(AdGroup, AdGroup.group_id == AdMapping.group_id).filter(AdUser.mosaic_user == mosaic_user)\
        .with_entities(AdUser.user_id, AdUser.user_name, AdGroup.group_name, AdGroup.group_id)
    user_list = []
    for user in users:
        user_group_mapping = {"user_id": user.user_id, "user_name": user.user_name, "group_name": user.group_name,
                              "group_id": user.group_id}
        user_list.append(user_group_mapping)
    return user_list


def create_jupyter_command(command, arguments):
    """Create juputerhub/jupyterlab run command in case of user impersonation"""
    run_command = ""
    run_command = command
    for arg in arguments:
        run_command = run_command + " " + arg
    return run_command


def update_branch_metadata(payload):
    """
    Updates the branch metadata or creates new branch locally
    Args:
        payload: json
    Returns:
    """
    try:
        for branch in payload:
            git_branch = GitRepoBranches(**branch)
            if git_branch.branch_id:
                db.session.query(GitRepoBranches) \
                    .filter(GitRepoBranches.branch_id == git_branch.branch_id) \
                    .update(dict(freeze_flag=git_branch.freeze_flag,
                                 share_flag=git_branch.share_flag))
            else:
                db.session.add(git_branch)
        db.session.flush()
        db.session.commit()
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        raise e

def create_default_branch(repo_id, branch_name, default_flag=True):
    """Create Default Branch for given repo id"""
    git_repo_branches = GitRepoBranches(repo_id=repo_id,
                                        branch_name=branch_name,
                                        default_flag=default_flag)
    db.session.add(git_repo_branches)
    db.session.flush()
    return git_repo_branches


def add_to_active_repo(project_id, repo_id, username, branch_id):
    """Add to active repo"""
    not_exist = db.session.query(GitRepoActive)\
                 .filter(GitRepoActive.project_id == project_id)\
                 .filter(GitRepoActive.username == username) \
                 .first() is None
    if not_exist:
        git_repo_active = GitRepoActive(repo_id=repo_id,
                                        project_id=project_id,
                                        username=username,
                                        branch_id=branch_id)
        db.session.add(git_repo_active)
        db.session.flush()
        db.session.commit()


def get_user_impersonation_details(mosaic_id, env):
    """
    Get user details for impersonation
    Args:
        mosaic_id:

    Returns:
    """
    # fetch UID and GID from database
    user_group_mapping = get_ad_user_groups(mosaic_id)
    user_imp_data = {}

    # set user and group info manually in case of no data in db
    if len(user_group_mapping) == 0:
        mosaic_user_name = parse_username(mosaic_id)
        mosaic_user_id = str(10001)
        env["user_name"] = env["group_name_1"] = mosaic_user_name
        env["user_id"] = env["group_id_1"] = mosaic_user_id
        env["number_of_groups"] = str(1)
        user_imp_data["supplemental_groups"] = []
    else:
        user_imp_data["supplemental_groups"] = []
        for i, user in enumerate(user_group_mapping, 1):
            env["group_name_{}".format(i)] = parse_username(user["group_name"])
            env["group_id_{}".format(i)] = str(user["group_id"])
            user_imp_data["supplemental_groups"].append(int(user["group_id"]))
        env["number_of_groups"] = str(len(user_group_mapping))
        env["user_name"] = parse_username(user_group_mapping[0]['user_name'])
        env["user_id"] = str(user_group_mapping[0]['user_id'])

    return env, user_imp_data


def parse_username(username):
    """
    Update username to comply with ubuntu/fedora username policy
    Args:
        username: username string
    Returns:
        username after changes
    """
    mosaic_user_name = username.split("@")[0]
    mosaic_user_name = app.config.get("USER_IMPERSONSATION_PREFIX", "A") + mosaic_user_name \
        if mosaic_user_name.isnumeric() else mosaic_user_name
    return mosaic_user_name


def create_pod_metrics(metrics_data):
    """
    Create Pod Metrics
    Args:
        metrics_data:Pod Metrics Data

    Returns: NotebookPodMetrics
    """
    data = copy.deepcopy(metrics_data)
    # parse extra data
    user = g.user["mosaicId"]
    data['created_by'] = user
    data['updated_by'] = user
    log.debug("Creating notebook pod metrics object")
    notebook_pod_metrics = NotebookPodMetrics(**data)
    try:
        # save notebook pod metrics object
        metrics = db.session.merge(notebook_pod_metrics)
        db.session.add(metrics)
        db.session.commit()

    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        db.session.rollback()

    return notebook_pod_metrics


def download_report(data):
    """
    To download a report for notebooks utilisation
    Args:
        data:Pod Metrics Data

    Returns: Report CSV file
    """

    start_time = datetime.strptime(data['from_date'] + " 00:00:00", "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(data['to_date'] + " 23:59:59", "%Y-%m-%d %H:%M:%S")

    log.debug("Inside download_report")

    try:
        temp_dir = tempfile.mkdtemp()
        file_name = ReportFiles.notebooks_report
        temp_file = os.path.join(temp_dir, file_name)

        # get data from db
        report_data = db.session \
            .query(NotebookPodMetrics.created_by,
                   func.sum(NotebookPodMetrics.max_cpu).label("cup_used"),
                   func.sum(NotebookPodMetrics.max_memory).label("memory_used"),
                   func.avg(NotebookPodMetrics.max_cpu).label("avg_cpu"),
                   func.avg(NotebookPodMetrics.max_memory).label("avg_memory")) \
            .filter(((NotebookPodMetrics.created_on >= start_time)
                     & (NotebookPodMetrics.created_on <= end_time))) \
            .group_by(NotebookPodMetrics.created_by) \
            .all()

        user_list = []
        for user in report_data:
            user_group_mapping = {
                "User": user.created_by,
                "Total CPU Used": user.cup_used,
                "Total Memory Used": user.memory_used,
                "AVG CPU": user.avg_cpu,
                "AVG Memory": user.avg_memory,
            }
            user_list.append(user_group_mapping)

        df = pd.DataFrame(user_list)
        df.to_csv(temp_file, index=False)

        @after_this_request
        def remove_file(response):
            shutil.rmtree(temp_dir)
            return response

        return temp_dir, file_name

    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        raise e


def get_ad_user_info(mosaic_user=None):
    """
    Get user information from ad tables
    Args:
        mosaic_user: mosaic user_id
    Returns:
        list of user info dict
    """
    if mosaic_user:
        user_data = AdUser.query.filter(AdUser.mosaic_user == mosaic_user).first()
        user_data = user_data.as_dict() if user_data else []
        user_mapping = AdMapping.query\
            .join(AdUser, AdMapping.user_id == AdUser.user_id)\
            .join(AdGroup, AdGroup.group_id == AdMapping.group_id) \
            .with_entities(AdUser.mosaic_user, AdUser.user_id, AdUser.user_name, AdGroup.group_name, AdGroup.group_id)\
            .filter(AdUser.mosaic_user == mosaic_user)
    else:
        user_data = AdUser.query.all()
        user_data = [x.as_dict() for x in user_data]
        group_data = AdGroup.query.all()
        group_data = [x.as_dict() for x in group_data]
        user_mapping = AdMapping.query \
            .join(AdUser, AdMapping.user_id == AdUser.user_id) \
            .join(AdGroup, AdGroup.group_id == AdMapping.group_id) \
            .with_entities(AdUser.mosaic_user, AdUser.user_id, AdUser.user_name, AdGroup.group_name, AdGroup.group_id)

    user_mapping_info = {}
    for user in user_mapping:
        group_details = {"group_name": user.group_name, "group_id": user.group_id}
        mosaic_user_id = user.mosaic_user
        if mosaic_user_id not in user_mapping_info:
            user_mapping_info[mosaic_user_id] = [group_details]
        else:
            user_mapping_info[mosaic_user_id].append(group_details)

    if mosaic_user:
        return {"user_mapping_info": user_mapping_info, "user_data": user_data}
    return {"user_mapping_info": user_mapping_info, "user_data": user_data, "group_data": group_data}


def add_user_group_details(data):
    """
    Add User group details in user impersonation tables
    Args:
        data: dict containing user_details and group_details
    Returns:
    """
    try:
        user_details = data.get("user_detail", [])
        group_details = data.get("group_detail", [])
        mapping_details = data.get("user_group_mapping", [])
        users = []
        groups = []
        mappings = []
        for user in user_details:
            user_object = AdUser(user_id=user.get("user_id"),
                                 user_name=user.get("user_name"),
                                 mosaic_user=user.get("mosaic_user_id"))
            users.append(user_object)
        db.session.bulk_save_objects(users)
        db.session.flush()

        for group in group_details:
            group_object = AdGroup(group_id=group.get("group_id"),
                                   group_name=group.get("group_name"))
            groups.append(group_object)
        db.session.bulk_save_objects(groups)
        db.session.flush()

        for mapping in mapping_details:
            user_id = mapping.get("user_id")
            group_list = mapping.get("group_id")
            for group_id in group_list:
                mapping_object = AdMapping(user_id=user_id,
                                           group_id=group_id)
                mappings.append(mapping_object)
        db.session.bulk_save_objects(mappings)
        db.session.flush()

        db.session.commit()
        return "Data inserted successfully"
    except Exception as e:
        db.session.rollback()
        log.info(e)
        raise e


def delete_user_group_details(data):
    """
    Delete User group details in user impersonation tables
    Args:
        data: dict containing user_details and group_details
    Returns:
    """
    try:
        user_ids = data.get("user_ids", [])
        group_ids = data.get("group_ids", [])
        mapping_details = data.get("user_group_mapping", [])

        # delete user and all it's mappings
        for user_id in user_ids:
            user_object = AdUser.query.filter(AdUser.user_id == user_id).delete()
            db.session.flush()

            group_mapping = AdMapping.query.filter(AdMapping.user_id == user_id).delete()
            db.session.flush()

        # delete groups and all it's mapping
        for group_id in group_ids:
            group_object = AdGroup.query.filter(AdGroup.group_id == group_id).first()
            db.session.delete(group_object)
            db.session.flush()

            group_mapping = AdMapping.query.filter(AdMapping.group_id == group_id).delete()
            db.session.flush()

        # delete user-group mappings
        for mapping in mapping_details:
            user_id = mapping.get("user_id")
            groups = mapping.get("group_id")
            for group_id in groups:
                mapping_object = AdMapping.query.filter(
                    AdMapping.group_id == group_id, AdMapping.user_id == user_id).delete()
                db.session.flush()

        db.session.commit()
        return "Data deleted successfully"
    except Exception as e:
        db.session.rollback()
        log.info(e)
        raise e


def update_user_group_mappings(data):
    """
    Update User group details in user impersonation tables
    Args:
        data: dict containing user group mapping details
    Returns:
    """
    try:
        mapping = data.get("user_group_mapping", {})
        user_id = mapping.get("user_id")
        groups = mapping.get("group_id")

        existing_mappings = AdMapping.query.filter(AdMapping.user_id == user_id).delete()
        db.session.flush()
        if existing_mappings > 0:
            mappings = []
            for group_id in groups:
                mapping_object = AdMapping(user_id=user_id,
                                           group_id=group_id)
                mappings.append(mapping_object)
            db.session.bulk_save_objects(mappings)

            db.session.commit()
            return "Data updated successfully", 200
        return "Not data available to update", 204
    except Exception as e:
        db.session.rollback()
        log.info(e)
        raise e


def update_user_details(data, user_id):
    """
    Update User details in user impersonation tables
    """
    try:
        user: AdUser = AdUser.query.filter(AdUser.user_id == user_id).first()
        if user:
            new_user_name = data.get("user_name")
            user.user_name = new_user_name
            db.session.commit()
            return "Success", 200
        return "Not data available to update", 204
    except Exception as e:
        db.session.rollback()
        log.info(e)
        raise e


def update_group_details(data, group_id):
    """
    Update Group details in user impersonation tables
    """
    try:
        group: AdGroup = AdGroup.query.filter(AdGroup.group_id == group_id).first()
        if group:
            new_group_name = data.get("group_name")
            group.group_name = new_group_name
            db.session.commit()
            return "Success", 200
        return "Not data available to update", 204
    except Exception as e:
        db.session.rollback()
        log.info(e)
        raise e


def init_empty_git_repo(repo_details):
    """
    This API initialize a empty git repository.
    """
    try:
        repo_details = _resolve_if_private_repo(copy.deepcopy(repo_details))
        # headers = {"X-Auth-Userid": g.user["mosaicId"],
        #            "X-Auth-Username": g.user["first_name"],
        #            "X-Auth-Email": g.user["email_address"],
        #            "X-Project-Id": g.user.get('project_id', None),
        #            "Enabled-Repo": json.dumps(repo_details)}
        payload = {
            "branch":repo_details.get("branch", "master"),
            "default_branch_flag":"true"
        }
        # create_branch_url = app.config["VCS_BASE_URL"]+VcsURL.CREATE_BRANCH
        # res = requests.post(create_branch_url, headers=headers, json=payload)
        response, code = View(repo_details=json.dumps(repo_details)).create_branch(payload)
        if code != 201:
            raise Exception(response)
        return response, code
    except Exception as e:
        log.exception(e)
        raise e

def fetch_git_branches(payload):
    """
    Method fetches the active list of git branches from git server.
    """
    payload = _resolve_if_private_repo(copy.deepcopy(payload))
    return list_git_branches(None, [], repo_details=payload, raise_=True)


def hash_username(username: str) -> str:
    """
    Returns MD5 hash of username
    :param username:
    :return:
    """
    return hashlib.md5(str(username).encode("utf-8")).hexdigest()


def get_resource_details(notebook, resource_type):
    """
    Returns the database table contents from NotebookPodResources table
    Args: resource_type (string) type of resource cpu or memory
    """
    pod_limit_resources = {}
    pod_request_resource = {}
    if notebook.get(resource_type).get('extra') != "cpu":
        if notebook.get(resource_type).get('extra').lower() == "nvidia":
            pod_limit_resources = pod_metrics_summary.fetch_resource_limitscaling_guarantee(
                notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'), "nvidia",
                app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"],
                app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"])
            pod_request_resource = pod_metrics_summary.fetch_resource_request_limit(
                notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'),
                app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"],
                app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"], "nvidia")
        elif notebook.get(resource_type).get('extra').lower() == "amd":
            pod_request_resource = pod_metrics_summary.fetch_resource_request_limit(
                notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'),
                app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"],
                app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"], "amd")
            pod_limit_resources = pod_metrics_summary.fetch_resource_limitscaling_guarantee(
                notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'), "amd",
                app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"],
                app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"])

        docker_url = notebook.get('docker_image').get('gpu_docker_url')
    else:
        docker_url = notebook.get('docker_image').get('docker_url')
        pod_limit_resources = pod_metrics_summary.fetch_resource_limitscaling_guarantee(
            notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'), None,
            app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"],
                app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"])
        pod_request_resource = pod_metrics_summary.fetch_resource_request_limit(
            notebook.get(resource_type).get('cpu'), notebook.get(resource_type).get('mem'),
            app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"],
            app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"])
    return pod_limit_resources, pod_request_resource, docker_url


def get_all_branches(repo_id):
    """
    fetch all branches from database and remote.
    Args:
        repo_id (str):

    Returns: repo branch list

    """
    try:
        repo = get_git_repo(repo_id)
        repo, is_validator = get_user_role(repo)
        repo = prepare_branches(is_validator, repo, repositories_dict={}, remote_branches=True, raise_=True)
        return repo.get("branches", [])
    except Exception as e:
        log.exception(e)
        raise e

def get_input_params(notebook_id, jwt, headers, project_id=None, is_scheduled_job=False):
    """

    :param notebook_id:
    :param jwt:
    :param headers:
    :param project_id:
    :param is_scheduled_job
    :return:
    """
    # dict of env variables to set in the container
    env = {}
    # get input params
    try:
        url = app.config["INPUT_PARAM_BASE_URL"]
        if project_id:
            log.debug("Inside get_project_input_params, project_id: %s", project_id)
            env = get_all_input_params(env, headers, url, project_id,
                                       InputParamReferenceType.ref_type_project)

        log.debug("Inside get_notebook_params, notebook_id: %s", notebook_id)
        env = get_all_input_params(env, headers, url, notebook_id,
                                   InputParamReferenceType.ref_type_notebook)

        log.debug("Inside get_user_input_params")
        env = get_all_input_params(env, headers, url, g.user["mosaicId"],
                                   InputParamReferenceType.ref_type_user)
        return env

    # pylint: disable=broad-except
    except Exception as e:
        log.error(e)
        return jsonify("Error in getting input params")

def get_envs(notebook_id, jwt, headers, project_id=None, is_scheduled_job=False):

    # updating the token generated and connector variables in env dictionary
    # For schedyled job its value is True, for others its default value is False
    env={}
    if is_scheduled_job:
        env.update(TOKEN=jwt,
                   UID=app.config["UID"],
                   CONNECTOR_PYTHON_HOST=app.config["CONNECTOR_PYTHON_HOST_SCHEDULE_JOB"],
                   CONNECTOR_PYTHON_PORT=app.config["CONNECTOR_PYTHON_PORT"],
                   CONNECTOR_BASE_URL=app.config["CONNECTOR_BASE_URL_SCHEDULE_JOB"],
                   DB_URL=app.config["DB_URL"])
    else:
        env.update(TOKEN=jwt,
                   UID=app.config["UID"],
                   CONNECTOR_PYTHON_HOST=app.config["CONNECTOR_PYTHON_HOST"],
                   CONNECTOR_PYTHON_PORT=app.config["CONNECTOR_PYTHON_PORT"],
                   CONNECTOR_BASE_URL=app.config["CONNECTOR_BASE_URL"],
                   DB_URL=app.config["DB_URL"])
    return env


def create_token():
    """
    For creating JWt token
    Returns: jwt

    """
    data = {"userid": g.user["mosaicId"], "username": g.user["first_name"], "useremail": g.user["email_address"]}
    encoded_jwt = create_jwt(data)
    final_jwt = encoded_jwt.encode("utf-8").decode("utf-8")
    return final_jwt


def create_jwt(data):
    """Creates jwt token"""
    secret = app.config["JWT_SECRET"]
    algorithm = app.config["JWT_ALGORITHM"]
    return jwt.encode(data, secret, algorithm=algorithm)


def get_project_details(project_id):
    console_url = app.config["CONSOLE_BACKEND_URL"]
    headers = generate_headers(
        userid=g.user["mosaicId"],
        email=g.user["email_address"],
        username=g.user["first_name"],
        project_id=project_id,
    )

    project_details_url = f"{console_url}/secured/api/project/v1/{project_id}"
    response = requests.get(project_details_url, headers=headers)
    if response.status_code == 200:
        response_json = response.json()
        return response_json
    raise FetchProjectDetailException


def get_template_url_details(pod_name):
    """
    This function accepts pod_name as its argument and returns the database object 
    Get project id, template_id and user details from TemplateStatus
    table and return it
    pod_name: (str) name of the pod
    """
    return db.session.query(TemplateStatus.project_id, TemplateStatus.template_id,
                            TemplateStatus.created_by) \
        .filter(TemplateStatus.pod_name == pod_name) \
        .first()


def save_pod_resource_details(new_pods_list=[], existing_pods=[], resource_type=""):
    """
    Saves pod resource details to NotebookPodResources table
    Args:
    new_pods_list: list of pods containing pod names and its details
    existing_pods: list of pods containing pod names and its details
    resource_type: (string) type of resource either cpu or memory
    """
    try:
        if new_pods_list or existing_pods:
            db.session.query(NotebookPodResources) \
                .filter(NotebookPodResources.resource_type == resource_type).delete()
            db.session.commit()
            for each_pod in new_pods_list:
                pod_data = NotebookPodResources(new_pods=each_pod[0], usage_percent=each_pod[1],
                                                resource_type=each_pod[2], project_id=each_pod[3],
                                                project_name=each_pod[4], template_name=each_pod[5],
                                                template_id=each_pod[6], user_name=each_pod[7],
                                                alert_status=each_pod[8])
                db.session.add(pod_data)

            for each_pod in existing_pods:
                pod_data = NotebookPodResources(existing_pods=each_pod[0], usage_percent=each_pod[1],
                                                resource_type=each_pod[2], project_id=each_pod[3],
                                                project_name=each_pod[4], template_name=each_pod[5],
                                                template_id=each_pod[6], user_name=each_pod[7],
                                                alert_status=each_pod[8])
                db.session.add(pod_data)
            db.session.commit()
    except Exception as e:
        log.error(e)
        db.session.rollback()


def clear_pod_resource_details(resource_type=""):
    """
    This method clears the nb_pod_resource_alerts tables based on resource_type
    resource_type (string) - type of resource (cpu or memory)
    """
    try:
        db.session.query(NotebookPodResources) \
            .filter(NotebookPodResources.resource_type == resource_type) \
            .delete()
        db.session.commit()
    except Exception as err:
        log.error(err)
        db.session.rollback()


def get_docker_template_name(template_id):
    """
    Returns the template name from DockerImage table by using the template_id
    Args:
    template_id: (string) template id of docker template
    """
    try:
        template_name = db.session.query(DockerImage.name) \
            .filter(DockerImage.id == template_id).first()
        if template_name:
            return template_name
        else:
            return "",
    except Exception as err:
        log.error(str(err))
        return "",



def get_pod_resource_details(resource_type=""):
    """
    Returns pod usage details from the database table NotebookPodResources
    based on the resource type
    """
    nb_resource_details = db.session.query(NotebookPodResources.new_pods,
                                           NotebookPodResources.existing_pods,
                                           NotebookPodResources.alert_status) \
        .filter(NotebookPodResources.resource_type == resource_type) \
        .all()
    return nb_resource_details


def fetch_pod_usage(pod_name):
    """
    Fetches the pod cpu, memory utilization for a given pod and
    returns it back
    Args: pod_name (string) name of the pod
    """
    pods_usage = db.session.query(NotebookPodResources.resource_type,
                                  NotebookPodResources.usage_percent,
                                  NotebookPodResources.template_name,
                                  NotebookPodResources.project_name) \
        .filter(or_(NotebookPodResources.new_pods == pod_name,
                    NotebookPodResources.existing_pods == pod_name)).all()
    return pods_usage or []


def compare_pods_list(db_pods, incoming_pods):
    """
    This method takes two arguments and compares the database pods to the pods
    list coming in incoming request and if the pod names coming in the incoming
    request is present in db_pods then it is appended to pod_to_db list
    Args:
    db_pods (set) list of pods names coming from database table
    incoming_pods list of pod details coming from alerts manager
    returns list of pods to save in database
    """
    db_pods = list(db_pods)
    pods_to_db = []
    for i, each in enumerate(incoming_pods):
        if each[0] in db_pods:
            pods_to_db.append(incoming_pods[i])
    return pods_to_db


def bell_notification_payload(nb_user_id, nb_project_id, nb_template_id, message):
    """
    This function creates the payload and headers required by Lens notification
    service and returns the g_headers and payload json
    Args:
    nb_user_id: str username
    nb_project_id: str project_id
    nb_template_id: str temp;ate_id
    message: str alerying message
    """
    g_headers = {
        'X-Auth-Userid': nb_user_id,
        'X-Auth-Username': nb_user_id,
        'X-Auth-Email': nb_user_id,
        'x-project-id': nb_project_id
    }

    notification_payload = {
        "user_id": nb_user_id,
        "status": "Success",
        "uuid": str(uuid4()),
        "notificationURL": f"/ai/notebooks/{nb_project_id}/template/{nb_template_id}",
        "notificationDescription": message,
        "notificationType": "Notebooks",
        "createdBy": nb_user_id,
        "notificationDetails": {
            "senderName": nb_user_id,
            "accessType": "FullAccess",
        },
    }
    return g_headers, notification_payload


def email_user_payload(nb_project_id, nb_template_id, message, subject, additional_description, nb_user_id):
    """
    This function creates the payload for sending email notification through AiOPS Notification Service
    post api of User Management is called to fetch first name & user email against the user id
    Arguments:
    nb_project_id: str project_id
    nb_template_id: str notebooks template id
    message: str Alert message string which will be inserted in email body
    subject: str Subject of the email
    additional_description: str email body text
    nb_user_id: str username which will be used in user management api for getting
                the user details like firstname, email address
    """
    user_mgm_url = app.config["USER_MANAGEMENT_URL"] + "/user/completeuserinfo"
    user_details = requests.post(url=user_mgm_url, json=nb_user_id)
    user_details = user_details.json()
    first_name = user_details["firstName"]
    user_email = user_details["email"]
    email_template_id = app.config["EMAIL_TEMPLATE_ID"]
    email_config_identifier = app.config["EMAIL_CONFIG_IDENTIFIER"]
    email_notification_payload = {
        "template_id": email_template_id,
        "config_identifier": email_config_identifier,
        "subject": subject,
        "template_params": {
            "alert_message": message,
            "template_url": f"/ai/notebooks/{nb_project_id}/template/{nb_template_id}",
            "additional_description": additional_description,
            "first_name": first_name
        },
        "recipients": [user_email]
    }
    return email_notification_payload


def get_notebook_details(pod_name_list, pod_type="existing", resource_type=""):
    """
    This function takes the pod details list which contains details of a pod like its name,
    usage percentage, resource type apart from these basic details we do require the project
    name, template name details which is later used by the bell notification api. The function
    makes an api call to the console backend api for getting the project details by using the
    project id obtained from get_template_url_details functions
    Args:
    pod_name_list: Pod details in list form
    resource_type: str type of resorce either cpu or memory
    It add project id, project name, template name, template id, user id to the pod name list
    and retuns the updated list containing these details 
    """
    add_empty_values = [""] * 4
    add_empty_values.append(True)
    # The above line creates a blank list with 5 elements to be added when no pod information is found
    for each_pod in pod_name_list:
        project_details = get_template_url_details(each_pod[0])
        if project_details:
            nb_project_id, nb_template_id, nb_user_id = project_details
            try:
                g_headers = {
                    'X-Auth-Userid': nb_user_id,
                    'X-Auth-Username': nb_user_id,
                    'X-Auth-Email': nb_user_id,
                    'x-project-id': nb_project_id
                }
                console_backend_url = app.config["CONSOLE_BACKEND_URL"] + f"/secured/api/project/v1/{nb_project_id}"
                project_resp = requests.get(url=console_backend_url,
                                            headers=g_headers)
                log.info("Console backend api response")
                log.info(project_resp.status_code)
                project_dict = project_resp.json()
                project_name = project_dict.get("projectName", "")
                each_pod.append(nb_project_id)
                each_pod.append(project_name)
                each_pod.append(get_docker_template_name(nb_template_id)[0])
                each_pod.append(nb_template_id)
                each_pod.append(nb_user_id)
                if resource_type == 'cpu' and pod_type == 'new':
                    send_bell_notification(each_pod, resource_type)
                    if each_pod[1] >= app.config["CPU_PERCENT_HIGH_THRESHOLD2"]:
                        each_pod.append(True)
                    else:
                        each_pod.append(False)
                elif resource_type == 'memory' and pod_type == 'new':
                    send_bell_notification(each_pod, resource_type)
                    if each_pod[1] >= app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]:
                        each_pod.append(True)
                    else:
                        each_pod.append(False)
            except Exception as err:
                log.error(str(err))
                del each_pod[3:]
                each_pod.extend(add_empty_values)
        else:
            each_pod.extend(add_empty_values)

    return pod_name_list


def send_bell_notification(each_pod, resource_type=""):
    """
    This method takes each_pod list containing details of an individual pod
    and send the bell notification to user's pod
    The bell icon notification paylaod is obtained by usin the bell_notifiction_payload
    function and this payload is used by the lens notification service
    Arguments:
    each_pod: list containing pod related information like pod_name, usage percentage, template_name,
                project_name
    resource_type: str variable for type of resource either cpu or memory

    The message which gets sent to the user will be read from the config string and users will be 
    notified accordingly.
    """
    nb_project_id, nb_project_name, nb_template_name, \
            nb_template_id, nb_user_id = each_pod[3:8]
    
    if resource_type == 'cpu':
        if app.config["CPU_PERCENT_HIGH_THRESHOLD1"] <= float(each_pod[1]) \
                < app.config["CPU_PERCENT_HIGH_THRESHOLD2"]:
            message = f'{app.config["CPU_MORE_THAN_80_PERCENT"]} {nb_template_name} in {nb_project_name} project'
        elif float(each_pod[1] >= app.config["CPU_PERCENT_HIGH_THRESHOLD2"]):
            message = f'{app.config["CPU_MORE_THAN_100_PERCENT"]} {nb_template_name} in {nb_project_name} project'

    elif resource_type == 'memory':
        reached_threshold2 = False
        if app.config["MEMORY_PERCENT_HIGH_THRESHOLD1"] <= float(each_pod[1]) \
                < app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]:
            message = f'{app.config["MEMORY_PERCENT_HIGH_THRESHOLD1_MESSAGE"]} {nb_template_name} in {nb_project_name} project'
        elif float(each_pod[1] >= app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]):
            message = f'{app.config["MEMORY_PERCENT_HIGH_THRESHOLD2_MESSAGE"]} {nb_template_name} in {nb_project_name} project'
            reached_threshold2 = True

        try:
            # sending email alert
            if reached_threshold2:
                subject = app.config["MEMORY_PERCENT_HIGH_THRESHOLD2_SUBJECT"]
                additional_description = app.config["MEMORY_PERCENT_HIGH_THRESHOLD2_ADDITIONAL_DESCRIPTION"]
                email_notification_payload = email_user_payload(nb_project_id, nb_template_id, message, subject, additional_description, nb_user_id)
                log.info("Email Notification payload %s", email_notification_payload)
                email_url = app.config["EMAIL_URL"]
                g_headers = {
                    'X-Auth-Userid': nb_user_id,
                    'X-Auth-Username': nb_user_id,
                    'X-Auth-Email': nb_user_id,
                    'x-project-id': nb_project_id
                }
                resp = requests.post(url = email_url, json=email_notification_payload, headers=g_headers)
                log.info("socket call %s", resp.status_code)

        except Exception as err:
            log.error("Error in email sending function")
            log.error(err)

    try:
        g_headers, notification_payload = bell_notification_payload(
            nb_user_id, nb_project_id, nb_template_id, message)
        bell_notification_url = app.config["NOTIFICATION_URL"]
        resp = requests.post(url=bell_notification_url, headers=g_headers,
                                json=notification_payload)
        log.info("bell notifcation sent")
    except Exception as err:
        log.error(err)
        log.error("Error while sending bell notification")


def segregate_new_existing_pods(incoming_pod_names, new_pods_from_db, existing_pods_from_db):
    """
    This function takes three sets compares them as per logic for identfying the new 
    and existing pods and returns the new_pods and existing_pods set
    Arguments:
    incoming_pods_names: set of pod names coming in an incoming alert
    new_pods_from_db: set of pod names coming from new_pods column from the db table
    existing_pods_from_db: set of pod names coming from existing_pods column from the db table
    Below logic details:
    case1:
        incoming_pod_names = {'podA', 'podC'} 
        new_pods_from_db = {'podA','podB'}
        existing_pods_from_db = {}
        After applying the below logic for finding the existing_pods which is 
        incoming pods intersection with new pods from db or incoming pods
        intersection with existing pods from database
        new pods will be incoming pods from the alert - new pods - existing pods
        existing_pods = {'podA'}
        new_pods = {'podC'}
    The function returns two variables having set datatype
    """
    existing_pods = incoming_pod_names.intersection(new_pods_from_db) | \
                    incoming_pod_names.intersection(existing_pods_from_db)
    new_pods = incoming_pod_names - new_pods_from_db - existing_pods
    return new_pods, existing_pods


def trigger_cpu_alerts(cpu_pod_names, cpu_pods_with_resource_details):
    """
    This function loops over the pods which have cpu utilization greater than
    cpu threshold1 and 
    Args:
    cpu_pod_names: It has the list of pod names
    cpu_pods_with_resource_details: It has the list of pod details consisting
        pod names, usage percentage and resource type
    The function returns the list of pod names to which an alert was sent
    """
    resource_type = 'cpu'
    # Filter pods having usage above cpu_threshold1 eg 80%
    new_pod_name_list = [x for x in cpu_pods_with_resource_details if x[1] > app.config["CPU_PERCENT_HIGH_THRESHOLD1"]]
    # Get pods from database table
    pod_names_from_db_obj = get_pod_resource_details(resource_type=resource_type)
    new_pod_names_from_db = [x[0] for x in pod_names_from_db_obj if x[0] is not None]
    existing_pod_names_from_db = [x[1] for x in pod_names_from_db_obj if x[1] is not None]
    existing_pods_from_db = set(existing_pod_names_from_db)
    new_pods_from_db = set(new_pod_names_from_db)

    # The below two variables are of dictionary type and it is used to get information about the
    # alerts status of pods saved in database. The alert status is a boolean flag and
    # by default it is set to false, when the cpu usage goes above threshold2
    # eg more than 100% then the alert status flag is set to true after sending
    # the bell icon notification to the pod. Once the alert status is set to true
    # so new bell notification will be sent to that pod.
    alert_status_from_db = {x[1]: x[2] for x in pod_names_from_db_obj if x[1] is not None}
    existing_pods_status_from_db = {x[0]: x[2] for x in pod_names_from_db_obj if x[0] is not None}
    alert_status_from_db.update(existing_pods_status_from_db) # Keeping all values in single dictionary
    cpu_pod_names = set(cpu_pod_names)
    if len(new_pod_names_from_db) == 0 and len(existing_pod_names_from_db) == 0:
        new_pods_to_db = get_notebook_details(new_pod_name_list, "new", resource_type)
        save_pod_resource_details(new_pods_to_db, [], resource_type)

    else:
        new_pods, existing_pods = segregate_new_existing_pods(cpu_pod_names, new_pods_from_db, existing_pods_from_db )

        existing_pods_to_db = compare_pods_list(existing_pods, new_pod_name_list)
        new_pods_to_db = compare_pods_list(new_pods, new_pod_name_list)
        existing_pods_to_db = get_notebook_details(existing_pods_to_db, "existing", resource_type)
        new_pods_to_db = get_notebook_details(new_pods_to_db, "new", resource_type)

        if len(new_pods_to_db) == 0 and len(existing_pods_to_db) == 0:
            log.info("Deleting the database table contents")
            clear_pod_resource_details(resource_type)
        else:
            for each_pod in existing_pods_to_db:
                if each_pod[1] >= app.config["CPU_PERCENT_HIGH_THRESHOLD2"]:
                    if not alert_status_from_db.get(each_pod[0]):
                        send_bell_notification(each_pod, resource_type)
                    each_pod.append(True)
                else:
                    each_pod.append(False)
            save_pod_resource_details(new_pods_to_db, existing_pods_to_db, resource_type)
        
    return new_pods_to_db


def trigger_memory_alerts(memory_pod_names, memory_pods_with_resource_details):
    """
    This function loops over the pods which have memory utilization greater than
    memory threshold1 and calls the send bell notification function for sending the 
    alert and sends an email alert to users pod having memory utilization greater
    than 95 percent
    Args:
    memory_pod_names: It has the list of pod names
    memory_pods_with_resource_details: It has the list of pod details consisting
        pod names, usage percentage and resource type
    The function returns the list of pod names to which an alert was sent
    """
    resource_type = 'memory'
    # Filter pods having usage above cpu_threshold1
    new_pod_name_list = [x for x in memory_pods_with_resource_details if x[1] > app.config["MEMORY_PERCENT_HIGH_THRESHOLD1"]]
    # Get pods from database table
    pod_names_from_db_obj = get_pod_resource_details(resource_type=resource_type)
    new_pod_names_from_db = [x[0] for x in pod_names_from_db_obj if x[0] is not None]
    existing_pod_names_from_db = [x[1] for x in pod_names_from_db_obj if x[1] is not None]
    existing_pods_from_db = set(existing_pod_names_from_db)
    new_pods_from_db = set(new_pod_names_from_db)

    # The below two variables are of dictionary type and it is used to get information about the
    # alerts status of pods saved in database. The alert status is a boolean flag and
    # by default it is set to false, when the cpu usage goes above threshold2
    # eg more than 100% then the alert status flag is set to true after sending
    # the bell icon notification to the pod. Once the alert status is set to true
    # so new bell notification will be sent to that pod.
    alert_status_from_db = {x[1]: x[2] for x in pod_names_from_db_obj if x[1] is not None}
    existing_pods_status_from_db = {x[0]: x[2] for x in pod_names_from_db_obj if x[0] is not None}
    alert_status_from_db.update(existing_pods_status_from_db)
    memory_pod_names = set(memory_pod_names)
    if len(new_pod_names_from_db) == 0 and len(existing_pod_names_from_db) == 0:
        new_pods_to_db = get_notebook_details(new_pod_name_list, "new", resource_type)
        save_pod_resource_details(new_pods_to_db, [], resource_type)

    else:
        new_pods, existing_pods = segregate_new_existing_pods(memory_pod_names, new_pods_from_db, existing_pods_from_db)

        existing_pods_to_db = compare_pods_list(existing_pods, new_pod_name_list)
        new_pods_to_db = compare_pods_list(new_pods, new_pod_name_list)
        existing_pods_to_db = get_notebook_details(existing_pods_to_db, "existing", resource_type)
        new_pods_to_db = get_notebook_details(new_pods_to_db, "new", resource_type)

        if len(new_pods_to_db) == 0 and len(existing_pods_to_db) == 0:
            log.info("Deleting the database table contents")
            clear_pod_resource_details(resource_type)
        else:
            for each_pod in existing_pods_to_db:
                if each_pod[1] >= app.config["MEMORY_PERCENT_HIGH_THRESHOLD2"]:
                    if not alert_status_from_db.get(each_pod[0]):
                        send_bell_notification(each_pod, resource_type)
                    each_pod.append(True)
                else:
                    each_pod.append(False)
            save_pod_resource_details(new_pods_to_db, existing_pods_to_db, resource_type)

    return new_pods_to_db


def get_running_pods():
    """
    This function returns the list of pod names which are in running state
    """
    pod_name_list = db.session.query(TemplateStatus.pod_name) \
        .filter(TemplateStatus.status == 'RUNNING').all()
    return pod_name_list


def delete_active_repo_on_access_revoke(project_id, username):
    """
    Delete active repo details once access revoke from owner
    Args: project id : String
    Args : username : String
    Returns:
        message:
        Status code
    """
    # Remove the active branch based on both username and project_id
    active_branch = GitRepoActive.query.filter_by(project_id=project_id, username=username).first()
    if active_branch:
        db.session.delete(active_branch)
        db.session.commit()
        return {'message': 'Active branch removed successfully'}, 200
    else:
        return {'message': 'Active branch not found'}, 404

