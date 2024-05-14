#! -*- Coding: utf-8 -*-
# -*- coding: utf-8 -*-

"""manager module for kubespawner"""
# pylint: disable=too-many-lines
# pylint: disable=no-member
import ast
import functools
import hashlib
import json
import os
import re
import shutil
import urllib.parse
from datetime import datetime as date_time
import datetime # pylint: disable=unused-import
from threading import Thread
from typing import List
from uuid import uuid4
import random
import sys
import time
import requests
import yaml
from urllib.parse import quote_plus
from dateutil.tz import tzlocal # pylint: disable=unused-import
from statistics import mean
from flask import request, g, current_app
from mosaic_utils.ai.git_repo.utils import create_remote_url
from mosaic_utils.ai.k8.pod_metrics_summary import \
    fetch_resource_limitscaling_guarantee, \
    fetch_resource_request_limit, \
    volume_mount_count, \
    volume_count, \
    attach_snapshot_volume_mount, \
    volume_custom, volume_custom_mount
from mosaic_utils.ai.headers.constants import Headers
from notebooks_api.utils.quantity import parse_quantity
from mosaic_utils.ai.git_repo.utils import extract_proxy_values
from ..notebook.manager import register_snapshot

from retry import retry
from kubernetes import client, config, watch
import base64
from .constants import KernelType, Metering, Notebooks, Automl, Cron

if shutil.which("minikube"):
    config.load_kube_config()
elif os.getenv("KUBERNETES_SERVICE_HOST"):
    config.load_incluster_config()
else:
    pass
# pylint: disable=invalid-name
extension = client.BatchV1Api()


# conf = app_config()


def log_decorator(_func=None):
    """Logging Decorator"""
    def log_decorator_info(func):
        @functools.wraps(func)
        def log_decorator_wrapper(*args, **kwargs):

            """log function begining"""
            current_app.logger.info("Begin function: {0}".format(func.__name__))
            try:
                value = func(*args, **kwargs)
                current_app.logger.info("End function: {0}".format(func.__name__))
            except:
                current_app.logger.exception(f"Exception: {str(sys.exc_info()[1])}")
                current_app.logger.info("End function: {0} with exception".format(func.__name__))
                raise
            return value
        return log_decorator_wrapper
    if _func is None:
        return log_decorator_info
    return log_decorator_info(_func)


def fetch_spark_url(kernel):
    """Method to fetch spark url"""
    if kernel in [KernelType.spark, KernelType.spark_distributed]:
        new_url = current_app.config["AI_SERVER_URL"]
    else:
        new_url = current_app.config["MOSAIC_AI_SERVER"]
    return new_url


@log_decorator
def get_pod_name(job_name, max_retries=5) -> str:
    """
    Method returns pod name from job name
    :param max_retries:
    :param job_name:
    :return:
    """

    v1 = client.CoreV1Api()
    for i in range(max_retries):
        pod_list = v1.list_namespaced_pod(current_app.config["KUBERNETES_NAMESPACE"],
                                          label_selector='job-name={}'.format(job_name))
        if pod_list.items:
            pod_name = pod_list.items[0].metadata.name
            current_app.logger.info("Pod Name %s for Job - %s", pod_name, job_name)
            return pod_name

        current_app.logger.debug("retry %s ... list_namespaced for job - %s", str(i), job_name)
        time.sleep(1)

    current_app.logger.exception("Pod Not created for job - %s", job_name)
    return "Job does not exist"


@log_decorator
def list_namespaced_pod(job_name):
    """Method to list namespaced pod
    Can deprecate this method with get_pod_name()
    """
    v1 = client.CoreV1Api()
    current_app.logger.debug("inside list namespaced pod")
    # pod is taking time to launch
    time.sleep(5)
    pod_name = v1.list_namespaced_pod(current_app.config["KUBERNETES_NAMESPACE"],
                                      label_selector='job-name={}'.format(job_name))
    current_app.logger.debug("done - listing namespaced pod")
    for i in pod_name.items:
        # pylint: disable=logging-not-lazy
        if (i.metadata.labels is not None) and i.metadata.labels.get("job-name", None) == job_name:
            job_container_id = i.metadata.name
            current_app.logger.debug("Job Container Id : " + job_container_id)
            return job_container_id
    return "Job does not exist"


@log_decorator
def create_job(pod, job_name):
    """Method that creates job in kubernetes"""
    # Monitor deployment
    try:
        current_app.logger.info(f"Creating Job: {job_name}")
        # Executing the job in specified namespace
        retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
        job_id = list_namespaced_pod(job_name)
        current_app.logger.debug("fetching job id")
        current_app.logger.debug(job_id)
        while True:
            response_job_status = extension.read_namespaced_job_status(
                name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
            )
            s = response_job_status.status
            if s.succeeded == 1 or s.failed == 1:
                extension.delete_namespaced_job(
                    name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
                )
                v1 = client.CoreV1Api()
                v1.delete_namespaced_pod(
                    name=job_id, namespace=current_app.config["KUBERNETES_NAMESPACE"]
                )
                if s.succeeded == 1:
                    return "Success", job_id
                if s.failed == 1:
                    return "Fail", job_id
            else:
                time.sleep(5)
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        job_id = list_namespaced_pod(job_name)
        extension.delete_namespaced_job(
            name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )
        v1 = client.CoreV1Api()
        v1.delete_namespaced_pod(
            name=job_id, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )
        return "Fail", "Fail"


@log_decorator
def clean_env_variables(env_dict):
    """
    Returns dictionary of env_variables after removing invalid keys in it.
    :param env_dict: env variables dictionary.
    :return: env_vars dict
    """
    env_vars = {}
    for key, val in env_dict.items():
        if len(key) and not key.isspace():
            env_vars[key] = val
    return env_vars


@log_decorator
def create_environment_variables(env):
    """Method to create environment variables"""
    # Fetch spark details from configmap
    env["SPARK_USERNAME"] = current_app.config["SPARK_USERNAME"]
    env["SPARK_PASSWORD"] = current_app.config["SPARK_PASSWORD"]
    env["CLUSTER_NAME"] = current_app.config["CLUSTER_NAME"]
    env["BLOB_NAME"] = current_app.config["BLOB_NAME"]
    env["FOLDER_NAME"] = current_app.config["FOLDER_NAME"]
    env["BLOB_CONTAINER_NAME"] = current_app.config["BLOB_CONTAINER_NAME"]
    env["BLOB_ACCOUNT_NAME"] = current_app.config["BLOB_ACCOUNT_NAME"]
    env["BLOB_ACCOUNT_KEY"] = current_app.config["BLOB_ACCOUNT_KEY"]
    env["PYSPARK_PYTHON"] = current_app.config["PYSPARK_PYTHON"]
    env["PYSPARK3_PYTHON"] = current_app.config["PYSPARK3_PYTHON"]

    env_variables = []
    jwt = ""
    if env:
        for key, val in clean_env_variables(env).items():
            if isinstance(val, list):
                val = str(val)
            env_variable = {"name": key, "value": val}
            if key == "TOKEN":
                jwt = val
                current_app.logger.debug("value of jwt %s", jwt)
            env_variables.append(env_variable)
    pod_name = client.V1EnvVar(
        name="MY_POD_NAME",
        value_from=client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(field_path="metadata.name")
        ),
    )

    enc_env = json.dumps(env_variables)
    env_variables.append({"name": "encodedEnv", "value": enc_env})
    env_variables.append(pod_name)
    current_app.logger.debug("env_variables %s", env_variables)
    return env_variables, jwt


@log_decorator
def create_env_var(env):
    """Method to create environment variables"""
    env_variables = []
    if env:
        for key, val in clean_env_variables(env).items():
            if isinstance(val, list):
                val = str(val)
            env_variable = {"name": key, "value": val}
            env_variables.append(env_variable)
    pod_name = client.V1EnvVar(
        name="MY_POD_NAME",
        value_from=client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(field_path="metadata.name")
        ),
    )
    env_variables.append(pod_name)
    current_app.logger.debug("env_variables %s", env_variables)
    return env_variables


@log_decorator
def node_selector_term_values(key, operator, values):
    """Node selector term method"""
    return client.V1NodeSelectorTerm(
        match_expressions=[
            client.V1NodeSelectorRequirement(key=key, operator=operator, values=values)
        ]
    )

@log_decorator
def add_node_affinity_required(key, operator, values):
    """Add node affinity method"""
    return client.V1NodeSelector(
        node_selector_terms=[node_selector_term_values(key, operator, values)]
    )

@log_decorator
def add_tolerations(key, value, operator, effect):
    """Add tolerations method"""
    return client.V1Toleration(key=key, value=value, operator=operator, effect=effect)


# pylint: disable=too-many-arguments
@log_decorator
def template_manifest(
        job_name: str,
        init_containers: list,
        containers: list,
        share_process_namespace: bool,
        volumes: list,
        node_affinity_options: dict,
        user_impersonation: bool,
        user_imp_data: dict,
        kernal_type: str,
        envs: dict) -> object:
    """
    Template manifest method

    :param job_name:                String parameter containing name for job to create
    :param init_containers:         Collection of init containers
    :param containers:              Collection of containers
    :param volumes:                 Collection of volumes
    :param node_affinity_options:   Diction with all node affinity option specific to job
    :return:                        client.V1PodTemplateSpec
    """

    # get pod security context to set in pod spec
    if kernal_type == KernelType.sas:
        security_context = {}
    else:
        security_context = get_security_context(user_imp_data, user_impersonation, envs)


    spec = client.V1PodSpec(
        init_containers=init_containers,
        containers=containers,
        share_process_namespace=share_process_namespace,
        volumes=volumes,
        image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
        restart_policy="Never",
        service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
        affinity=client.V1Affinity(
            node_affinity=client.V1NodeAffinity(
                required_during_scheduling_ignored_during_execution=add_node_affinity_required(
                    node_affinity_options.get("NODE_AFFINITY_REQUIRED_KEY"),
                    node_affinity_options.get("NODE_AFFINITY_REQUIRED_OPERATOR"),
                    node_affinity_options.get("NODE_AFFINITY_REQUIRED_VALUES"),
                )
            )
        ),
        tolerations=[
            add_tolerations(
                key=node_affinity_options.get("TOLERATIONS_KEY"),
                value=node_affinity_options.get("TOLERATIONS_VALUE"),
                operator=node_affinity_options.get("TOLERATIONS_OPERATOR"),
                effect=node_affinity_options.get("TOLERATIONS_EFFECT"),
            )
        ],
        security_context=security_context,
        host_aliases=get_hostalias()
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": job_name, "owner": "ailogistics", \
                                             "catalog": "false", "decisions": "false",
                                             "ailogistics": "false",
                                             "lens": "false",
                                             "aiops": "false", "agnitio": "false"}), spec=spec
    )
    return template


def get_security_context(user_imp_data, user_impersonation, envs):
    """
    Prepare security context

    :param user_imp_data: contains UID and GID configured for user impersonation, None if user impersonation is disabled
    :param user_impersonation: flag to determine if user impersonation is enabled/disabled
    :return: security context object
    """

    if user_impersonation:
        pod_supplemental_groups = user_imp_data['supplemental_groups']
        pod_uid = pod_gid = int(envs.get("user_id"))
    else:
        pod_uid = pod_gid = os.getuid()
        pod_supplemental_groups = None
    security_context = client.V1PodSecurityContext(run_as_user=pod_uid,
                                                   run_as_group=pod_gid,
                                                   supplemental_groups=pod_supplemental_groups
                                                   )
    return security_context


@log_decorator
def fetch_resource_limit_guarantee(cpu, memory, resource_extra):
    """Fetch resource method"""
    if resource_extra == "nvidia":
        return {"nvidia.com/gpu": cpu}
    if resource_extra == "amd":
        return {"amd.com/gpu": cpu}
    return {"cpu": cpu, "memory": memory}


@log_decorator
def get_affinity_config(project_id, gpu=False):
    """
    This function is used to return node affinity data from json file
    :param project_id:
    :param gpu: A flag indicating whether GPU affinity is requested (default is False)
    :return: node affinity dict
    """
    # pylint: disable=too-many-function-args
    current_app.logger.info(f"Affinity for project_id: {project_id}")
    node_affinity = {}
    try:
        groupenv = "GPU_NODE" if gpu else None
        console_backend_url = current_app.config.get("CONSOLE_BACKEND_URL")
        project_details_url = f"{console_backend_url}/secured/api/project/v1/{project_id}"
        response = requests.get(project_details_url, headers={
                    Headers.x_auth_userid: g.user["mosaicId"],
                    Headers.x_auth_email: g.user["email_address"],
                    Headers.x_auth_username: g.user["first_name"],
                    Headers.x_project_id: g.user["project_id"]
                })
        if response.status_code == 200:
            response_json = response.json()
            if "groupenv" in response_json and response_json["groupenv"]:
                groupenv = response_json["groupenv"]

        affinity_file_name = "affinity_gpu.json" if gpu else "affinity.json"
        affinity_file = open(f"{current_app.config['NODE_AFFINITY_FOLDER']}/{affinity_file_name}")
        affinity_json = json.load(affinity_file)
        affinity_file.close()
        if groupenv is not None and affinity_json.get(groupenv):
            _node_affinity = ast.literal_eval(affinity_json[groupenv])
            _node_affinity["NODE_AFFINITY_REQUIRED_VALUES"] = _node_affinity[
                "NODE_AFFINITY_REQUIRED_VALUES"].split(",")
            current_app.logger.info("Affinity data from config")
            return _node_affinity
        current_app.logger.info("Default Affinity confing")
        return node_affinity
    except Exception as ex:
        current_app.logger.error(f"Unable to load affinity from config due to {ex}, using Default config")
        raise Exception


# pylint: disable-msg=too-many-locals, unused-argument, too-many-branches, too-many-statements
@log_decorator
def new_create_job_manifest(
        jwt,
        job_name,
        env_variables,
        git_url,
        git_repo,
        template_id,
        image_name,
        cpu,
        memory,
        resource_extra,
        execution_command,
        package_installation_command,
        pip_packages,
        kernel_type,
        file_path,
        node_affinity_options,
        enabled_repo,
        snapshots,
        git_macros_config,
        metering_info,
        resource_quota_full=False,
        automl_info=None,
        envs=None,
        user_imp_data=None,
        instance_id=None,
        log_id=None
):
    """create new job method"""
    remote_url = create_remote_url(enabled_repo)

    if enabled_repo['base_folder'] not in [None, ""]:
        base = enabled_repo['base_folder'].replace(" ", "\\ ")
        base_folder = f"/{base}/"
        base_copy_folder = f"/{base}/*"
    else:
        base_folder = "/"
        base_copy_folder = "/*"
    remote_branch = enabled_repo['branch']

    # Creating a JOB to execute the notebook
    # Volume
    volume = client.V1Volume(
        name="test-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_git = client.V1Volume(
        name="git", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_shared_code = client.V1Volume(
        name="code", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_tmp = client.V1Volume(
        name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_logs = "log-storage"
    user_impersonation_flag = envs.get("USER_IMPERSONATION")
    user_impersonation = bool(user_impersonation_flag and
                              user_impersonation_flag.lower() == "true")

    set_token_command = f"echo {jwt} > /home/mosaic-ai/.mosaic.ai || true;"
    if user_impersonation and kernel_type in [KernelType.python,
                                              KernelType.rstudio_kernel, KernelType.r_kernel, KernelType.vscode_python]:
        user_name = envs.get('user_name')
        set_token_command = f"echo {jwt} > /home/{user_name}/.mosaic.ai || true;"

    # lifecycle
    lifecycle_hooks = job_lifecyclehooks(jwt, metering_info, set_token_command, automl_info)

    cmd = ""
    terminate_now = ('if [ -z ${Terminate+x} ]; then echo "Program Success";'
                     +
                     ' else echo "Program Failed"; exit 1; fi; \n'
                     )

    # pylint: disable-msg=too-many-format-args
    command_var = update_command_var(cmd,
                                     jwt,
                                     execution_command,
                                     metering_info,
                                     automl_info,
                                     terminate_now,
                                     user_impersonation,
                                     kernel_type
                                     )

    job_volume_mount = [client.V1VolumeMount(name=volume.name, mount_path="/notebooks"),
                        client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
                        client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
                        client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code"),
                        client.V1VolumeMount(name=volume_logs, mount_path=current_app.config["LOG_DIRECTORY"])]
    volume_list = [volume, volume_git, volume_tmp, volume_shared_code]

    volume_count_output, volume_mount_output = volumeVolumeMounts(g.user["mosaicId"], g.user["project_id"])

    job_volume_mount.extend(get_volumes_mount(
        project_id=g.user["project_id"], username=g.user["mosaicId"], snapshots=snapshots,
        git_macros_config=git_macros_config, resource_quota_full=resource_quota_full,
        volume_mount_output=volume_mount_output, log_id=envs.get('log_id'), envs=envs))

    if kernel_type == KernelType.sas:
        volume_cas = client.V1Volume(
            name="cas-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )

        volume_data = client.V1Volume(
            name="data-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )

        volume_mount = [
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/data"),
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/permstore"),
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/cache"),
            client.V1VolumeMount(name=volume_data.name, mount_path="/data1"),
        ]
        job_volume_mount.extend(volume_mount)
        volume_list = [volume, volume_git, volume_cas, volume_data, volume_tmp, volume_shared_code]
    # Container
    container = client.V1Container(
        name=job_name,
        image=image_name,
        image_pull_policy="IfNotPresent",
        ports=[client.V1ContainerPort(container_port=80)],
        volume_mounts=job_volume_mount,
        env=env_variables,
        lifecycle=lifecycle_hooks,
        resources=client.V1ResourceRequirements(
            limits=fetch_resource_limitscaling_guarantee(
                cpu, memory, resource_extra, current_app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"], current_app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"]
            ),
            requests=fetch_resource_request_limit(cpu,
                                                  memory,
                                                  current_app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"],
                                                  current_app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"],
                                                  resource_extra)
        ),
        command= command_var,
    )
    volume_mounts = [client.V1VolumeMount(name=volume.name, mount_path="/notebooks"),
                     client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
                     client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
                     client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code"),
                     client.V1VolumeMount(
                         name=g.user["project_id"], mount_path="/data",
                         sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                  f'/{g.user["project_id"]}/{g.user["project_id"]}-Data'
                     ),
                     client.V1VolumeMount(
                         name=g.user["project_id"], mount_path="/output",
                         sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                  f'/{g.user["project_id"]}/'
                                  f'{g.user["project_id"]}-Snapshot'
                                  f'/{snapshots["output"]}'
                     )]
    if snapshots["input"] != KernelType.default:
        # pylint: disable-msg=line-too-long
        volume_mounts.append(client.V1VolumeMount(name=g.user["project_id"], mount_path="/input",
                                                  sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                                           f'/{g.user["project_id"]}'
                                                           f'/{g.user["project_id"]}-Snapshot'
                                                           f'/{snapshots["input"]}'))

    git_macro_command = create_git_macro_command(git_macros_config)
    if git_macros_config:
        # add volume mount for init-container
        output_dirs = get_distinct_values_by_key(git_macros_config, "output")
        for idx, dir_name in enumerate(output_dirs):
            volume_mounts.append(client.V1VolumeMount(name=f"vol-{idx}", mount_path=f"/{dir_name}"))
    # Init Container
    init_container = client.V1Container(
        name="init-container",
        image=current_app.config["GIT_INIT_IMAGE"],
        image_pull_policy="IfNotPresent",
        command=[
            "/bin/sh",
            "-c",
            "python script.py; \n"
            "cp -r /shared_code/* /code/; \n"
            "cd /git; \n"
            "mkdir -p /notebooks/notebooks/ && cp -r /git{4} /notebooks/notebooks/; \n"
            f"mkdir -p /output/{instance_id}; \n"
            f"touch /output/{instance_id}/central.log; \n"
            f"touch /output/{instance_id}/healthy; \n"
            "cd /notebooks/notebooks/; \n"
            "echo '{3}' > /notebooks/notebooks/requirements.sh; \n"
            f"echo \"====== * $(date '+%d/%m/%Y %H:%M:%S') * ====== \" >> /output/{instance_id}/central.log; \n"
            "chmod 777 -R /notebooks/notebooks; \n"
            f'{git_macro_command}; \n'.format(
                remote_url, remote_branch, base_folder, package_installation_command,
                base_copy_folder, kernel_type
            ),
        ],
        env=[client.V1EnvVar(name="user_name", value=g.user["mosaicId"]),
        client.V1EnvVar(name="PROJECT_ID", value=g.user["project_id"]),
        client.V1EnvVar(name="repo_id", value=enabled_repo["repo_id"]),
        client.V1EnvVar(name="first_name", value=g.user["first_name"]),
        client.V1EnvVar(name="email_address", value=g.user["email_address"]),
        client.V1EnvVar(name="template_id", value=template_id),
        client.V1EnvVar(name="mode", value="RUN"),
        client.V1EnvVar(name="kernel_type", value=kernel_type),
        client.V1EnvVar(name="instance_id", value=str(instance_id)),
        client.V1EnvVar(name="branch_name", value=enabled_repo.get("branch", None))],

        volume_mounts=volume_mounts,
        resources=client.V1ResourceRequirements(
            limits=json.loads(current_app.config["GIT_INIT_CONTAINER_LIMIT"]),
            requests=json.loads(current_app.config["GIT_INIT_CONTAINER_REQUEST"]),
        )
    )

    job_volume = get_volumes(
        project_id=g.user["project_id"],
        username=g.user["mosaicId"],
        snapshots=snapshots,
        git_macros_config=git_macros_config, volume_count_output=volume_count_output)

    job_volume.extend(volume_list)

    # Template
    template = template_manifest(
        job_name=job_name,
        init_containers=[init_container],
        containers=[container],
        share_process_namespace=True,
        volumes=job_volume,
        node_affinity_options=node_affinity_options,
        user_impersonation=user_impersonation,
        user_imp_data=user_imp_data,
        kernal_type=kernel_type,
        envs=envs
    )

    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=template
    )

    # Pod
    pod = client.V1Job(
        kind="Job", metadata=client.V1ObjectMeta(name=job_name), spec=spec_pod
    )
    return pod


@log_decorator
def create_git_macro_command(git_macros_configs):
    """ Returns the sh command for cloning macro repo"""
    command = "echo 'No git macros present..'"
    if git_macros_configs:
        command = ""
        for macro in git_macros_configs:
            try:
                remote_url = create_remote_url(macro)
                branch = macro["branch"]
                output = f"/{macro['output']}"
                proxy_details = macro.get('proxy_details', None)
                if proxy_details:
                    proxy_ip, verify_ssl, proxy_username, proxy_password, proxy_protocol = extract_proxy_values(proxy_details)
                    # If proxy server has user name and password add it to proxy ip field
                    if proxy_username and proxy_password:
                        proxy_ip = f"{proxy_username}:{proxy_password}@{proxy_ip}"
                    command += f'git -C {output} clone --config  "http.proxy={proxy_ip}" -c http.sslVerify={verify_ssl} --single-branch -b ' \
                          f"{branch} {remote_url} >> /tmp/macro-installation.log 2>&1 || true;"
                else:
                    command += f"git -C {output} clone --single-branch -b " \
                          f"{branch} {remote_url} >> /tmp/macro-installation.log 2>&1 || true;"
            # pylint: disable=broad-except
            except Exception as ex:
                current_app.logger.error("Git macro config insufficient keys %s", ex)
                current_app.logger.error("Git macro will not be cloned..")

    return command.rstrip(";")

@log_decorator
def get_image_name(language):
    """Method to get image name"""
    if language == "python":
        return current_app.config["PYTHON_IMAGE_NAME"]
    if language == "java":
        return current_app.config["JAVA_IMAGE_NAME"]
    if language == "shell":
        return current_app.config["SHELL_IMAGE_NAME"]
    if language == "snowpark":
        return current_app.config["SNOWPARK_IMAGE_NAME"]
    return None

@log_decorator
def get_image_name_by_cloud_data_warehouse(cloud_data_warehouse):
    """Method to get image name by cloud data warehouse type"""
    if cloud_data_warehouse == "dbt_snowflake":
        return current_app.config["DBT_SNOWFLAKE_IMAGE_NAME"]
    if cloud_data_warehouse == "dbt_databricks":
        return current_app.config["DBT_DATABRICKS_IMAGE_NAME"]
    return None

@log_decorator
def is_pod_started(job_name):
    """Method to check whether pod is started"""
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    current_app.logger.info("inside is pod started")
    current_app.logger.info("job name : " + job_name)
    start = time.time()
    while time.time() - start < 20:
        pod_name = v1.list_namespaced_pod(current_app.config["KUBERNETES_NAMESPACE"],
                                          label_selector='job-name={}'.format(job_name))
        for i in pod_name.items:
            job_container_id = i.metadata.name
            current_app.logger.info("Job Container Id : " + job_container_id)
            return job_container_id
        time.sleep(1)
        current_app.logger.info("Pod is not started yet! Checking Again...")
    return None


@log_decorator
def get_env_variables(data):
    """Method to get environment variables"""
    env_variables = []
    if data.get("env"):
        for key, val in clean_env_variables(data.get("env")).items():
            env_variable = {"name": key, "value": val}
            if key == "TOKEN":
                jwt = val
                current_app.logger.debug("value of jwt %s", jwt)
            env_variables.append(env_variable)
        current_app.logger.debug("env_variables %s", env_variables)
    return env_variables

@log_decorator
def get_runconfig_details(data):
    """Method to get run configuration details"""
    runconfig_details = {}
    if data.get("runConfiguration")!=None:
        for key, val in data.get("runConfiguration").items():
            runconfig_details[key]=val
        current_app.logger.info("runconfig_details %s", runconfig_details)
    return runconfig_details

def get_sensitive_info(data):
    """Method to get sensitive details"""
    sensitiveinfo = {}
    if data.get("sensitiveInfo"):
        for key, val in data.get("sensitiveInfo").items():
            sensitiveinfo[key]=val
    return sensitiveinfo

def encode_sensitive_info(sensitiveinfo):
    """Method to encode sensitive information to base64"""
    encoded_info={}
    for key, value in sensitiveinfo.items():
        if(type(value)==int):
            encoded_info[key]=base64.b64encode(str(value).encode('utf-8')).decode('utf-8')
        else:
            encoded_info[key]=base64.b64encode(value.encode('utf-8')).decode('utf-8')
    return encoded_info

def create_secret_env_var(secret_data,job_name):
    """Method to create secret enviroment variables"""

    secret_env_vars = []
    for key,_ in secret_data.items():
        env_var = client.V1EnvVar(
        name=key,
        value_from=client.V1EnvVarSource(
        secret_key_ref=client.V1SecretKeySelector(
                name=job_name,
                key=key
            )
        )
    )
        secret_env_vars.append(env_var)

    return secret_env_vars


def add_limits_from_run_configuration(runconfig_details):
    """Update cpu and memory limits from runConfiguration details"""
    limits = {}
    limits['cpu'] = runconfig_details.get("cpu","200m")
    limits['memory'] = runconfig_details.get("memory","200Mi")
    current_app.logger.info("limits %s", limits)
    return limits



@log_decorator
def get_init_container(image_name, data, git_repo, volume):
    """Get init container object"""
    init_container = client.V1Container(
        name="init-container",
        image=image_name,
        image_pull_policy="Always",
        command=[
            "/bin/sh",
            "-c",
            "git clone {}://{}:{}@{}/{}/{}.git /pre-post-hook;"
            "cd /pre-post-hook;".format(
                data.get("repo_protocol"),
                data.get("git_username"),
                data.get("git_access_token"),
                data.get("git_server"),
                data.get("git_namespace"),
                git_repo,
            ),
        ],
        volume_mounts=[
            client.V1VolumeMount(name=volume.name, mount_path="/pre-post-hook")
        ],
    )
    return init_container

@log_decorator
def add_limits_from_env_variables(env_variables):
    """Update cpu and memory limits from environment variables"""
    limits = {}
    input_param_val = {}
    input_param_val = get_env_value(env_variables,'input_params')
    input_params = input_param_val if input_param_val else {}
    mapParams = json.loads(str(input_params))
    limits['cpu'] = mapParams.get("cpu","2")
    limits['memory'] = mapParams.get("memory","4Gi")
    return limits

# pylint: disable-msg=too-many-locals
@log_decorator
def execute_custom_hook(data):
    """ Create a job for executing the scheduled notebook

    Args:

    JSON payload:
        {
          "file_content": ""
        }

    """

    image_name = get_image_name(data.get("language"))
    if image_name is None:
        return "Fail", "Wrong language passed!"

    config.load_incluster_config()
    # Preparing the data

    git_repo = data.get("repo_name")
    notebook_name = data.get("repo_name").replace("_", "-")
    notebook_id = data.get("job_instanceid")
    job_name = "{}-{}-job".format(notebook_id, notebook_name)

    env_variables = get_env_variables(data)

    # Creating a JOB to execute the notebook
    # Volume
    volume = client.V1Volume(
        name="test-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    limits = add_limits_from_env_variables(env_variables)
    # Container
    container = client.V1Container(
        name=job_name,
        image=image_name,
        image_pull_policy="Always",
        ports=[client.V1ContainerPort(container_port=80)],
        volume_mounts=[
            client.V1VolumeMount(name=volume.name, mount_path="/pre-post-hook")
        ],
        resources=client.V1ResourceRequirements(limits),
        env=env_variables,
    )
    # Init Container
    init_container = get_init_container(image_name, data, git_repo, volume)
    # Template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": job_name}),
        spec=client.V1PodSpec(
            init_containers=[init_container],
            containers=[container],
            volumes=[volume],
            image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
            restart_policy="Never",
        ),
    )

    project_id = g.user.get('project_id', data.get('project_id', data.get("repo_name")))
    if project_id:
        node_affinity_options = get_affinity_config(project_id)
        if node_affinity_options:
            template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": job_name}),
                spec=client.V1PodSpec(
                    init_containers=[init_container],
                    containers=[container],
                    volumes=[volume],
                    image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
                    restart_policy="Never",
                    affinity=client.V1Affinity(
                        node_affinity=client.V1NodeAffinity(
                            required_during_scheduling_ignored_during_execution=add_node_affinity_required(
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_KEY"),
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_OPERATOR"),
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_VALUES"),
                            )
                        )
                    ),
                    tolerations=[
                        add_tolerations(
                            key=node_affinity_options.get("TOLERATIONS_KEY"),
                            value=node_affinity_options.get("TOLERATIONS_VALUE"),
                            operator=node_affinity_options.get("TOLERATIONS_OPERATOR"),
                            effect=node_affinity_options.get("TOLERATIONS_EFFECT"),
                        )
                    ]
                ),
            )

    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=template
    )

    # Pod
    pod = client.V1Job(
        kind="Job", metadata=client.V1ObjectMeta(name=job_name), spec=spec_pod
    )

    # Monitor deployment
    try:
        # Executing the job in specified namespace
        retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
        job_id = is_pod_started(job_name)
        if job_id is None:
            current_app.logger.error(
                "Pod is unable to start for jobInstanceId "
                + str(data.get("job_instanceid"))
            )
            return "Fail", ""
        current_app.logger.debug(
            "Pod is successfully started for jobInstanceId "
            + str(data.get("job_instanceid"))
            + " and application_id "
            + str(job_id)
        )
        return "Success", job_id
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        job_id = is_pod_started(job_name)
        current_app.logger.error(
            "Pod is unable to start for jobInstanceId "
            + str(data.get("job_instanceid"))
            + " and application_id "
            + str(job_id)
        )
        return "Fail", ""

@log_decorator
def execute_custom_hook_with_docker(data):
    """ Create a container for executing the hooks

    Args:

    JSON payload:
        {
          "file_content": ""
        }

    """
    try:
        # Executing the job in specified namespace
        image_name = get_image_name(data.get("language"))
        if image_name is None:
            return "Fail", "Wrong language passed!"
        git_repo = data.get("repo_name")
        job_instanceid = data.get("job_instanceid")
        job_name = job_instanceid
        environment_vars = data.get("env")
        env_variables = get_env_variables(data)
        current_app.logger.info("env - "+str(data.get("env")))
        input_param_val = {}
        input_param_val = get_env_value(env_variables,'input_params')
        input_params = input_param_val if input_param_val else {}
        mapParams = json.loads(str(input_params))
        cpu_limit = data.get("env").get("CPU_LIMIT","1024")
        ram_limit = data.get("env").get("RAM_LIMIT","1G").replace("i","").lower()
        current_app.logger.info("CPU LIMIT "+str(cpu_limit))
        current_app.logger.info("RAM LIMIT "+str(ram_limit))
        pre_entrypoint_command = "git clone {}://{}:{}@{}/{}/{} hook && chmod -R 777 hook && cd hook".format(
                                    data.get("repo_protocol"),
                                    data.get("git_username"),
                                    data.get("git_access_token"),
                                    data.get("git_server"),
                                    data.get("git_namespace"),
                                    git_repo
                                )
        command = ["/bin/sh", "-c", f'{pre_entrypoint_command} && exec ./entrypoint.sh']
        client = docker.from_env()
        container = client.containers.run(
                image=image_name,
                environment=environment_vars,
                entrypoint=command,
                detach=True,
                name=job_name,
                hostname=job_name,
                mem_limit=ram_limit,
                cpu_shares=int(cpu_limit),
                )
        return "Success", container.id

    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        return "Fail", ""

# pylint: disable-msg=too-many-locals
@log_decorator
def execute_dbt_pod(data):
    """ Create a job for executing the scheduled notebook

    Args:

    JSON payload:
        {
          "file_content": ""
        }

    """

    image_name = get_image_name_by_cloud_data_warehouse(data.get("cloud_data_warehouse"))
    current_app.logger.info("image_name %s", image_name)
    if image_name is None:
        return "Fail", "Wrong cloud_data_warehouse passed!"

    config.load_incluster_config()
    # Preparing the data

    job_name=(data.get("podName").replace("_", "-")).lower()
    current_app.logger.info("job_name %s", job_name)
    env_variables = get_env_variables(data)
    runconfig_details=get_runconfig_details(data)
    sensitive_info=get_sensitive_info(data)
    secret_data=encode_sensitive_info(sensitive_info)

    #creating secrets
    create_secret = client.V1Secret(
        api_version='v1',
        kind='Secret',
        metadata=client.V1ObjectMeta(name=job_name),
        type='Opaque',
        data=secret_data)
    api = client.CoreV1Api()
    api.create_namespaced_secret(namespace=current_app.config["KUBERNETES_NAMESPACE"], body=create_secret)
    secret_env_var=create_secret_env_var(secret_data,job_name)


    # Creating a JOB to execute the notebook
    # Volume
    volume = client.V1Volume(
        name="test-volume",
        empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )
    volumeSourceDir = client.V1Volume(
            name="sourcedir-volume",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name="sourcedir-volume"))


    limits = add_limits_from_run_configuration(runconfig_details)

    # Container
    container = client.V1Container(
        name=job_name,
        image=image_name,
        image_pull_policy="Always",
        ports=[client.V1ContainerPort(container_port=80)],
        command = ["bash", "-c"],
            args = [
                    "chmod 777 /app/{}/{}/executable/entrypoint.sh;"
                     "bash /app/{}/{}/executable/entrypoint.sh;".format(
                    get_env_value(env_variables,'instanceId'),
                    get_env_value(env_variables,'objectName'),
                    get_env_value(env_variables,'instanceId'),
                    get_env_value(env_variables,'objectName'),
                     )
                    ],
        volume_mounts=[
            client.V1VolumeMount(name=volume.name, mount_path="/pre-post-hook"),
            client.V1VolumeMount(name="sourcedir-volume", mount_path="/app")
        ],
        resources=client.V1ResourceRequirements(limits),
        env=env_variables+secret_env_var
    )

    # Template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": job_name}),
        spec=client.V1PodSpec(
            containers=[container],
            volumes=[volume,volumeSourceDir],
            image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
            restart_policy="Never",
        ),

    )

    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=template
    )

    # Pod
    pod = client.V1Job(
        kind="Job", metadata=client.V1ObjectMeta(name=job_name), spec=spec_pod
    )

    # Monitor deployment
    try:
        # Executing the job in specified namespace
        retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
        job_id = is_pod_started(job_name)
        if job_id is None:
            current_app.logger.error(
                "Pod is unable to start for job "
                + str(job_name)
            )
            api.delete_namespaced_secret(job_name,current_app.config["KUBERNETES_NAMESPACE"])
            return "Fail", ""
        current_app.logger.info(
            "Pod is successfully started for job "
            + str(job_name)
            + " and application_id "
            + str(job_id)
        )
        return "Success", job_id


    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        job_id = is_pod_started(job_name)
        current_app.logger.error(
            "Pod is unable to start for job "
            + str(job_name)
            + " and application_id "
            + str(job_id)
        )
        return "Fail", ""




# pylint: disable=too-many-statements, too-many-locals
@log_decorator
def execute_custom_job_per_type(data):
    """ Create a job for executing the scheduled notebook

    Args:

    JSON payload:
        {
          "file_content": ""
        }

    """

    image_name = get_image_name(data.get("language"))
    if image_name is None:
        return "Fail", "Wrong language passed!"

    config.load_incluster_config()
    # Preparing the data

    git_repo = data.get("repo_name")
    initials_job_name = data.get("entity_type").replace("_", "-")
    execution_id = data.get("job_instanceid")

    if data.get("attempt_id"):
        job_name = "{}-execution-{}-{}-job".format(
            initials_job_name, execution_id, data.get("attempt_id")
        )
        service_name = "{}-execution-{}-{}".format(
            initials_job_name, execution_id, data.get("attempt_id")
        )
    else:
        job_name = "{}-execution-{}-job".format(initials_job_name, execution_id)
        service_name = "{}-execution-{}".format(initials_job_name, execution_id)

    cpu_request = data.get("env").get("CPU_REQUEST")
    ram_request = data.get("env").get("RAM_REQUEST")
    cpu_limit = data.get("env").get("CPU_LIMIT")
    ram_limit = data.get("env").get("RAM_LIMIT")

    env_variables = get_env_variables(data)

    # Creating a JOB to execute

    # PV from CM
    code_location = data.get("env").get("CODE_LOCATION")

    # In case of vcs create a emply volume and clone git in that mount
    # In case of volume mount attach pworkflow pvc
    if code_location == "VCS":
        volume = client.V1Volume(
            name="test-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )
        init_container = get_init_container(image_name, data, git_repo, volume)
    elif code_location == "VOLUME_MOUNT":
        volume = client.V1Volume(
            name="workflow-volume",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=current_app.config["WORKFLOW_PVC_NAME"]))

    else:
        raise ValueError(f"Invalid request parameter: CODE_LOCATION: {code_location}")

    volume_tmp = client.V1Volume(name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium=""))

    # Container
    container = client.V1Container(
        name=job_name,
        image=image_name,
        image_pull_policy="Always",
        ports=[client.V1ContainerPort(container_port=80)],
        volume_mounts=[
            client.V1VolumeMount(name=volume.name, mount_path="/pre-post-hook"),
            client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp")
        ],
        env=env_variables,
        resources=client.V1ResourceRequirements(
            limits={"cpu": cpu_limit, "memory": ram_limit},
            requests={"cpu": cpu_request, "memory": ram_request},
        ),
    )

    # Template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": job_name}),
        spec=client.V1PodSpec(
            init_containers=[init_container] if code_location == "VCS" else None,
            containers=[container],
            volumes=[volume,volume_tmp],
            image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
            restart_policy="Never",
            service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
        ),
    )

    project_id = g.user.get('project_id', data.get('repo_name'))
    if project_id:
        node_affinity_options = get_affinity_config(project_id)
        if node_affinity_options:
            template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": job_name}),
                spec=client.V1PodSpec(
                    init_containers=[init_container] if code_location == "VCS" else None,
                    containers=[container],
                    volumes=[volume, volume_tmp],
                    image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
                    restart_policy="Never",
                    service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
                    affinity=client.V1Affinity(
                        node_affinity=client.V1NodeAffinity(
                            required_during_scheduling_ignored_during_execution=add_node_affinity_required(
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_KEY"),
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_OPERATOR"),
                                node_affinity_options.get("NODE_AFFINITY_REQUIRED_VALUES"),
                            )
                        )
                    ),
                    tolerations=[
                        add_tolerations(
                            key=node_affinity_options.get("TOLERATIONS_KEY"),
                            value=node_affinity_options.get("TOLERATIONS_VALUE"),
                            operator=node_affinity_options.get("TOLERATIONS_OPERATOR"),
                            effect=node_affinity_options.get("TOLERATIONS_EFFECT"),
                        )
                    ]
                ),
            )

    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=template
    )

    # Pod
    pod = client.V1Job(
        kind="Job", metadata=client.V1ObjectMeta(name=job_name), spec=spec_pod
    )

    # Service
    service = client.V1Service()
    service.api_version = "v1"
    service.kind = "Service"
    service.metadata = client.V1ObjectMeta(name=service_name)
    spec = client.V1ServiceSpec()
    spec.selector = {"app": job_name}
    spec.ports = [client.V1ServicePort(protocol="TCP", port=80, target_port=8080)]
    service.spec = spec

    # Monitor deployment
    try:
        # Executing the job in specified namespace
        retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
        job_id = is_pod_started(job_name)
        if job_id is None:
            current_app.logger.error(
                "Pod is unable to start for jobInstanceId "
                + str(data.get("job_instanceid"))
            )
            return "Fail", ""
        current_app.logger.debug(
            "Pod is successfully started for jobInstanceId "
            + str(data.get("job_instanceid"))
            + " and application_id "
            + str(job_id)
        )
        # create service
        api_instance = client.CoreV1Api()
        try:
            api_instance.create_namespaced_service(
                body=service, namespace=current_app.config["KUBERNETES_NAMESPACE"]
            )
        # pylint: disable=broad-except
        except Exception as ex:
            current_app.logger.error("Error in starting service")
            print(ex)
        return "Success", job_id
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        job_id = is_pod_started(job_name)
        current_app.logger.error(
            "Pod is unable to start for jobInstanceId "
            + str(data.get("job_instanceid"))
            + " and application_id "
            + str(job_id)
        )
        return "Fail", ""

# pylint: disable=too-many-statements, too-many-locals
@log_decorator
def execute_custom_job_per_type_with_docker(data):
    try:
        image_name = get_image_name(data.get("language"))
        if image_name is None:
            return "Fail", "Wrong language passed!"
        initials_job_name = data.get("entity_type").replace("_", "-")
        execution_id = data.get("job_instanceid")
        if data.get("attempt_id"):
            service_name = "{}-execution-{}-{}".format(
                initials_job_name, execution_id, data.get("attempt_id")
            )
        else:
            service_name = "{}-execution-{}".format(initials_job_name, execution_id)

        cpu_limit = data.get("env").get("CPU_LIMIT")
        ram_limit = data.get("env").get("RAM_LIMIT").replace("i","").lower()
        env = data.get("env")
        port_mapping = {'80/tcp':None}
        network = current_app.config["DOCKER_NETWORK"]
        volume_mount = docker.types.Mount(
            type='bind',  # Indicates a bind mount
            source=current_app.config["HOST_VOLUME_FOR_WORKFLOW"],
            target='/pre-post-hook')

        client = docker.from_env()

        try:
            existing_container = client.containers.get(execution_id)
            existing_container.remove()
        except docker.errors.NotFound:
            current_app.logger.error("Container with same name doesn't exist")

        container = client.containers.run(
                    image=image_name,
                    environment=env,
                    detach=True,
                    name=execution_id,
                    mem_limit=ram_limit,
                    cpu_shares=int(cpu_limit),
                    mounts=[volume_mount],
                    hostname=service_name,
                    ports=port_mapping,
                    network=network
                    )
        return "Success",container.id
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        return "Fail", ex

# pylint: disable=inconsistent-return-statements
def execute_dbt_pod_with_docker(data):
    try:
        image_name = get_image_name_by_cloud_data_warehouse(data.get("cloud_data_warehouse"))
        if image_name is None:
            return "Fail", "Wrong cloud_data_warehouse passed!"
        job_name=(data.get("podName").replace("_", "-")).lower()
        current_app.logger.info("job_name %s", job_name)
        env = data.get("env")
        env_variables = get_env_variables(data)
        runconfig_details=get_runconfig_details(data)

        sensitive_info=get_sensitive_info(data)
        instance_id = get_env_value(env_variables,'instanceId')

        client = docker.APIClient(base_url=current_app.config["DOCKER_SOCKET_PATH"])
        #Creating volume mount
        volume_mount = docker.types.Mount(
            type='bind',
            source=current_app.config["DAG_ENGINE_SOURCEDIR"],
            target="/app"
        )

        secret_data_str = "\n".join([f"{key}={value}" for key, value in sensitive_info.items()]).encode()

        secret_response = client.create_secret(
            name= instance_id,
            data=secret_data_str
        )

        secret_id = secret_response["ID"]

        #Highlighted green command from below will set secrets as env before running dbt
        commands = ["/bin/bash", "-c", 'export $(xargs < /run/secrets/'+instance_id+') && chmod 777 /app/{}/{}/executable/entrypoint.sh && bash /app/{}/{}/executable/entrypoint.sh'
                    .format(get_env_value(env_variables,'instanceId'),
                            get_env_value(env_variables,'objectName'),
                            get_env_value(env_variables,'instanceId'),
                            get_env_value(env_variables,'objectName'))]

        #Creating reference to secrets
        secret = docker.types.SecretReference(secret_name=instance_id, secret_id=secret_id)

        #Creating container specs
        container_spec = docker.types.ContainerSpec(
            image= image_name,
            command=commands,
            mounts=[volume_mount],
            secrets=[secret],
            env=env
        )

        task_template = {
            "ContainerSpec": container_spec,
            "RestartPolicy": {
                "Name": "on-failure",
                "Condition": "none",
                "MaximumRetryCount": 0
            },
            "Resources": get_resources_for_docker(runconfig_details)
        }

        current_app.logger.info("Task template - " +str(task_template))
        service = client.create_service(
            task_template=task_template,
            name=instance_id
        )

        return "Success", service["ID"]
    except Exception as ex:
        current_app.logger.error("Exception: ")
        current_app.logger.error(ex)
        return "Fail", ex


@log_decorator
def get_resources_for_docker(runconfig_details):

        cpu_value_str = runconfig_details.get("cpu","200m")
        memory_limit_str = runconfig_details.get("memory","200Mi")
        numeric_value = int(memory_limit_str[:-2])
        unit = memory_limit_str[-2:]
        int(cpu_value_str[:-1])
        # Define conversion factors for different memory units
        unit_to_bytes = {
            'Ki': 1024,
            'Mi': 1024 * 1024,
            'Gi': 1024 * 1024 * 1024,
            # Add more units as needed
        }

        memory_limit_bytes = numeric_value * unit_to_bytes[unit]
        cpu_cores = 0.2
        if cpu_value_str.endswith("m"):
            # Value is in milliCPU format, extract numeric value and convert to CPU cores
            numeric_value = int(cpu_value_str[:-1])
            cpu_cores = numeric_value / 1000
        else:
             # Value is in regular integer format (number of CPUs)
            cpu_cores = int(cpu_value_str)


        return  {
                    "Limits": {
                        "NanoCPUs": int(cpu_cores * 1000000000),
                        "MemoryBytes": memory_limit_bytes
                    }
                 }

# pylint: disable=inconsistent-return-statements
@log_decorator
def check_job_status(job_name, experiment_id, headers, job_id, request_url):
    """Method to check job status"""
    response_job_status = extension.read_namespaced_job_status(
        name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
    )
    s = response_job_status.status
    if s.active == 1:
        time.sleep(5)
    elif s.failed == 1:
        time.sleep(10)
        response = requests.put(
            request_url,
            json={
                "status": "failed",
                "message": response_job_status.status.conditions[0].message,
            },
            headers=headers,
        )
        if response.status_code == 200:
            current_app.logger.debug(
                "status update succeeded for the experiment_id: {}".format(
                    experiment_id
                )
            )
        else:
            current_app.logger.error(
                "status updated failed for the experiment_id: {}".format(experiment_id)
            )
        extension.delete_namespaced_job(
            name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )
        v1 = client.CoreV1Api()
        v1.delete_namespaced_pod(
            name=job_id, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )
        return "Failed", job_id
    elif s.succeeded == 1:
        response = requests.put(
            request_url,
            json={
                "status": "completed",
                "message": "Experiment job with id {} executed successfully".format(
                    job_id
                ),
            },
            headers=headers,
        )
        if response.status_code == 200:
            current_app.logger.debug(
                "status update succeeded for the experiment_id: {}".format(
                    experiment_id
                )
            )
        else:
            current_app.logger.error(
                "status updated failed for the experiment_id: {}".format(experiment_id)
            )
        return "Success", job_id


@log_decorator
def check_status_for_job(job_name, experiment_id, headers):
    """Method to check status for job"""
    with current_app.app_context():
        job_id = list_namespaced_pod(job_name)
        current_app.logger.debug("fetching job id")
        request_url = "{}/{}".format(current_app.config["AUTO_ML_SERVICE_URL"], experiment_id)
        while True:
            try:
                check_job_status(job_name, experiment_id, headers, job_id, request_url)
            # pylint: disable=broad-except
            except Exception as ex:
                response = requests.put(
                    request_url,
                    json={
                        "status": "aborted",
                        "message": "job deleted for experiment_id: {}".format(
                            experiment_id
                        ),
                    },
                    headers=headers,
                )
                if response.status_code == 200:
                    current_app.logger.debug(
                        "status update succeeded for the experiment_id: {}".format(
                            experiment_id
                        )
                    )
                else:
                    current_app.logger.error(
                        "status updated failed for the experiment_id: {}".format(
                            experiment_id
                        )
                    )
                current_app.logger.error(ex)
                return "Success", job_id


# pylint: disable-msg=too-many-locals
@log_decorator
def execute_experiment(experiment_id, experiment_data, token):
    """
    Create a job for executing the experiment
    :param experiment_id:
    :param experiment_data:
    :return:
    """
    experiment_style = experiment_data['experiment_style']
    input_params = {}
    for key, value in experiment_data['recipe_param']['recipe_run_params'] \
            [experiment_style].items():
        pair = {key : value}
        input_params.update(pair)
    current_app.logger.debug(input_params)
    env_vars = {
        "experiment_id": experiment_id,
        "experiment_recipe_id": experiment_data["experiment_recipe_id"],
        "dataset_name": experiment_data["base_dataset_name"],
        "additional_dataset_params": json.dumps(experiment_data["additional_dataset_params"]),
        "upload_from_catalog": str(experiment_data["upload_from_catalog"]),
        "feature_column": experiment_data["feature_column"],
        "target_column": experiment_data["target_column"],
        "experiment_style": experiment_data["experiment_style"],
        "experiment_type": experiment_data["experiment_type"],
        "experiment_name": experiment_data["experiment_name"],
        "PROJECT_ID": g.user["project_id"],
        "TOKEN": token,
        "MOSAIC_AI_SERVER": current_app.config["MOSAIC_AI_SERVER"]
    }
    env_vars.update(input_params)
    current_app.logger.debug(env_vars)
    # create job name
    revised_notebook_name = experiment_data['recipe_param']['recipe_nb_name'].\
        split("/")[-1].replace(".ipynb", "")
    job_name = "{}-{}-job".format(revised_notebook_name.lower(), uuid_generator())
    # to remove spaces & special characters apart from '-' from job name,
    # keeps only alphanumeric values
    current_app.logger.debug(job_name)
    job_name = "".join(e for e in job_name if e == "-" or e.isalnum())
    if len(job_name) > 55:
        job_name = job_name[-55:]
    current_app.logger.debug(job_name)
    snapshot_name = "automl_{}".format(experiment_data["experiment_recipe_id"])
    snapshot = {"input": snapshot_name, "output": snapshot_name, "container_object": {"name": 'NA'}}
    enabled_repo = {"repo_name": "NA", "branch": "NA"}
    register_snapshot(snapshot, request.headers.get("X-Auth-Username"), request.headers.get("X-Project-Id"),
                      enabled_repo)
    # set environment variables
    env_variables, _ = create_environment_variables(env_vars)

    automl_info = {"experiment_recipe_id": experiment_data["experiment_recipe_id"],
                   "PROJECT_ID": g.user["project_id"]}
    set_token_command = f"echo {token} > /home/mosaic-ai/.mosaic.ai || true;"
    command = [
        "/bin/sh",
        "-c",
        "{}".format(set_token_command)]
    # check if it's an automl job
    command[2] += "{};".format(update_automl_recipe(token, automl_info, 'running'))
    lifecycle_hooks = client.V1Lifecycle(
        post_start=client.V1LifecycleHandler(
            _exec=client.V1ExecAction(
                command=command
            )
        )
    )
    init_script = experiment_data['recipe_param']['init_script']
    cmd = ""
    log_central_on_success = ("pkill tail;")

    log_central_on_fatal = "mv /output/healthy /output/unhealthy;sleep 15;"
    # pylint: disable = line-too-long
    terminate_now = "if [ -z ${{Terminate+x}} ];" \
                    "then {0}; \n {2} \n" \
                    "else {1}; \n {3} \n exit 1; fi; \n".format(
                        update_automl_recipe(token, automl_info, job_status='completed'),
                        update_automl_recipe(token, automl_info, job_status='failed'),
                        log_central_on_success,
                        log_central_on_fatal)
    execution_command = ["/bin/sh",
                         "-c",
                         "source /tmp/requirements.sh; \n {0} \n {1} \n"
                         "{2} \n"
                         "exit 0;".format(cmd, experiment_data['recipe_param']['recipe_execution_command'],
                                          terminate_now)]

    # Creating a JOB to execute the experiment
    # Container
    volume_tmp = client.V1Volume(
        name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )
    volume_mounts = [client.V1VolumeMount(name=g.user["project_id"], mount_path="/data",
                                          sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                          f'/{g.user["project_id"]}/{g.user["project_id"]}-Data'),
                     client.V1VolumeMount(name=g.user["project_id"], mount_path="/output",
                                          sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                          f'/{g.user["project_id"]}/'
                                          f'{g.user["project_id"]}-Snapshot'
                                          f'/{snapshot_name}'),
                    client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp")]

    init_container = client.V1Container(
        name="init",
        image=current_app.config["GIT_IMAGE_NAME"],
        image_pull_policy="IfNotPresent",
        command=[
            "/bin/sh",
            "-c",
            "touch /output/central.log; \n"
            "touch /tmp/requirements.sh;\n"
            "touch /output/healthy; \n"
            f'echo "{init_script}" > /tmp/requirements.sh; \n'
            "echo \"===== * $(date '+%d/%m/%Y %H:%M:%S') * ===== \" >> /output/central.log; \n"
        ],
        volume_mounts=volume_mounts,
        resources=client.V1ResourceRequirements(
            limits=json.loads(current_app.config["GIT_INIT_CONTAINER_LIMIT"]),
            requests=json.loads(current_app.config["GIT_INIT_CONTAINER_REQUEST"]),
        )
    )
    container = client.V1Container(
        name=job_name,
        image=experiment_data['recipe_param']['recipe_docker_url'],
        image_pull_policy="Always",
        ports=[client.V1ContainerPort(container_port=80)],
        env=env_variables,
        lifecycle=lifecycle_hooks,
        volume_mounts=volume_mounts,
        resources=client.V1ResourceRequirements(
            limits=fetch_resource_limitscaling_guarantee(
                experiment_data['resource_json']['cpu'],
                experiment_data['resource_json']['mem'],
                experiment_data['resource_json']['extra'],
                current_app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"],
                current_app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"]
            ),
            requests=fetch_resource_request_limit(experiment_data['resource_json']['cpu'],
                                                  experiment_data['resource_json']['mem'],
                                                  current_app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"],
                                                  current_app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"],
                                                  experiment_data['resource_json']['extra'])
        ),
        command=execution_command,
    )

    log_central = client.V1Container(
        name="log-central",
        image=current_app.config["GIT_IMAGE_NAME"],
        image_pull_policy="IfNotPresent",
        volume_mounts=volume_mounts,
        liveness_probe=client.V1Probe(_exec=client.V1ExecAction(
            command=["cat", "/output/healthy"]),
                                      initial_delay_seconds=5,
                                      period_seconds=5,
                                      timeout_seconds=4),
        command=[
            "/bin/sh",
            "-c",
            "tail -n+1 -f /output/central.log; \n"
            "true;"
        ]
    )
    job_volume = get_volumes(
        project_id=g.user["project_id"],
        username=g.user["mosaicId"])
    job_volume.append(volume_tmp)
    job_uid = os.getuid()
    job_gid = os.getgid()
    #template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=attach_metadata_lable_to_pod(job_name)),
        spec=client.V1PodSpec(restart_policy="Never",
                              share_process_namespace=True,
                              init_containers=[init_container],
                              containers=[container, log_central],
                              service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
                              image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
                              volumes=job_volume,
                              security_context=client.V1PodSecurityContext(run_as_user=job_uid,
                                                     run_as_group=job_gid
                                                     )
                              )
    )
    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=template
    )
    # Pod
    pod = client.V1Job(
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=spec_pod
    )
    try:
        current_app.logger.debug("Creating Job")
        # Executing the job in specified namespace
        retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
        current_app.logger.debug("entering list namespaced pod")
        job_id = list_namespaced_pod(job_name)
        #current_app.logger.debug(StatusCodes.MOSAIC_0002)
        current_app.logger.debug(job_id)
        return {
            "job_name": job_id,
            "snapshot_name": snapshot_name
        }
    # pylint: disable=broad-except
    except Exception as ex:
        job_id = list_namespaced_pod(job_name)
        v1 = client.CoreV1Api()
        extension.delete_namespaced_job(
            name=job_name, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )
        v1.delete_namespaced_pod(
            name=job_id, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )

        current_app.logger.error(ex)
        job_status = "failed"
        return {
            "job_status": job_status,
            "snapshot_name": snapshot_name
        }


@log_decorator
def uuid_generator():
    """Method to generate uuid"""
    _uuid = uuid4()
    return str(_uuid)


@log_decorator
def replace_special_chars_with_ascii(password):
    """Method that returns ascii"""
    # Function checks if the password
    # contains any special character
    # if found, it will encode it
    return urllib.parse.quote(password)


@log_decorator
def package_target_path(nas_location, base_docker_image_name, template_id, version=None):
    py_version = version
    template_name = base_docker_image_name

    return os.path.join(os.path.sep, nas_location, template_name, template_id, py_version)

# pylint: disable=too-many-branches
@log_decorator
def create_package_installation(kernel_type, pip_packages, cran_packages, init_script, conda_packages, lib_path="/tmp", project_id=None, log_id=None, experiment_name=None):
    """Method to get installation command"""
    py_url = current_app.config["PYPI_PACKAGE_REPO"]
    cran_url = current_app.config["R_PACKAGE_REPO"]
    conda_url = current_app.config["CONDA_PACKAGE_REPO"]
    conda_r_url = current_app.config["CONDA_R_PACKAGE_REPO"]
    log_directory = current_app.config["LOG_DIRECTORY"]
    conda_cmd = ''
    trusted_host = urllib.parse.urlparse(py_url).hostname
    init_script_path = "{0}/{1}_{2}_init-script.log".format(log_directory, log_id, project_id)
    package_file_path = "{0}/{1}_{2}_package-installation.log".format(log_directory, log_id, project_id)


    if kernel_type in [KernelType.python, KernelType.spark, KernelType.spark_distributed, KernelType.vscode_python]:
        # Try to install conda package first with pip, if its not available in
        # pip then only install via conda
        # Reason behind this we are using old pip which do not
        # check package compability , but conda does check &
        # avoid installation in case of any compatibility issue
        # AILOG-1780 AILOG-1781
        # Handling init-script command write at nas level
        # marking init-script empty for default init-script.log file creation
        if experiment_name:
            pip_packages = "" if (not pip_packages or pip_packages.isspace()) else pip_packages
            pip_packages = pip_packages + current_app.config.get('MLFLOW_DEPENDENCY_PACKAGES') if current_app.config.get('MLFLOW_DEPENDENCY_PACKAGES') else pip_packages
        if init_script is None or init_script == "" or init_script.isspace():
            init_cmd = ""
        else:
            current_app.logger.debug(init_script)
            # converting init-script commands into a list of commands
            init_arr = init_script.split('\n')
            init_cmd = ''
            for i in init_arr:
                if i == '':
                    continue
                if i == '#/bin/bash':
                    init_cmd = init_cmd + i + '\n'
                    continue
                init_cmd = init_cmd + i + ' >> {0} 2>&1;'.format(init_script_path)
        if conda_packages:
            conda_packages_list = conda_packages.split(' ')
            for each_package in conda_packages_list:
                conda_cmd += "pip install --trusted-host {3} -i {0} {1} >> {4} " \
                             "2>&1 || conda install -c {2} " \
                             "--yes {1} --override-channels >> " \
                             "{4} 2>&1;".format(py_url, each_package,
                                                conda_url, trusted_host, package_file_path)
        if pip_packages is None or pip_packages == "" or pip_packages.isspace():
            installation_command = "{0}  {1}".format(init_cmd, conda_cmd)
        else:
            package_type = 'pip'
            installation_command = "{3} " \
                               "python /code/nas_package.py -nas_location {4} -pkg_dependency \"{1}\" -package_type {5};" \
                                   "cat /tmp/package_present_in_venv_different_version_{5}.txt | xargs -n 1 pip uninstall --yes >> /tmp/package-uninstallation.log 2>&1;" \
                                   "cat /tmp/missing_package_final_{5}.txt | xargs -n 1 pip install --target {6} --trusted-host {7} -i {0} --upgrade >> {8} 2>&1;" \
                            " {2} ".format(py_url, pip_packages, conda_cmd, init_cmd, current_app.config['TEMPLATE_NAS_DIRECTORY'], package_type, lib_path, trusted_host, package_file_path)
    elif kernel_type in [KernelType.r_kernel, KernelType.rstudio_kernel]:
        if init_script is None or init_script == "" or init_script.isspace():
            init_script = ""
        else:
            init_script_cmd = '''R -e "system(\\" {0} \\")"'''
            init_script = init_script_cmd.format(init_script)

        if conda_packages:
            conda_packages_list = conda_packages.split(' ')
            conda_cmd = ''
            for each_package in conda_packages_list:
                # pylint: disable = line-too-long
                conda_cmd += "conda install -c {0} --yes {1} --override-channels >> {2} 2>&1;" \
                    .format(conda_r_url, each_package, package_file_path)
        if cran_packages:
            cran_installation_command = _build_cran_package_install(kernel_type, cran_packages, cran_url)
            # pylint: disable = line-too-long
            installation_command = f'\n {init_script} >> {init_script_path} 2>&1; {cran_installation_command} >> {package_file_path} 2>&1; \n {conda_cmd} >> {package_file_path} 2>&1;'
        else:
            installation_command = f' \n {init_script} >> {init_script_path}  2>&1; \n {conda_cmd} >> {package_file_path}  2>&1;'

    else:
        installation_command = ""

    # creating default package files at nas location when init-script and dependency section is empty
    end_message = "-------End of log file------------"
    no_package_init_message = "No command specified in init-script that produces logs."
    no_package_depend_message = "No Package specified in dependency section that needs to be installed"
    init_end_cmd = "[ -s {0} ] && echo {1} >> {0} 2>&1 || echo {2} >> {0} 2>&1; ".format(init_script_path, end_message, no_package_init_message)
    dependency_end_cmd = "[ -s {0} ] && echo {1} >> {0} 2>&1 || echo {2} >> {0} 2>&1; ".format(package_file_path, end_message, no_package_depend_message)
    installation_command = installation_command + init_end_cmd + dependency_end_cmd

    return installation_command



def _build_cran_package_install(kernel_type, cran_packages, cran_url):
    if kernel_type == KernelType.rstudio_kernel:
        cran_installation_command = f"python /code/nas_package_R.py -operation PACKAGE_INSTALL -package_type CRAN"
    else:
        package_command = ['library(remotes);']
        for package in cran_packages:
            # pylint: disable = line-too-long
            command = f'tryCatch({{remotes::install_version("{package}", "{cran_packages[package]}", repos="{cran_url}", dependencies=TRUE, silent = TRUE)}}, error = function(e) {{print(e)}});'
            package_command.append(command)
        cran_installation_command = f'R -e \'{" ".join(package_command)}\''
    return cran_installation_command


@log_decorator
def create_metering_request(metering_info):
    """Method to get metering create request command"""
    start_metering_url = (
        current_app.config["METERING_BACKEND_URL"] +
        Metering.create_request.format(subscriber_id=metering_info['subscriber_id'])
    )
    current_app.logger.debug(start_metering_url)
    # pylint: disable = line-too-long
    start_metering_command = "curl -X POST \"{0}\" -H \"accept:application/json\" -H \"X-Auth-Userid:{1}\" -H \"Content-Type:application/json\" -d \'{{\"user_id\":\"{2}\", \"resource_key\":\"{3}\", \"resource_request\":{4}, \"pod_id\":\"{5}\", \"description\":\"{6}\", \"project_id\":\"{7}\"}}\';".format(
        start_metering_url,
        metering_info['user_id'],
        metering_info['user_id'],
        metering_info['resource_key'],
        metering_info['resource_request'],
        metering_info['pod_id'],
        metering_info['description'],
        metering_info['project_id'])
    current_app.logger.debug(start_metering_command)
    return start_metering_command


@log_decorator
def stop_metering_request(metering_info):
    """Method to get metering create request command"""
    stop_metering_url = (
        current_app.config["METERING_BACKEND_URL"] +
        Metering.update_usage.format(pod_id=metering_info['pod_id'])
    )
    current_app.logger.debug(stop_metering_url)
    # pylint: disable = line-too-long
    stop_metering_command = "curl -X PUT \"{0}\" -H \"accept:application/json\" -H \"X-Auth-Userid:{1}\"".format(
        stop_metering_url,
        metering_info['user_id'])
    current_app.logger.debug(stop_metering_command)
    return stop_metering_command


@log_decorator
def delete_resources_onstop(template_id):
    """Method to delete svc/ing and update template status on pod delete command"""
    delete_resources_url = (
        current_app.config["NOTEBOOKS_API_SERVER_URL"] +
        Notebooks.delete_pod.format(template_id=template_id)
    )
    current_app.logger.debug(delete_resources_url)
    # pylint: disable = line-too-long
    delete_resources_command = "\n curl -X DELETE \"{0}\" -H \"accept: application/json\" -H \"X-Auth-Userid: {1}\" -H \"X-Auth-Username: {1}\" -H \"X-Auth-Email: {1}\" -H \"X-Project-Id: {2}\" \n".format(
        delete_resources_url,
        g.user["mosaicId"],
        g.user["project_id"])
    current_app.logger.debug(delete_resources_command)
    return delete_resources_command

@log_decorator
def create_prometheus_payload(pod_name, additional_params):
    """
    Method returns common payload required for prometheus api
    :param pod_name: K8s pod name
    :param additional_params: optional keys - step, end, start
    :return:
    """
    _pod_name = current_app.config["PODNAME"]
    _container_name = current_app.config["CONTAINERNAME"]

    cpu_usage_query_string = {
        "query": "sum(rate(container_cpu_usage_seconds_total{"
                 f"{_container_name}!='POD',"
                 f"namespace!='',{_pod_name}="
                 f"'{pod_name}'"
                 f",{_container_name}!='', "
                 f"{_container_name}!="
                 "'knights-watch'}[2m]))"
                 f" by ({_pod_name})"
    }
    mem_usage_querystring = {
        "query": "sum(container_memory_usage_bytes{"
                 f"{_container_name}!='POD',namespace!='',"
                 f"{_pod_name}="
                 f"'{pod_name}'"
                 f",{_container_name}!='', "
                 f"{_container_name}!="
                 "'knights-watch'})"
                 f" by ({_pod_name}) / 1000000"
    }
    cpu_usage_query_string.update(additional_params)
    mem_usage_querystring.update(additional_params)
    return cpu_usage_query_string, mem_usage_querystring


def get_pod_metrics_range(pod_name: str, service_name: str, start: float, end: float, step: int, time_series_data=False):
    """
    :param time_series_data:
    :param pod_name: k8s pod name
    :param service_name: prometheus api
    :param start: start timestamp
    :param end: end timestamp
    :param step:
    :return:
    """
    try:
        current_app.logger.debug("Fetching Query Range for %s %s %s %s", pod_name, start, end, step)

        url = f"{service_name}/api/v1/query_range"
        _pod_name = current_app.config["PODNAME"]
        additional_params = {"start":start, "end":end, "step":step}
        cpu_usage_query_string, mem_usage_querystring = create_prometheus_payload(pod_name, additional_params)

        mem_response = requests.get(url, params=mem_usage_querystring)
        cpu_response = requests.get(url, params=cpu_usage_query_string)

        mem_response.raise_for_status()
        cpu_response.raise_for_status()

        if (
                cpu_response.json()["data"]["result"] and mem_response.json()["data"]["result"]
        ):
            cpu_list = [float(x[1]) for x in cpu_response.json()["data"]["result"][0]["values"]]
            mem_list = [float(x[1]) for x in mem_response.json()["data"]["result"][0]["values"]]

            pod_metrics = {
                "pod": cpu_response.json()["data"]["result"][0]["metric"][f"{_pod_name}"],
                "cpu_utilization": {
                    "mean": round(mean(cpu_list), 2),
                    "max": round(max(cpu_list), 2),
                    "min": round(min(cpu_list), 2),
                },
                "memory_utilization": {
                    "mean": round(mean(mem_list), 2),
                    "max": round(max(mem_list), 2),
                    "min": round(min(mem_list), 2),
                },
            }
            if time_series_data:
                pod_metrics["cpu_utilization_data"] = cpu_response.json()["data"]["result"][0]["values"]
                pod_metrics["memory_utilization_data"] = mem_response.json()["data"]["result"][0]["values"]
        else:
            pod_metrics = {}

        return pod_metrics

    except Exception as ex:
        current_app.logger.error(ex)
        raise ValueError("unable to fetch pod metrics")


@log_decorator
def get_pod_metrics(pod_name, service_name):
    """Method to get pod metrics"""
    try:
        url = f"{service_name}/api/v1/query"
        _pod_name = current_app.config["PODNAME"]
        cpu_usage_query_string, mem_usage_querystring = create_prometheus_payload(pod_name, {})

        mem_response = requests.get(url, params=mem_usage_querystring)
        cpu_response = requests.get(url, params=cpu_usage_query_string)

        print(mem_response.json())
        print(cpu_response.json())

        mem_response.raise_for_status()
        cpu_response.raise_for_status()
        if (
                cpu_response.json()["data"]["result"] and mem_response.json()["data"]["result"]
        ):
            pod_metrics = {
                "pod": cpu_response.json()["data"]["result"][0]["metric"][f"{_pod_name}"],
                "cpu_utilization": {
                    "time": cpu_response.json()["data"]["result"][0]["value"][0],
                    "cpu_percent": cpu_response.json()["data"]["result"][0]["value"][1],
                },
                "mempry_utilization": {
                    "time": mem_response.json()["data"]["result"][0]["value"][0],
                    "memory": mem_response.json()["data"]["result"][0]["value"][1],
                },
            }
        else:
            pod_metrics = {}
        return pod_metrics
    except Exception as ex:
        current_app.logger.error(ex)
        raise ValueError("unable to fetch pod metrics")

@log_decorator
def time_since_pod_started(pod_name, service_name):
    """Return the time period since the pod was started till the current time"""
    url = f"{service_name}/api/v1/query"
    _pod_name = current_app.config["PODNAME"]
    _container_name = current_app.config["CONTAINERNAME"]
    container_name = 'notebooks'

    time_since_pod_started_query_string = {
        "query": "time() - sum(container_start_time_seconds{" +
                 f"{_pod_name}=\"{pod_name}\",{_container_name}=\"{container_name}\"" +
                 "})"
    }

    time_response = requests.get(url, params=time_since_pod_started_query_string)
    time_response.raise_for_status()
    return time_response.json()["data"]["result"][0]["value"][1]

@log_decorator
def get_pod_metrics_max(pod_name, service_name):
    try:
        url = f"{service_name}/api/v1/query"
        _pod_name = current_app.config["PODNAME"]
        _container_name = current_app.config["CONTAINERNAME"]
        _time_since_pod_started = time_since_pod_started(pod_name, service_name).split('.')[0] + 's'

        cpu_usage_query_string = {
            "query": "max_over_time(sum(rate(container_cpu_usage_seconds_total{"
                     f"{_pod_name}="f"'{pod_name}',"
                     f"{_container_name}=""'notebooks'}[2m]))"
                     f"[{_time_since_pod_started}:1s])"
        }

        mem_usage_querystring = {
            "query": "max(container_memory_max_usage_bytes{"
                     f"{_pod_name}="f"'{pod_name}',"
                     f"{_container_name}=""'notebooks'})/1000000"
        }

        cpu_response = requests.get(url, params=cpu_usage_query_string)
        mem_response = requests.get(url, params=mem_usage_querystring)

        cpu_response.raise_for_status()
        mem_response.raise_for_status()

        if cpu_response.json()["data"]["result"] and mem_response.json()["data"]["result"]:
            metrics_max = {
                "pod": pod_name,
                "max_cpu_utilization": {
                    "time": cpu_response.json()["data"]["result"][0]["value"][0],
                    "cpu": cpu_response.json()["data"]["result"][0]["value"][1],
                },
                "max_memory_utilization": {
                    "time": mem_response.json()["data"]["result"][0]["value"][0],
                    "memory": mem_response.json()["data"]["result"][0]["value"][1],
                }
            }

        else:
            metrics_max = {}
        return metrics_max
    except Exception as ex:
        current_app.logger.error(ex)
        raise ValueError("unable to fetch max pod metrics")

@log_decorator
def delete_job(name, namespace):
    """Delete job and pod.

    :param name: job name
    :param namespace: job namespace
    """
    try:
        data = extension.delete_namespaced_job(
            name,
            namespace=namespace,
            body=client.V1DeleteOptions(propagation_policy="Background"),
        )
        current_app.logger.debug(data)
        return "success"
    except Exception as ex:
        current_app.logger.error(ex)
        raise ValueError("unable to delete job")


# pylint: disable=too-few-public-methods
class DeploymentTemplateNames:
    """Deployment template names class"""
    default_endpoints_template = "manifests/endpoints.yaml"
    default_cron_template = "manifests/cronjob.yaml"
    default_job_template = "manifests/job.yaml"

    def get_default_service_template(self):
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            return "manifests/service_alb.yaml"
        else:
            return "manifests/service.yaml"

    def get_default_ingress_template(self):
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            return "manifests/ingress_alb.yaml"
        else:
            return "manifests/ingress.yaml"

    def get_default_namespace(self):
        return current_app.config["KUBERNETES_NAMESPACE_KNIGHTS_WATCH"]

    def get_default_host(self):
        return current_app.config["DEFAULT_HOST"]


class DeploymentSidecarNames:
    """Deployment template names class"""
    # if get_application().config["INGRESS_CONTROLLER"] == 'alb':
    def get_default_service_template(self):
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            return "manifests/byoc/service_alb.yaml"
        else:
            return "manifests/byoc/service.yaml"

    def get_default_ingress_template(self):
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            return "manifests/byoc/ingress_alb.yaml"
        else:
            return "manifests/byoc/ingress.yaml"

    def get_default_endpoint_template(self):
        return "manifests/byoc/endpoints.yaml"


@log_decorator
def load_template(template_name):
    """
        Loads the necessary template
        :param template_name:
        :return:
        """
    with open(os.path.join(os.path.dirname(__file__), template_name)) as f:
        template_yaml = f.read()
        return template_yaml


class JobFactory:
    def __init__(self, job_name, job_type):
        job_map = {
            "job": Job,
            "cronjob": CronJob
        }
        self.select = job_map[job_type](job_name)

    def create(self, cron_dict):
        return self.select.create(cron_dict)


class Job:
    def __init__(self, job_name):
        self.job_name = job_name
        self.namespace = DeploymentTemplateNames().get_default_namespace()

    @log_decorator
    def create(self, cron_dict):
        job_yaml = load_template(DeploymentTemplateNames().default_job_template)
        job_yaml = job_yaml.format(
            namespace=self.namespace,
            jobName=self.job_name,
            image=cron_dict["image"],
            envVar=cron_dict["envVar"],
            command=cron_dict["command"],
            image_pull_secret=cron_dict["image_pull_secret"]
        )
        job_manifest = yaml.safe_load(job_yaml)
        current_app.logger.debug(job_manifest)
        try:
            extension.create_namespaced_job(self.namespace, body=job_manifest)
            current_app.logger.info("Job created for job_name: {}".format(self.job_name))
            return "success"
        except Exception as ex:
            current_app.logger.error(ex)


class CronJob:
    def __init__(self, job_name):
        self.job_name = job_name
        self.namespace = DeploymentTemplateNames().get_default_namespace()

    @log_decorator
    def create(self, cron_dict):
        cronjob_yaml = load_template(DeploymentTemplateNames().default_cron_template)
        cronjob_yaml = cronjob_yaml.format(
            namespace=self.namespace,
            jobName=self.job_name,
            image=cron_dict["image"],
            cronSchedule=cron_dict["cronSchedule"],
            envVar=cron_dict["envVar"],
            command=cron_dict["command"],
            concurrencyPolicy=cron_dict["concurrencyPolicy"],
            image_pull_secret=cron_dict["image_pull_secret"],
            timeZone=cron_dict["timeZone"]
        )
        cronjob_manifest = yaml.safe_load(cronjob_yaml)
        current_app.logger.debug(cronjob_manifest)
        # create cronjob
        try:
            extension.create_namespaced_cron_job(self.namespace, body=cronjob_manifest)
            current_app.logger.info("Cronjob created for job_name: {}".format(self.job_name))
            return "success"
        except Exception as ex:
            current_app.logger.error(ex)

    @log_decorator
    def delete(self):
        """Method to delete cron job in kubernetes"""
        try:
            extension.delete_namespaced_cron_job(self.job_name, self.namespace)
            current_app.logger.info("Cronjob deleted for job_name: {}".format(self.job_name))
            return "success"
        except Exception as ex:
            current_app.logger.error(ex)

    @log_decorator
    def suspend_and_resume(self, action):
        """Method to suspend or resume cron job in kubernetes"""
        body = {
            "spec": {}
        }
        try:
            body["spec"]["suspend"] = Cron.action_dict[action]
            extension.patch_namespaced_cron_job(self.job_name, self.namespace, body)
            current_app.logger.info("Cron job {}: {}".format(self.job_name, action))
            return "success"
        except Exception as ex:
            current_app.logger.error(ex)

    @log_decorator
    def update(self, cron_schedule, env_var):
        """Method to update cron expression and env variables on existing cron job in kubernetes"""
        cron_env = []
        for key, value in env_var.items():
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            env = {"name": key, "value": value}
            cron_env.append(env)

        try:
            response = extension.read_namespaced_cron_job(self.job_name, self.namespace)
            updated_dict = response.to_dict()
            updated_dict["spec"]["schedule"] = cron_schedule
            updated_dict["spec"]["jobTemplate"] = updated_dict["spec"].pop("job_template")
            updated_dict["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["env"] = cron_env

            extension.patch_namespaced_cron_job(self.job_name, self.namespace, updated_dict)
            current_app.logger.info("Cronjob updated for job_name: {}".format(self.job_name))
            return "success"
        except Exception as ex:
            current_app.logger.error(ex)


@log_decorator
def create_cronjob_or_instantaneous_job(data):
    """ Method to create cron job or instantaneous job in kubernetes
        based on request"""

    job_name = data["jobName"]
    cron_schedule = data.get("cronExpression")
    cron_flag = data["cronFlag"]
    env_var = data["envVar"]
    time_zone = env_var["timeZone"]
    cron_env = []
    for key, value in env_var.items():
        if isinstance(value, int) or isinstance(value, float):
            value = str(value)
        env = {"name": key, "value": value}
        cron_env.append(env)

    cron_dict = {
        "image": data["image"],
        "cronSchedule": cron_schedule,
        "envVar": cron_env,
        "command": data.get("command", ""),
        "concurrencyPolicy": data.get("concurrencyPolicy", "Forbid"),
        "image_pull_secret": current_app.config["IMAGE_PULL_SECRETS"],
        "timeZone": time_zone
    }
    if not cron_schedule and cron_flag is False:
        job_type = "job"
    elif cron_schedule and cron_flag is True:
        job_type = "cronjob"
    else:
        current_app.logger.info("Invalid request")
        return None
    try:
        response = JobFactory(job_name, job_type).create(cron_dict)
        return response
    except Exception as ex:
        current_app.logger.error(ex)



@log_decorator
def create_ingress(pod_name, template_id, namespace, host):
    """Method that creates ingress in kubernetes"""
    # load default ingress template
    ingress_yaml = load_template(DeploymentTemplateNames().get_default_ingress_template())
    if current_app.config["INGRESS_CONTROLLER"] == 'alb':
        ingress_yaml = ingress_yaml.format(
            ingress_class=current_app.config["INGRESS_CONTROLLER"],
            namespace=namespace,
            pod_name=pod_name,
            template_id=template_id,
            listen_ports=current_app.config["ALB_LISTEN_PORTS"],
            group_order=find_unique_ingress_order(),
            alb_group_name=current_app.config["ALB_GROUP_NAME"],
            alb_inbound_cidrs=current_app.config["ALB_INBOUND_CIDRS"],
            alb_scheme=current_app.config["ALB_SCHEME"],
            alb_target_type=current_app.config["ALB_TARGET_TYPE"]
        )
    else:
        ingress_yaml = ingress_yaml.format(
            ingress_class=current_app.config["INGRESS_CONTROLLER"],
            pathType=current_app.config.get("INGRESS_PATHTYPE", "Prefix"),
            namespace=namespace,
            host=host,
            pod_name=pod_name, template_id=template_id
        )
    ingress_manifest = yaml.safe_load(ingress_yaml)
    current_app.logger.debug(ingress_manifest)
    # create ingress
    k8s_network = client.NetworkingV1Api()
    try:
        k8s_network.create_namespaced_ingress(body=ingress_manifest, namespace=namespace)
        current_app.logger.debug(
            "ingress created for pod_name: {} template_id : {}".format(
                pod_name, template_id
            )
        )
        return "success"
    # pylint: disable=broad-except
    except Exception as ex:
        if ex.reason != "Conflict":
            current_app.logger.error(ex.reason)
            current_app.logger.error(ex)
            raise ex


@log_decorator
def create_endpoints(template_id, pods_internal_ip, namespace):
    """Creates endpoints in kubernetes"""
    api = client.CoreV1Api()
    # load default endpoints template
    endpoints_yaml = load_template(DeploymentTemplateNames().default_endpoints_template)

    endpoints_yaml = endpoints_yaml.format(
        pods_internal_ip=pods_internal_ip, namespace=namespace, template_id=template_id
    )
    endpoints_manifest = yaml.safe_load(endpoints_yaml)
    current_app.logger.debug(endpoints_manifest)
    # create endpoints
    try:
        api.create_namespaced_endpoints(body=endpoints_manifest, namespace=namespace)
    # pylint: disable=broad-except
    except Exception as ex:
        if ex.reason != "Conflict":
            current_app.logger.error(ex)


@log_decorator
def create_service(namespace, template_id, pod_name, kernel_type=None):
    """Creates service in kubernetes"""
    api = client.CoreV1Api()
    # load default endpoints template
    if kernel_type == KernelType.spark_distributed:
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            service_yaml = load_template("manifests/spark_distributed_service_alb.yaml")
        else:
            service_yaml = load_template("manifests/spark_distributed_service.yaml")
    else:
        service_yaml = load_template(DeploymentTemplateNames().get_default_service_template())
    if current_app.config["INGRESS_CONTROLLER"] == 'alb':
        service_yaml = service_yaml.format(namespace=namespace,
                                           template_id=template_id,
                                           service_type=current_app.config["SERVICE_TYPE"],
                                           container_name=pod_name)
    else:
        service_yaml = service_yaml.format(namespace=namespace, template_id=template_id, container_name=pod_name)
    service_manifest = yaml.safe_load(service_yaml)
    current_app.logger.debug(service_manifest)
    # create service
    try:
        api.create_namespaced_service(body=service_manifest, namespace=namespace)
    # pylint: disable=broad-except
    except Exception as ex:
        if ex.reason != "Conflict":
            current_app.logger.error(ex)
            raise ex


@log_decorator
def create_k8_resources(pod_name, template_id, kernel_type=None):
    """Creates kubernetes resources"""
    try:
        current_app.logger.debug("kubespawner : start of create_k8_resources")
        api = client.CoreV1Api()
        namespace = DeploymentTemplateNames().get_default_namespace()
        host = DeploymentTemplateNames().get_default_host()
        response = api.read_namespaced_pod(pod_name, namespace)
        pod = response.to_dict()
        current_app.logger.debug("{}, {}".format(pod_name, namespace))
        # adding pod.status.pod_ip is not None for pending pod condition
        # where we don't get IP
        if pod.get("status").get("pod_ip") is not None:
            pods_internal_ip = pod.get("status").get("pod_ip")
            current_app.logger.debug("kubespawner : function create_service")
            create_service(namespace, template_id, pod_name, kernel_type)
            current_app.logger.debug("kubespawner : function create_endpoints")
            create_endpoints(template_id, pods_internal_ip, namespace)
            current_app.logger.debug("kubespawner : function create_ingress")
            create_ingress(pod_name, template_id, namespace, host)
            current_app.logger.debug("kubespawner : end of create_k8_resources")
        current_app.logger.debug("kubespawner : end of create_k8_resources")
    except Exception as e:
        raise e

@log_decorator
def delete_k8_resources(template_id):
    """Deletes kubernetes resources"""
    current_app.logger.debug("kubespawner : start of delete_k8_resources")
    template_id = "jupyter-endpoints-" + str(template_id)
    namespace = DeploymentTemplateNames().get_default_namespace()
    delete_successful = True

    delete_successful = _delete_namespaced_endpoints(delete_successful, namespace, template_id)

    delete_successful = _delete_namespaced_service(delete_successful, namespace, template_id)

    delete_successful = _delete_namespaced_ingress(delete_successful, namespace, template_id)

    current_app.logger.debug("kubespawner : end of delete_k8_resources")
    return delete_successful


def _delete_namespaced_ingress(delete_successful, namespace, template_id):
    try:
        k8s_network = client.NetworkingV1Api()
        api_response = k8s_network.delete_namespaced_ingress(
            name=template_id,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        #current_app.logger.debug("Ingress deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    return delete_successful


def _delete_namespaced_service(delete_successful, namespace, template_id):
    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_service(
            name=template_id,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        #current_app.logger.debug("Service deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    return delete_successful


def _delete_namespaced_endpoints(delete_successful, namespace, template_id):
    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_endpoints(
            name=template_id,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        #current_app.logger.debug("Endpoint deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    return delete_successful


def delete_k8_service_obj(obj_to_del):
    "Deletes kubernetes service objects"

    current_app.logger.debug("kubespawner : Starting to delete k8 service objects")
    namespace = DeploymentTemplateNames().get_default_namespace()
    delete_successful = True
    try:
        k8_api = client.CoreV1Api()
        for i in obj_to_del.keys():
            for ele in obj_to_del[i]:
                delete_successful = _delete_namespaced_service(delete_successful, namespace, ele)

                delete_successful = _delete_namespaced_endpoints(delete_successful, namespace, ele)

                delete_successful = _delete_namespaced_ingress(delete_successful, namespace, ele)

                delete_successful = _delete_pod(delete_successful, namespace, ele)

                delete_successful = _delete_job(delete_successful, ele, namespace)


    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)

    current_app.logger.debug("kubespawner : end of delete_k8_service objects")
    return delete_successful

def _delete_pod(delete_successful, namespace, ele):
    try:
        k8_api = client.CoreV1Api()
        k8_api.delete_namespaced_pod(
            name=ele,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
    except client.rest.ApiException as ex:
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    return delete_successful


def _delete_job(delete_successful, ele, namespace):
    try:
        extension.delete_namespaced_job(
            name=ele,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Background")
        )
    except client.rest.ApiException as ex:
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    return delete_successful


@log_decorator
def delete_pod(name, namespace):
    """ Method to delete pod by pod name

    :param name: pod name
    :param namespace: pod namespace
    """
    try:
        current_app.logger.debug("kubespawner : start of delete_pod")
        v1 = client.CoreV1Api()
        v1.delete_namespaced_pod(name=name, namespace=namespace)
        current_app.logger.debug("kubespawner : end of delete_pod")
        return "success"
    except Exception as ex:
        current_app.logger.error(ex)
        raise ValueError("unable to delete pod")


@log_decorator
def get_env_value(env, key):
    """ This returns value of env key specified"""
    try:
        for item in env:
            if item.get("name") == key:
                return item.get("value")
    except Exception as ex:
        current_app.logger.error(key)
        current_app.logger.error(ex)


@log_decorator
def get_config_from_cm(env, cm_file_name, config_dict):
    """ This function sets env variable from configmap """
    for key, value in config_dict.items():
        config_map_ref = client.V1ConfigMapKeySelector(
            key=key,
            name=cm_file_name)
        env_var = client.V1EnvVarSource(
            config_map_key_ref=config_map_ref)
        env_object = client.V1EnvVar(
            name=value,
            value_from=env_var)
        env.append(env_object)
    return env


@log_decorator
def get_lifecycle(kernel_type, pip_packages, conda_packages, cran_packages, init_script, env,
                  metering_info):
    """ Generate post lifecycle hook"""
    # pylint: disable=no-else-return
    # pylint: disable=no-else-return, line-too-long
    current_app.logger.debug("inside function get_lifecycle")
    current_app.logger.debug(env)
    os = get_env_value(env, 'os')
    current_app.logger.debug("OS IS : %s", os)
    # pylint: disable=no-else-return, line-too-long
    if kernel_type in [KernelType.python, KernelType.spark, KernelType.spark_distributed, KernelType.r_kernel, KernelType.vscode_python]:
        return client.V1Lifecycle(
            post_start=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c",
                    "{}"
                    "{}"
                    "{}".format(
                        create_metering_request(metering_info),
                        create_package_installation(kernel_type,
                                                    pip_packages,
                                                    cran_packages,
                                                    init_script,
                                                    conda_packages,
                                                    lib_path=get_env_value(env, 'nas_package_dir'),
                                                    project_id= g.user["project_id"],
                                                    log_id= get_env_value(env, 'log_id'),
                                                    experiment_name=get_env_value(env, 'EXPERIMENT_NAME')
                                                    ),
                        set_jwt_token_path(env, kernel_type)),
                ])
            ),
            pre_stop=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c",
                    "{}"
                    "{}".format(
                        stop_metering_request(metering_info),
                        delete_resources_onstop(get_env_value(env, 'template_id')))
                ])
            )
        )
    elif kernel_type in [KernelType.rstudio_kernel]:
        return client.V1Lifecycle(
            post_start=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c", "mkdir -p /tmp/rstudio; chmod 777 -R /tmp/rstudio;"
                    "{}"
                    "{}echo MOSAIC_AI_SERVER={} >> /tmp/rstudio/.Renviron;"
                    "echo PROJECT_ID={} >> /tmp/rstudio/.Renviron;"
                    "echo NOTEBOOKS_API_SERVER={} >> /tmp/rstudio/.Renviron;"
                    "echo TZ='Etc/UTC' >> /tmp/rstudio/.Renviron;"
                    "{}".format(
                        create_metering_request(metering_info),
                        env_var_list(env),
                        get_env_value(env, 'MOSAIC_AI_SERVER'),
                        get_env_value(env, 'PROJECT_ID'),
                        get_env_value(env, 'NOTEBOOKS_API_SERVER'),
                        create_package_installation(
                            kernel_type,
                            pip_packages,
                            cran_packages,
                            init_script,
                            conda_packages,
                            lib_path=get_env_value(env, 'R_PACKAGE_DIR'),
                            project_id=g.user["project_id"],
                            log_id=get_env_value(env, 'log_id'),
                            )),
                ])
            ),
            pre_stop=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c",
                    "{}"
                    "{}".format(
                        stop_metering_request(metering_info),
                        delete_resources_onstop(get_env_value(env, 'template_id')))
                ])
            )
        )
    else:
        return client.V1Lifecycle(
            post_start=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c",
                    f"{create_metering_request(metering_info)}"
                    f"{create_umask_command(env, kernel_type)}"

                ])
            ),
            pre_stop=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(command=[
                    "/bin/sh", "-c",
                    "{}"
                    "{}"
                    "{}".format(
                        stop_metering_request(metering_info),
                        delete_resources_onstop(get_env_value(env, 'template_id')),
                        create_sas_prestop_script(env))
                ])
            )
        )


def create_umask_command(env, kernal_type):
    """
    Create umask command for user impersonation
    """
    user_impersonation_flag = get_env_value(env, 'USER_IMPERSONATION')
    if user_impersonation_flag and user_impersonation_flag.lower() == "true" and kernal_type in [KernelType.sas]:
        umask_value = get_env_value(env, "NB_UMASK")
        return f'echo "umask {umask_value}" >> /etc/bashrc; echo "umask {umask_value}" >> /home/.bashrc; ' \
               f'echo "umask {umask_value}" | tee -a /etc/profile.d/*;'
    return ""


@log_decorator
def env_var_list(env):
    """ This returns list of env var to be appended to Renviron File"""
    echo_list = ""
    for item in env:
        echo_list += "echo {}={} >> /tmp/rstudio/.Renviron;".format(
            item.get("name"), item.get("value"))
    return echo_list


@log_decorator
def attach_metadata_lable_to_pod(label):
    """ Method to change labels in metadata of pod """
    labels = {
        "app": label,
        "owner": "ailogistics",
        "catalog": "false",
        "decisions": "false",
        "ailogistics": "false",
        "lens": "false",
        "aiops": "false",
        "agnitio": "false"
    }
    return labels


def create_netrc_file(enabled_repo: dict) -> str:
    """
    Method to create .netrc file in home dir
    :param enabled_repo:
    :return: string
    """
    # we don't need the port number
    host = urllib.parse.urlparse(enabled_repo["repo_url"]).netloc.split(":")[0]
    user = enabled_repo["username"]
    password = enabled_repo["password"]

    return f"machine {host} login {user} password {password}"

def bash_env(kernel_type):

    if kernel_type == KernelType.rstudio_kernel:
        cmd="mkdir -p /tmp/rstudio; chmod 777 -R /tmp/rstudio; cat /notebooks/.env >> /tmp/rstudio/.Renviron;"
        return cmd
    else:
        cmd=f""
        return cmd

@log_decorator
def create_k8_pod(container_name, docker_image_name, port_no, resources,
                  cmd, args, env, repo_name, commit_type, kernel_type, cran_packages,
                  pip_packages, conda_packages, init_script, node_affinity_options,
                  enabled_repo, snapshots, metering_info, git_macros_config,
                  resource_quota_full=None, envs=None, user_imp_data=None, version=None):

    """Method to create a new pod for BYOC"""
    project_id = g.user.get('project_id', metering_info.get('project_id', repo_name))
    if project_id:
        contains_gpu = any('gpu' in key for key in resources['limits'])
        node_affinity = get_affinity_config(project_id, gpu=True) if contains_gpu else get_affinity_config(project_id)
        if node_affinity:
            node_affinity_options = node_affinity

    current_app.logger.debug("inside function create_k8_pod")
    namespace = current_app.config["KUBERNETES_NAMESPACE"]
    # Volume

    volume_git = client.V1Volume(
        name="git", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_shared_code = client.V1Volume(
        name="code", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_tmp = client.V1Volume(
        name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_notebooks = client.V1Volume(
        name="notebooks", empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )
    volume_data = client.V1Volume(
        name=g.user["project_id"], empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )

    volume_log = "log-storage"
    remote_url = create_remote_url(enabled_repo)
    base_folder = enabled_repo['base_folder']
    remote_branch = enabled_repo['branch']
    repo_id=enabled_repo["repo_id"]
    template_id = get_env_value(env, 'template_id')
    nas_location = current_app.config['TEMPLATE_NAS_DIRECTORY']
    base_docker_image_name = get_env_value(env, 'base_docker_image_name')
    if kernel_type in [KernelType.python, KernelType.spark_distributed, KernelType.spark, KernelType.vscode_python]:
        path_list = ['', package_target_path(nas_location, base_docker_image_name, template_id, version), "/tmp/pip_packages"]
        nas_package_dir = package_target_path(nas_location, base_docker_image_name, template_id, version)
        pythonpath_dict = {"name": 'PYTHONPATH', "value": ":".join(path_list)}
        nas_package_dir_dict = {"name": 'nas_package_dir', "value": nas_package_dir}
        env.append(pythonpath_dict)
        env.append(nas_package_dir_dict)

    if kernel_type == KernelType.spark:
        spark_driver_host = {"name": 'spark_driver_host', "value": current_app.config.get('SPARK_DRIVER_HOSTS','127.0.0.1').split(";")[0]}
        driver_nodeport, blockmanager_nodeport = select_nodeports_for_spark()
        spark_driver_port = {"name": 'spark_driver_port', "value": str(driver_nodeport)}
        spark_driver_blockmanager_port = {"name": 'spark_driver_blockmanager_port', "value": str(blockmanager_nodeport)}
        env.extend([spark_driver_host, spark_driver_port, spark_driver_blockmanager_port])
    default_commit_message = "auto save by knights-watch"
    user_commit_message = get_env_value(env, 'knights_watch_commit_message')
    commit_message = user_commit_message if user_commit_message else default_commit_message
    jira_id = get_env_value(env, 'knights_watch_jira_id')
    cull_idle_in_minutes = current_app.config['CULL_IDLE_TIME_MINUTES'] if get_env_value(env, 'cull_idle_in_minutes') is None \
        else get_env_value(env, 'cull_idle_in_minutes')
    init_container = git_init_container(
        repo_name,
        template_id,
        cmd,
        args,
        kernel_type,
        repo_id,
        volume_git,
        volume_shared_code,
        volume_tmp,
        volume_notebooks,
        remote_url,
        base_folder,
        remote_branch,
        volume_data,
        base_docker_image_name,
        snapshots,
        git_macros_config,
        envs
    )

    # create v1resource object
    v1_resource = client.V1ResourceRequirements(
        requests=resources["requests"],
        limits=resources["limits"]
    )

    # load cull config, and set the cpu and memory as per template
    cull_config = json.loads(current_app.config["CULL_CONFIG"])
    cull_config["cpu_cores"] = float(parse_quantity(resources["actual"]["cpu"]))
    cull_config["memory_in_mi"] = float(parse_quantity(resources["actual"]["mem"]) / (1024 * 1024))
    cull_config = json.dumps(cull_config)
    current_app.logger.debug("Cull Config %s %s",container_name, cull_config)

    volume_count_output, volume_mount_output = volumeVolumeMounts(g.user["mosaicId"], g.user["project_id"])

    # check base docker image is sas or other
    if base_docker_image_name and base_docker_image_name.lower() == 'sas':
        volume_cas = client.V1Volume(
            name="cas-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )

        volume_data = client.V1Volume(
            name="data-volume", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )

        knights_watch = client.V1Container(
            name="knights-watch",
            image=current_app.config["KNIGHTS_WATCH_IMAGE_NAME"],
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=4000)],

            env=[{"name": 'FLASK_ENV', "value": 'sas'},
                 {"name": "base_folder", "value": base_folder},
                 {"name": "git_branch", "value": remote_branch},
                 {"name": "template_status_id", "value": metering_info["pod_id"]},
                 {"name": "user_id", "value": g.user["mosaicId"]},
                 {"name": "user_email", "value": g.user["email_address"]},
                 {"name": "metering_url", "value": current_app.config["METERING_BACKEND_URL"]},
                 {"name": "token", "value": get_env_value(env, 'TOKEN')},
                 {"name": "template_id", "value": get_env_value(env, 'template_id')},
                 {"name": "project_id", "value": get_env_value(env, 'PROJECT_ID')},
                 {"name": "commit_message", "value": commit_message},
                 {"name": "knights_watch_uid", "value": envs.get('user_id')},
                 {"name": "cull_config", "value": cull_config},
                 {"name": "notebook_name", "value": envs.get("NOTEBOOK_NAME")},
                 {"name": "jira_id", "value": jira_id},
                 {"name": "project_name", "value": get_env_value(env, 'project_name')}
                 ],

            command=[
                "sh", "-c",
                "cd /notebooks;"
                "python /app/app.py -commit_type {0} -pod_name {1} "
                "-idle_time {2}".format(commit_type,
                                        container_name,
                                        cull_idle_in_minutes)
            ],
            resources=client.V1ResourceRequirements(
                limits=json.loads(current_app.config.get("KNIGHTS_WATCH_CONTAINER_LIMIT", '{"cpu": "200m", "memory": "1Gi"}')),
                requests=json.loads(
                    current_app.config.get("KNIGHTS_WATCH_CONTAINER_REQUEST", '{"cpu": "100m", "memory": "256Mi"}')),
            ),
            volume_mounts=[
                client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
                client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks"),
                client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
                client.V1VolumeMount(name=volume_data.name, mount_path="/data1"),
                client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code")
            ],

        )

        user_impersonation_flag = envs.get("USER_IMPERSONATION")
        user_impersonation = bool(user_impersonation_flag and
                                  user_impersonation_flag.lower() == "true")
        if user_impersonation:
            pod_uid = int(envs.get("user_id"))
            container_security_context = client.V1SecurityContext(run_as_user=pod_uid, run_as_group=pod_uid)
        else:
            container_security_context = {}
        init_container.security_context = container_security_context
        knights_watch.security_context = container_security_context

        volume_mount = [
            client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
            client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks"),
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/data"),
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/permstore"),
            client.V1VolumeMount(name=volume_cas.name, mount_path="/cas/cache"),
            client.V1VolumeMount(name=volume_data.name, mount_path="/data1"),
            client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
            client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code")
        ]
        volume_mount.extend(get_volumes_mount(
            project_id=g.user["project_id"], username=g.user["mosaicId"], snapshots=snapshots,
            git_macros_config=git_macros_config, resource_quota_full=resource_quota_full,
            volume_mount_output= volume_mount_output, log_id=get_env_value(env, 'log_id'), envs=envs))

        # pylint: disable = line-too-long
        container = client.V1Container(
            name="notebooks",
            image=docker_image_name,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=port_no)],
            # command=cmd,
            command=["/bin/bash","-c",
            "bash /notebooks/entrypoint.sh"],
            args=args,
            env=env,
            resources=v1_resource,
            volume_mounts=volume_mount,
            lifecycle=get_lifecycle(kernel_type, pip_packages, conda_packages, cran_packages,
                                    init_script, env, metering_info)
        )

        volumes = [volume_git, volume_notebooks, volume_cas, volume_data, volume_tmp, volume_shared_code]
        volumes.extend(get_volumes(
            project_id=g.user["project_id"]
            , username=g.user["mosaicId"]
            , snapshots=snapshots
            , git_macros_config=git_macros_config
            , volume_count_output=volume_count_output))

        spec = client.V1PodSpec(
            init_containers=[init_container],
            containers=[container, knights_watch],
            volumes=volumes,
            image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
            restart_policy="Never",
            service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
            affinity=client.V1Affinity(
                node_affinity=client.V1NodeAffinity(
                    required_during_scheduling_ignored_during_execution=add_node_affinity_required(
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_KEY"),
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_OPERATOR"),
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_VALUES"),
                    )
                )
            ),
            tolerations=[
                add_tolerations(
                    key=node_affinity_options.get("TOLERATIONS_KEY"),
                    value=node_affinity_options.get("TOLERATIONS_VALUE"),
                    operator=node_affinity_options.get("TOLERATIONS_OPERATOR"),
                    effect=node_affinity_options.get("TOLERATIONS_EFFECT"),
                )
            ]
        )

    else:
        # get pod security context to set in pod spec
        user_impersonation_flag = envs.get("USER_IMPERSONATION")
        user_impersonation = bool(user_impersonation_flag and
                                  user_impersonation_flag.lower() == "true")
        security_context: client.V1PodSecurityContext = get_security_context(user_imp_data, user_impersonation, envs)
        container_security_context = {}
        if kernel_type in [KernelType.rstudio_kernel, KernelType.spark, KernelType.spark_distributed]:
            uid = os.getuid()
            container_security_context = client.V1SecurityContext(run_as_user=uid, run_as_group=uid)
            if envs.get("READ_ONLY_ENV") == "true":
                security_context.run_as_user = security_context.run_as_group = uid
        if kernel_type == KernelType.rstudio_kernel:
            r_package_dir = {"name": 'R_PACKAGE_DIR',
                               "value": package_target_path(nas_location, base_docker_image_name, template_id, version=version)}
            cran_packages_dict = {"name": 'CRAN_PACKAGES',
                               "value": json.dumps(cran_packages)}
            env.append(cran_packages_dict)
            env.append(r_package_dir)
            current_app.logger.debug("base_docker_image_name : %s", base_docker_image_name)
            if get_env_value(env, 'os') == "RHEL":
                image_user_id = {"name": 'USER_ID', "value": 'mosaic-ai'}
                image_user = {"name": 'USER', "value": 'mosaic-ai'}
                env.append(image_user_id)
                env.append(image_user)
        knights_watch = client.V1Container(
            name="knights-watch",
            image=current_app.config["KNIGHTS_WATCH_IMAGE_NAME"],
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=4000)],
            env=[{"name": "base_folder", "value": base_folder},
                 {"name": "git_branch", "value": remote_branch},
                 {"name": "template_status_id", "value": metering_info["pod_id"]},
                 {"name": "user_id", "value": g.user["mosaicId"]},
                 {"name": "user_email", "value": g.user["email_address"]},
                 {"name": "metering_url", "value": current_app.config["METERING_BACKEND_URL"]},
                 {"name": "token", "value": get_env_value(env, 'TOKEN')},
                 {"name": "template_id", "value": get_env_value(env, 'template_id')},
                 {"name": "project_id", "value": get_env_value(env, 'PROJECT_ID')},
                 {"name": "commit_message", "value": commit_message},
                 {"name": "knights_watch_uid", "value": envs.get('user_id')},
                 {"name": "cull_config", "value": cull_config},
                 {"name": "notebook_name", "value": envs.get("NOTEBOOK_NAME")},
                 {"name": "jira_id", "value": jira_id},
                 {"name": "project_name", "value": get_env_value(env, 'project_name')}
                 ],
            command=[
                "sh", "-c",
                "cd /notebooks;"
                "python /app/app.py -commit_type {0} -pod_name {1} "
                "-idle_time {2}".format(commit_type,
                                        container_name,
                                        cull_idle_in_minutes)
            ],
            resources=client.V1ResourceRequirements(
                limits=json.loads(current_app.config.get("KNIGHTS_WATCH_CONTAINER_LIMIT", '{"cpu": "200m", "memory": "1Gi"}')),
                requests=json.loads(current_app.config.get("KNIGHTS_WATCH_CONTAINER_REQUEST", '{"cpu": "100m", "memory": "256Mi"}')),
            ),
            volume_mounts=[
                client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
                client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
                client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks"),
                client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code")
            ]
        )
        notebooks_volumes_mount = [
            client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
            client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
            client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks"),
            client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code"),
            client.V1VolumeMount(name=volume_log, mount_path=current_app.config["LOG_DIRECTORY"])
            ]
        notebooks_volumes_mount.extend(get_volumes_mount(project_id=g.user["project_id"]
                                                         , username=g.user["mosaicId"]
                                                         , snapshots=snapshots
                                                         , git_macros_config=git_macros_config
                                                         , resource_quota_full=resource_quota_full
                                                         , volume_mount_output=volume_mount_output
                                                         , log_id=get_env_value(env, 'log_id'), envs=envs))
        notebook_volume = [volume_git, volume_tmp, volume_notebooks, volume_shared_code]
        notebook_volume.extend(get_volumes(
            project_id=g.user["project_id"]
            , username=g.user["mosaicId"]
            , snapshots=snapshots
            , git_macros_config=git_macros_config, volume_count_output=volume_count_output))

        env.append({"name": 'pvc_name', "value": current_app.config["SHARED_PVC"]})

        container = client.V1Container(
            name="notebooks",
            image=docker_image_name,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=port_no)] if kernel_type != KernelType.spark_distributed else [client.V1ContainerPort(container_port=port_no), client.V1ContainerPort(container_port=7777, name="blockmanager"), client.V1ContainerPort(container_port=2222, name="driver")],
            command=["/bin/bash","-c",
            "{}"
            "bash /notebooks/entrypoint.sh".format(bash_env(kernel_type))],
            args=None,
            env=env,
            resources=v1_resource,
            volume_mounts=notebooks_volumes_mount,
            lifecycle=get_lifecycle(kernel_type, pip_packages, conda_packages, cran_packages,
                                    init_script, env, metering_info),
            security_context=container_security_context
        )

        spec = client.V1PodSpec(
            init_containers=[init_container],
            containers=[container, knights_watch],
            volumes=notebook_volume,
            image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
            restart_policy="Never",
            service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'] if kernel_type != KernelType.spark_distributed else current_app.config['SERVICE_ACCOUNT_NAME_SPARK_DIST_TEMP'],
            affinity=client.V1Affinity(
                node_affinity=client.V1NodeAffinity(
                    required_during_scheduling_ignored_during_execution=add_node_affinity_required(
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_KEY"),
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_OPERATOR"),
                        node_affinity_options.get("NODE_AFFINITY_REQUIRED_VALUES"),
                    )
                )
            ),
            tolerations=[
                add_tolerations(
                    key=node_affinity_options.get("TOLERATIONS_KEY"),
                    value=node_affinity_options.get("TOLERATIONS_VALUE"),
                    operator=node_affinity_options.get("TOLERATIONS_OPERATOR"),
                    effect=node_affinity_options.get("TOLERATIONS_EFFECT"),
                )
            ],
            security_context=security_context,
            host_aliases=get_hostalias()
        )

    pod = client.V1Pod(
        kind="Pod", metadata=client.V1ObjectMeta(
            name=container_name,
            labels=attach_metadata_lable_to_pod(container_name)),
        spec=spec
    )
    api = client.CoreV1Api()
    current_app.logger.debug(f"create_k8_pod POD: {pod}")
    api.create_namespaced_pod(body=pod, namespace=namespace)
    current_app.logger.debug("End of function create_k8_pod")


def get_hostalias():
    """
    Get host alias from config for ADS connectivity
    """
    ads_config = current_app.config.get("ADS_CONFIG", [])
    host_aliases = []
    if ads_config:
        ads_config = json.loads(ads_config)
        for config in ads_config["hostAliases"]:
            ip = config.get("ip")
            hostnames = config.get("hostnames")
            host_alias: client.V1HostAlias = client.V1HostAlias(ip=ip, hostnames=hostnames)
            host_aliases.append(host_alias)
    return host_aliases


@log_decorator
def create_ingress_byoc(namespace, default_host, container_name, ingress_url, ingress_auth_url,
                        ingress_auth_fail_url, ingress_auth_snippet):
    """ function to create ingress for byoc pod """
    ingress_yaml = load_template(DeploymentSidecarNames().get_default_ingress_template())
    if current_app.config["INGRESS_CONTROLLER"] == 'alb':
        current_app.logger.info(ingress_yaml)
        current_app.logger.info(current_app.config["INGRESS_CONTROLLER"])
        current_app.logger.info(namespace)
        ingress_yaml = ingress_yaml.format(
            ingress_class=current_app.config["INGRESS_CONTROLLER"],
            pathType=current_app.config.get("INGRESS_PATHTYPE", "Prefix"),
            namespace=namespace,
            container_name=container_name,
            ingress_url=ingress_url,
            group_order=find_unique_ingress_order(),
            listen_ports=current_app.config["ALB_LISTEN_PORTS"],
            alb_group_name=current_app.config["ALB_GROUP_NAME"],
            alb_inbound_cidrs=current_app.config["ALB_INBOUND_CIDRS"],
            alb_scheme=current_app.config["ALB_SCHEME"],
            alb_target_type=current_app.config["ALB_TARGET_TYPE"],
        )
    else:
        ingress_yaml = ingress_yaml.format(
            ingress_class=current_app.config["INGRESS_CONTROLLER"],
            pathType=current_app.config.get("INGRESS_PATHTYPE", "Prefix"),
            namespace=namespace,
            default_host=default_host,
            container_name=container_name,
            ingress_url=ingress_url,
            ingress_auth_url=ingress_auth_url,
            ingress_auth_fail_url=ingress_auth_fail_url,
            ingress_auth_snippet=ingress_auth_snippet
        )
    ingress_manifest = yaml.safe_load(ingress_yaml)
    current_app.logger.debug(ingress_manifest)
    # create ingress
    k8s_network = client.NetworkingV1Api()
    try:
        k8s_network.create_namespaced_ingress(body=ingress_manifest, namespace=namespace)
        current_app.logger.debug(
            "byoc ingress created for pod_name: {}".format(container_name)
        )
    # pylint: disable=broad-except
    except Exception as e:
        if e.reason != "Conflict":
            current_app.logger.error(e)
            current_app.logger.error("failed to create byoc ing "
                                     "for pod_name: {}".format(container_name))
            raise e

@log_decorator
def create_endpoints_byoc(container_name, pods_internal_ip, namespace, port_no):
    """ function to create endpoints for byoc pod """
    api = client.CoreV1Api()
    # load default endpoints template
    endpoints_yaml = load_template(DeploymentSidecarNames().get_default_endpoint_template())

    endpoints_yaml = endpoints_yaml.format(
        pods_internal_ip=pods_internal_ip,
        namespace=namespace,
        container_name=container_name,
        port_no=port_no
    )
    endpoints_manifest = yaml.safe_load(endpoints_yaml)
    current_app.logger.debug(endpoints_manifest)
    # create endpoints
    try:
        api.create_namespaced_endpoints(body=endpoints_manifest, namespace=namespace)
        current_app.logger.debug(
            "byoc endpoint created for pod_name: '{0}'".format(container_name)
        )
    # pylint: disable=broad-except
    except Exception as ex:
        if ex.reason != "Conflict":
            current_app.logger.error(ex.reason)
            current_app.logger.error(ex)
            current_app.logger.error(
                "unable to create byoc endpoint for pod_name: '{0}'".format(container_name)
            )


@log_decorator
def create_service_byoc(container_name, pods_internal_ip, namespace, port_no, kernel_type=None):
    """ function to create service for byoc pod """
    api = client.CoreV1Api()
    # load default endpoints template
    if kernel_type == KernelType.spark_distributed:
        if current_app.config["INGRESS_CONTROLLER"] == 'alb':
            service_yaml = load_template("manifests/byoc/spark_distributed_service_alb.yaml")
        else:
            service_yaml = load_template("manifests/byoc/spark_distributed_service.yaml")
    else:
        service_yaml = load_template(DeploymentSidecarNames().get_default_service_template())
    if current_app.config["INGRESS_CONTROLLER"] == 'alb':
        service_yaml = service_yaml.format(
            pods_internal_ip=pods_internal_ip,
            namespace=namespace,
            container_name=container_name,
            port_no=port_no,
            service_type=current_app.config["SERVICE_TYPE"])
    else:
        service_yaml = service_yaml.format(
            pods_internal_ip=pods_internal_ip,
            namespace=namespace,
            container_name=container_name,
            port_no=port_no)
    service_manifest = yaml.safe_load(service_yaml)
    current_app.logger.debug(service_manifest)
    # if spark template create nodeport service
    if kernel_type == KernelType.spark:
        nodeport_service_yaml = load_template("manifests/byoc/spark_nodeport_service.yaml")
        driver_nodeport = retrieve_env_for_spark(container_name, 'spark_driver_port')
        blockmanager_nodeport = retrieve_env_for_spark(container_name, 'spark_driver_blockmanager_port')
        nodeport_service_yaml = nodeport_service_yaml.format(
            pods_internal_ip=pods_internal_ip,
            namespace=namespace,
            service_name=container_name[:40]+"nodeport",
            container_name=container_name,
            blockmanager_nodeport=int(blockmanager_nodeport),
            driver_nodeport=int(driver_nodeport),
            service_type=current_app.config["SERVICE_TYPE"]
        )
        nodeport_service_manifest = yaml.safe_load(nodeport_service_yaml)
        # create nodeport service for spark
        try:
            api.create_namespaced_service(body=nodeport_service_manifest, namespace=namespace)
            current_app.logger.debug(
                "byoc nodeport service created for pod_name: '{0}'".format(container_name)
                )
    # pylint: disable=broad-except
        except Exception as ex:
            if ex.reason != "Conflict" and "port is already allocated" not in str(ex):
                current_app.logger.error(ex)
                current_app.logger.error(
                    "unable to create nodepoprt service for pod_name: '{0}'".format(container_name)
                )
                raise ex


    # create service
    try:
        api.create_namespaced_service(body=service_manifest, namespace=namespace)
        current_app.logger.debug(
            "byoc service created for pod_name: '{0}'".format(container_name)
        )
    # pylint: disable=broad-except
    except Exception as ex:
        if ex.reason != "Conflict":
            current_app.logger.error(ex)
            current_app.logger.error(
                "unable to create service for pod_name: '{0}'".format(container_name)
            )
            raise ex


@log_decorator
def create_endpoint_svc_ing_byoc(container_name, pods_internal_ip, port_no, ingress_url,
                                 namespace, default_host, ingress_auth_url, ingress_auth_fail_url,
                                 ingress_auth_snippet, kernel_type=None):
    """Method to create svc, ing, endpoints for BYOC"""
    try:
        print("ingress creation in progress")
        current_app.logger.debug("inside function create_endpoint_svc_ing_byoc")

        create_endpoints_byoc(container_name, pods_internal_ip, namespace, port_no)
        create_service_byoc(container_name, pods_internal_ip, namespace, port_no, kernel_type)
        create_ingress_byoc(namespace, default_host, container_name, ingress_url,
                            ingress_auth_url, ingress_auth_fail_url, ingress_auth_snippet)
        current_app.logger.debug("end of function create_endpoint_svc_ing_byoc")
        print("ingress creation completed")
    except Exception as e:
        print("exception occured while createing ingress ", e)
        raise e


@log_decorator
def delete_k8_pod(pod_name, namespace):
    """Method to Delete pod"""
    api = client.CoreV1Api()
    api.delete_namespaced_pod(name=pod_name, namespace=namespace)


@log_decorator
def fetch_git_url(git_repo):
    """ git repo associated with the project """
    username = current_app.config["GIT_USERNAME"]
    password = replace_special_chars_with_ascii(str(current_app.config["GIT_ACCESS_TOKEN"]))
    url = "{0}/{1}.git".format(current_app.config["GIT_URL"], git_repo)
    url_parts = url.split("//")
    remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])
    return remote_url


def get_distinct_values_by_key(_list: List, key: str) -> List:
    """
    Function to return unique values of a key in list
    :param _list: [{"output_folder":"shared_data","url":""},{"output_folder":"shared_2","url":""}]
    :param key: output_folder
    :return: {"shared_data","shared_2"}
    """
    return sorted({obj[key] for obj in _list})

def create_run_cmd(temp_cmd,temp_arg):
    run_command = ""
    run_command = temp_cmd[0]
    for arg in temp_arg:
        run_command = run_command + " " + arg
    current_app.logger.info(
            "run command: {}".format(run_command)
        )
    return run_command

@log_decorator
def git_init_container(git_repo,template_id,temp_cmd,temp_arg,kernel_type,repo_id, volume_git, volume_shared_code,volume_tmp, volume_notebooks,
                       remote_url, base_folder, remote_branch, volume_data, base_docker_image_name,
                       snapshots=None, git_macros_config=None, envs=None):
    """Get init container object"""
    current_app.logger.debug("inside git_init_container")
    volume_mounts = [
        client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
        client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks"),
        client.V1VolumeMount(name=volume_data.name, mount_path="/data",
                             sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                      f'/{volume_data.name}/{volume_data.name}-Data'),
        client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code"),
    ]
    if snapshots:
        volume_mounts.append(client.V1VolumeMount(name=volume_data.name, mount_path="/output",
                                                  sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                                           f'/{volume_data.name}'
                                                           f'/{volume_data.name}-Snapshot'
                                                           f'/{snapshots["output"]}'))
        volume_mounts.append(client.V1VolumeMount(name=volume_data.name, mount_path="/input",
                                                  sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                                                           f'/{volume_data.name}'
                                                           f'/{volume_data.name}-Snapshot'
                                                           f'/{snapshots["input"]}'))

    if git_macros_config:
        volume_mounts.append(client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"))

        output_dirs = get_distinct_values_by_key(git_macros_config, "output")
        for idx, dir_name in enumerate(output_dirs):
            volume_mounts.append(client.V1VolumeMount(name=f"vol-{idx}", mount_path=f"/{dir_name}"))

    git_macro_command = create_git_macro_command(git_macros_config)
    if base_folder not in [None, ""]:
        base = base_folder.replace(" ", "\\ ")
        base_folder = f"/{base}/*"
    else:
        base_folder = "/*"

    username = 'sasdemo'
    commit_message = " gitattributes added"
    if envs:
        if envs.get('USER_IMPERSONATION') == "true":
            username = envs.get('user_name')
        if envs.get("knights_watch_commit_message"):
            commit_message = envs.get("knights_watch_commit_message") + commit_message
    run_command=''
    if temp_cmd!=None and temp_arg!=None:
        run_command = create_run_cmd(temp_cmd,temp_arg)
    init_container = client.V1Container(
        name="git-init",
        image=current_app.config["GIT_INIT_IMAGE"],
        image_pull_policy="IfNotPresent",
        command=[
            "sh", "-c",
            "python script.py;"
            "cp -r /shared_code/* /code/ ;"
            "cd /git; "
            "if [ -d /notebooks/notebooks/ ]; then echo 'folder notebooks already present'; "
            "else echo 'notebooks folder doesnt exist, copying'; "
            "mkdir -p /notebooks/notebooks/ && cp -r /git{2} /notebooks/notebooks/; fi;"
            "git config core.filemode false;"
            "git config user.name {3}; "
            "git config user.email {4}; "
            "git config push.default current; "
            "if [ ! -f .gitattributes ]; then echo 'gitattributes is not present'; "
            "touch .gitattributes; echo '*.ipynb diff=nb2md' > .gitattributes;"
            "git add .gitattributes; git commit -m '{7}'; git fetch origin; "
            "git rebase origin/{1};"
            "git push origin {1} -f;"
            "else echo 'gitattributes already present'; fi;"
            "git config diff.nb2md.textconv 'jupyter nbconvert "
            "--ClearOutputPreprocessor.enabled=True --to markdown --stdout --log-level=0 \"$1\"';"
            "chmod 777 -R /notebooks/notebooks;"
            "if [[ '{5}' == 'SAS' ]]; then echo 'its sas container';"
            "cd /notebooks/notebooks/;"
            "touch authinfo.txt; echo 'default user {6} password {6}' > authinfo.txt; cd -;"
            "else echo 'not sas container, skipping password generation'; fi;"
            f'{git_macro_command};'.format(remote_url,
                                           remote_branch,
                                           base_folder,
                                           g.user["first_name"],
                                           g.user["email_address"],
                                           base_docker_image_name,
                                           username,
                                           commit_message
                                           )
        ],
        env=[client.V1EnvVar(name="user_name", value=g.user["mosaicId"]),
        client.V1EnvVar(name="PROJECT_ID", value=g.user["project_id"]),
        client.V1EnvVar(name="repo_id", value=repo_id),
        client.V1EnvVar(name="template_id", value=template_id),
        client.V1EnvVar(name="first_name", value=g.user["first_name"]),
        client.V1EnvVar(name="email_address", value=g.user["email_address"]),
        client.V1EnvVar(name="mode", value="LAUNCH"),
        client.V1EnvVar(name="jupyter_run_cmd", value=run_command),
        client.V1EnvVar(name="kernel_type", value=kernel_type)],
        volume_mounts=volume_mounts,
        resources=client.V1ResourceRequirements(
            limits=json.loads(current_app.config["GIT_INIT_CONTAINER_LIMIT"]),
            requests=json.loads(current_app.config["GIT_INIT_CONTAINER_REQUEST"]),
        ),
    )
    return init_container


@log_decorator
def pod_already_spawnned(name, namespace):
    """ function to check k8 resources already created"""
    k8s_network = client.NetworkingV1Api()

    api = client.CoreV1Api()
    try:
        k8s_network.read_namespaced_ingress(name=name, namespace=namespace)
        api.read_namespaced_service(name=name, namespace=namespace)
        api.read_namespaced_endpoints(name=name, namespace=namespace)
        current_app.logger.debug("all k8 resources already created for pod name: {0}".format(name))
        return True
    # pylint: disable=broad-except
    except Exception:
        current_app.logger.debug("Not all k8 resources created for pod name: {0}".format(name))
        return False


def handle_resource_allocation_event(event, stage, container_event):
    """Method to analyse progress and status of first stage-Allocating resource"""
    if container_event > 0:
        stage['1'] = "success"
    else:
        stage['1'] = "loading"

def handle_event(event, pod, stage, field_path):
    """Method to analyze progress and status of different stages"""
    success_flags = [False] * 4
    if 'knights-watch' in field_path:
        container_statuses = pod.status.container_statuses
        container_name = 'knights-watch'
        stage_key = '4'
    elif 'git-init' in field_path:
        container_statuses = pod.status.init_container_statuses
        container_name = 'git-init'
        stage_key = '2'
    elif 'notebooks' in field_path:
        container_statuses = pod.status.container_statuses
        container_name = 'notebooks'
        stage_key = '3'
    else:
        return
    if container_statuses is not None:
        for container in container_statuses:
            if container.name == container_name:
                if container.ready:
                    stage[stage_key] = "success"
                    success_flags[int(stage_key)-1] = True

    if not success_flags[int(stage_key)-1]:
        if event["object"].reason == 'Failed':
            stage[stage_key] = "failed"
        else:
            stage[stage_key] = "loading"



@log_decorator
def get_pod_progress(pod_name, port_no, ingress_url, kernel_type=None, call_instance=1):
    """Method to return pod ip progress"""
    try:
        current_app.logger.debug("inside function get_pod_progress")
        api = client.CoreV1Api()
        namespace = DeploymentTemplateNames().get_default_namespace()
        resp = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        phase = resp.to_dict().get('status').get('phase')
        #pod_condition_list has boolean values:'PodScheduled', 'ContainersReady', 'Initialized', 'Ready'
        pod_condition_list = []
        for pod_condition in resp.to_dict().get('status').get('conditions'):
            pod_condition_list.append(pod_condition['status'])
            current_app.logger.info("Info: {type} : {status}".format(type=pod_condition['type'],
                                                                     status=pod_condition['status']))
        #For defining the current status of each stage
        stage = {
            '1': 'waiting',
            '2': 'waiting',
            '3': 'waiting',
            '4': 'waiting'
        }
        if phase == "Running" and pod_already_spawnned(pod_name, namespace):
            progress = ""
            stage = {
                '1': 'success',
                '2': 'success',
                '3': 'success',
                '4': 'success'
            }
            stage_success_count = list(stage.values()).count('success')
            progress_perc_stage = 25 * stage_success_count
            data = {"message": progress, "progress": progress_perc_stage, "stage": stage}
            return data

        pod_internal_ip = resp.to_dict().get('status').get('pod_ip')
        default_host = current_app.config["DEFAULT_HOST"]
        notebook_api_url = current_app.config["NOTEBOOKS_API_SERVER_URL"]
        ingress_auth_fail_url = current_app.config["INGRESS_AUTH_ERROR_PAGE"]
        ingress_auth_api = "/v1/ingress-auth/"
        ingress_auth_url = (notebook_api_url + ingress_auth_api + pod_name + "/" + hashlib.md5(str(g.user["mosaicId"]).encode("utf-8")).hexdigest())
        ingress_auth_snippet = current_app.config["INGRESS_AUTH_SNIPPET"]
        create_endpoint_svc_ing_byoc(pod_name, pod_internal_ip, port_no,
                                     ingress_url, namespace, default_host,
                                     ingress_auth_url, ingress_auth_fail_url,
                                     ingress_auth_snippet, kernel_type)
        template_id = "-".join(pod_name.split("-")[1:6])
        create_k8_resources(pod_name, template_id, kernel_type)

        field_selector = "involvedObject.name=" + pod_name
        stream = watch.Watch().stream(api.list_namespaced_event,
                                      namespace=namespace,
                                      field_selector=field_selector,
                                      timeout_seconds=1)

        progress = ""
        event_list = []
        #Defines no of events that are associated with a container
        container_event = 0
        for event in stream:
            if event["object"].event_time is None:
                progress = event["object"].type + " " + event["object"].message
            else:
                progress = date_time.strftime(event["object"].event_time, "%Y-%m-%d %H:%M:%S") \
                           + " " + event["object"].type + " " + event["object"].message
            if event not in event_list:
                event_list.append(progress)

            #Selects the container associated with the current event
            field_path = event["object"].involved_object.field_path
            if field_path is not None:
                container_event += 1
                if container_event == 1:
                    handle_resource_allocation_event(event, stage, container_event)
                handle_event(event, resp, stage, field_path)
            if container_event == 0:
                handle_resource_allocation_event(event, stage, container_event)

        stage_success_count = list(stage.values()).count('success')
        progress_perc_stage = 25 * stage_success_count
        if call_instance == 0:
            data = {"message": event_list, "progress": progress_perc_stage, "stage": stage}
        else:
            data = {"message": progress, "progress": progress_perc_stage, "stage": stage}
        return data
    except Exception as e:
        raise e


@log_decorator
def delete_k8_resources_byoc(pod_name):
    """Deletes kubernetes resources"""
    current_app.logger.debug("kubespawner : start of delete_k8_resources_byoc")
    delete_successful = True
    namespace = DeploymentTemplateNames().get_default_namespace()
    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_endpoints(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Endpoint deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)

    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_service(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Service deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)

    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_service(
            name=pod_name[:40]+'nodeport',
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Nodeport Service deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)

    try:
        k8s_network = client.NetworkingV1Api()
        api_response = k8s_network.delete_namespaced_ingress(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Ingress deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)
    try:
        k8_api = client.CoreV1Api()
        api_response = k8_api.delete_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Pod deleted. status='%s' " % str(api_response.status))
    # pylint: disable=broad-except
    except client.rest.ApiException as ex:
        # raise exception
        delete_successful = bool(ex.reason == "Not Found")
        current_app.logger.exception(ex)

    current_app.logger.debug("kubespawner : end of delete_k8_resources_byoc")
    return delete_successful


@log_decorator
def get_volumes(project_id=None, username=None, snapshots=None, git_macros_config=None, volume_count_output=None):
    """
    This function is used to return kubernetes volume object of register pv claims
    :param project_id:
    :param username:
    :return:
    """
    # pylint: disable=too-many-function-args
    if volume_count_output:
        volumes = volume_count_output
    else:
        volumes = volume_count(project_id, username, project_manager_base_url=current_app.config["CONSOLE_BACKEND_URL"])
    volumes.extend(volume_custom(project_id, current_app.config["SHARED_PVC"]))
    volumes.extend(volume_custom("log-storage", "fluentd-pvc"))

    kubernetes_volumes = []

    if git_macros_config:
        output_dirs = get_distinct_values_by_key(git_macros_config, "output")
        for idx, _ in enumerate(output_dirs):
            kubernetes_volumes.append(client.V1Volume(
                name=f"vol-{idx}", empty_dir=client.V1EmptyDirVolumeSource(medium="")
            ))

    for volume in volumes:
        data_volume = client.V1Volume(
            name=volume.get("name"),
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=volume.get("persistentVolumeClaim").get("claimName")))
        kubernetes_volumes.append(data_volume)
    return kubernetes_volumes


@log_decorator
def get_volumes_mount(project_id=None, username=None, snapshots=None, git_macros_config=None,
                      resource_quota_full=None, volume_mount_output=None, log_id=None,
                      custom_plugin=None, envs=None):
    """
    This function is used to return the kubernetes
    volume mount object from register pvc for specific project
    :param snapshots:
    :param git_macros_config:
    :param project_id:
    :param username:
    :param resource_quota_full:
    :param volume_mount_output:
    :param log_id:
    :param custom_plugin:
    :param envs:
    :return
    """
    k8_volume_mounts = []
    if volume_mount_output:
        volume_mount= volume_mount_output
    else:
        volume_mount = volume_mount_count(project_id, username, project_manager_base_url=current_app.config['CONSOLE_BACKEND_URL'])
    volume_mount.extend(volume_custom_mount(project_id,
                                            current_app.config["MINIO_DATA_BUCKET"],
                                            resource_quota_full))
    if snapshots:
        volume_mount.append(attach_snapshot_volume_mount
                            (project_id, "input",
                             snapshots["input"], current_app.config["MINIO_DATA_BUCKET"]))
        volume_mount.append(attach_snapshot_volume_mount
                            (project_id, "output", snapshots["output"],
                             current_app.config["MINIO_DATA_BUCKET"], resource_quota_full))

    if log_id:
        volume_mount.extend(log_volume_mount(project_id, log_id, current_app.config["MINIO_DATA_BUCKET"],
                                         resource_quota_full))

    if custom_plugin:
        volume_mount.extend(custom_plugin_mount(project_id, current_app.config["MINIO_DATA_BUCKET"], resource_quota_full, envs))

    if envs and envs.get("EXPERIMENT_NAME"):
        current_app.logger.info("Adding experiment volume mount")
        volume_mount.extend(experiment_mount(project_id, current_app.config["MINIO_DATA_BUCKET"], resource_quota_full))

    if git_macros_config:
        output_dirs = get_distinct_values_by_key(git_macros_config, "output")
        for idx, dir_name in enumerate(output_dirs):
            volume_mount.append({"name": f"vol-{idx}", "mountPath": f"/{dir_name}"})

    for volume_mount in volume_mount:
        k8_volume_mounts.append(client.V1VolumeMount(name=volume_mount.get("name"),
                                                     sub_path=volume_mount.get("subPath"),
                                                     mount_path=volume_mount.get("mountPath"),
                                                     read_only=bool(volume_mount.get("readOnly"))))
    return k8_volume_mounts


def set_jwt_token_path(env, kernal_type):
    """
    Create token path for user impersonation
    """
    user_impersonation_flag = get_env_value(env, 'USER_IMPERSONATION')
    token = get_env_value(env, 'TOKEN')
    if user_impersonation_flag and user_impersonation_flag.lower() == "true" \
            and kernal_type in [KernelType.python,
                                KernelType.r_kernel]:
        user_name = get_env_value(env, 'user_name')
        return f"echo {token} > /home/{user_name}/.mosaic.ai || true;"
    return f"echo {token} > /home/mosaic-ai/.mosaic.ai || true;"


def job_lifecyclehooks(jwt, metering_info, set_token_command, automl_info=None):
    """
    Job lifecycle function for jobs
    """
    command = [
        "/bin/sh",
        "-c",
        "{}"
        "{}".format(set_token_command, create_metering_request(metering_info))]
    # check if it's an automl job

    if automl_info and automl_info.get('experiment_recipe_id'):
        command[2] += "{};".format(update_automl_recipe(jwt, automl_info, 'running'))
    lifecycle_hooks = client.V1Lifecycle(
        post_start=client.V1LifecycleHandler(
            _exec=client.V1ExecAction(
                command=command
                )
            )
        )
    return lifecycle_hooks


@log_decorator
def update_automl_recipe(jwt, automl_info, job_status):
    """Method to update automl recipe command"""
    update_status_url = (
        current_app.config["AUTOML_BACKEND_URL"] + \
        Automl.update_recipe_status.format(experiment_recipe_id=automl_info['experiment_recipe_id'])
    )
    current_app.logger.debug(update_status_url)
    # pylint: disable = line-too-long
    update_recipe_command = "curl -X PUT \"{0}\" -H \"accept: application/json\" -H \"Authorization: Token {1} \" -H \"X-project-id:{2}\" -H \"Content-Type: application/json\" -d \'{{\"job_status\": \"{3}\"}}\'".format(
        update_status_url,
        jwt,
        automl_info['PROJECT_ID'],
        job_status)
    current_app.logger.debug(update_recipe_command)
    return update_recipe_command


@log_decorator
def update_command_var(cmd,
                       jwt,
                       execution_command,
                       metering_info,
                       automl_info,
                       terminate_now,
                       user_impersonation,
                       kernel_type
                       ):
    """update command if automl job"""
    if automl_info['experiment_recipe_id']:
        # pylint: disable = line-too-long
        terminate_now = "if [ -z ${{Terminate+x}} ];" \
                        "then {0}; \n"\
                        "else {1}; \n exit 1; fi; \n".format(
                            update_automl_recipe(jwt, automl_info, job_status='completed'),
                            update_automl_recipe(jwt, automl_info, job_status='failed'),
                            )

    command = "sh /notebooks/notebooks/requirements.sh; \n {0} \n {1} \n" \
              "{2} || ({2} && echo \"metering error\" && exit 1); \n" \
              "{3} \n" \
              "exit 0;".format(cmd, execution_command,
                               stop_metering_request(metering_info), terminate_now)

    # Add any command that needs to be run before executing file in job
    pre_run_command = get_job_pre_run_command(kernel_type)

    # Execute job command as user in case of user impersonation in sas template
    if kernel_type in [KernelType.sas] and user_impersonation:
        command = f"sudo -E su $user_name -c \'{command}\'"

    command_var = [
        "/bin/bash",
        "-c",
        f"{pre_run_command} "
        f"{command}"
    ]
    current_app.logger.debug(command_var)
    return command_var


def get_job_pre_run_command(kernel_type):
    """
    Get command to be run before job command
    """
    if kernel_type in [KernelType.sas]:
        pre_run_command = f'sudo chmod -R 777 /notebooks; \n' \
                          f'sudo chmod -R 777 /data; \n' \
                          f'sudo chmod -R 777 /input; \n'\
                          f'sudo chmod -R 777 /output; \n' \
                          f'sudo -E su root -c "nohup /usr/local/bin/tini -- ' \
                          f'/sas_workdir/run_entrypoint.sh & \n' \
                          f'sleep 120"; \n'

    elif kernel_type in [KernelType.r_kernel, KernelType.rstudio_kernel]:
        pre_run_command = "{} source /notebooks/.bashrc;".format(bash_env(kernel_type))
    else:
        pre_run_command = "source /notebooks/.bashrc;"
    return pre_run_command


def find_unique_ingress_order():
    """ This returns unique ingress group number between 500 to 1000 range
        which is not already used in already created ingress
    """
    already_used_ingress_group_order = find_already_used_ingress_group_order()
    ingress_start = current_app.config['INGRESS_START_RANGE']
    ingress_end = current_app.config['INGRESS_END_RANGE']
    unique_ingress_order = random.sample(range(ingress_start, ingress_end), 1)
    if already_used_ingress_group_order and already_used_ingress_group_order == unique_ingress_order:
        return find_unique_ingress_order()
    else:
        return unique_ingress_order[0]


def find_already_used_ingress_group_order():
    k8s_network = client.NetworkingV1Api()
    namespace = DeploymentTemplateNames().get_default_namespace()
    all_ingress = k8s_network.list_namespaced_ingress(namespace=namespace,
                                                   label_selector='ingress_group=template')
    allocated_group_order_numbers = []
    for ing in all_ingress.items:
        allocated_group_order_numbers.append(ing._metadata.annotations.get('alb.ingress.kubernetes.io/group.order'))
    return allocated_group_order_numbers


# @retry(tries=_config.get("RETRY_COUNT", 5), delay=_config.get("RETRY_DELAY", 5))
def retry_create_namespaced_job(namespace, pod_body):
    """
    retry_create_namespaced_job with retry decorator
    :param namespace: k8 namespace where job need to create
    :param pod_body:  pod specification

    retry has below options:
    :param exceptions: an exception or a tuple of exceptions to catch. default: Exception.
    :param tries: the maximum number of attempts. default: -1 (infinite).
    :param delay: initial delay between attempts. default: 0.
    :param max_delay: the maximum value of delay. default: None (no limit).
    :param backoff: multiplier applied to delay between attempts. default: 1 (no backoff).
    :param jitter: extra seconds added to delay between attempts. default: 0.
                   fixed if a number, random if a range tuple (min, max)
    :param logger: logger.warning(fmt, error, delay) will be called on failed attempts.
                   default: retry.logging_logger. if None, logging is disabled
    """
    try:
        api_response = extension.create_namespaced_job(namespace, body=pod_body)
        # pylint: disable=logging-not-lazy
        current_app.logger.debug("Job creation API, status='%s' " % str(api_response.status))
    except Exception as e:
        current_app.logger.error("Exception when calling BatchV1Api->create_namespaced_job: "
                                 "%s\n" % e)
        current_app.logger.error("Retrying retry_create_namespaced_job function")
        raise


def create_sas_prestop_script(env):
    """
    Create preStop hook command to delete sas tmp work directory
    """
    sas_tmp_dir = get_env_value(env, "SAS_WORDIR")
    if sas_tmp_dir:
        return f"/etc/init.d/sas-viya-all-services stop; rm -Rf {sas_tmp_dir};"


def volumeVolumeMounts(username, project_id):
    url = f"{current_app.config['CONSOLE_BACKEND_URL']}/secured/api/pvc/project/{project_id}"
    url2 = f"{current_app.config['CONSOLE_BACKEND_URL']}/secured/api/pvc/project/all"
    volume_count_output = []
    volume_mount_count_output = []
    headers = {"X-Auth-Username": username}

    for item in [url, url2]:
        response = requests.get(item, headers=headers)
        response = response.json()
        if response:
            for x in range(len(response)):
                desc = {
                    "name": response[x]["pvcName"],
                    "persistentVolumeClaim": {"claimName": response[x]["pvcName"]},
                }
                volume_count_output.append(desc)

            for x in range(len(response)):
                desc = {
                    "name": response[x]["pvcName"],
                    "mountPath": response[x]["mountpath"],
                }
                volume_mount_count_output.append(desc)
    return volume_count_output, volume_mount_count_output


def log_volume_mount(project_id, log_id, minio_bucket=None, resource_quota_full=None):
    volume = []
    desc = {
        "name": project_id,
        "mountPath": f"/log/{project_id}/{log_id}",
        "subPath": f"{minio_bucket}/log/{project_id}/{log_id}"
    }
    if resource_quota_full:
        desc["readOnly"] = True
    volume.append(desc)
    return volume


def custom_plugin_mount(project_id, minio_bucket, resource_quota_full, envs):
    """
    This function is used to return the kubernetes volume mount params
    :param project_id:
    :param minio_bucket:
    :param resource_quota_full:
    :param envs:
    :return dict:
    """
    volumes = []
    # custom plugin recipe mount
    cp_recipe = {
        "name": project_id,
        "mountPath": "/custom_plugin",
        "subPath": f"{minio_bucket}/custom_plugin/"
    }
    if resource_quota_full:
        cp_recipe["readOnly"] = True
    volumes.append(cp_recipe)

    # custom plugin snapshot mount
    cp_snapshot = {
        "name": project_id,
        "mountPath": "/snapshot",
        "subPath": f"{minio_bucket}/{project_id}/{project_id}-Snapshot"
    }
    if resource_quota_full:
        cp_snapshot["readOnly"] = True
    volumes.append(cp_snapshot)

    # custom plugin models mount
    if envs.get('model_id') and envs.get('version_id'):
        cp_model = {
            "name": project_id,
            "mountPath": "/models",
            "subPath": f"{minio_bucket}/model-data/{envs.get('model_id')}/{envs.get('version_id')}"
        }
        if resource_quota_full:
            cp_model["readOnly"] = True
        volumes.append(cp_model)

    return volumes


def experiment_mount(project_id, minio_bucket, resource_quota_full):
    """
    This function is used to return the kubernetes volume mount params
    :param project_id:
    :param minio_bucket:
    :param resource_quota_full:
    :return dict:
    """
    volumes = []
    # Experiment mount
    exp_mount = {
        "name": project_id,
        "mountPath": "/mlflow",
        "subPath": f"{minio_bucket}"
    }
    if resource_quota_full:
        exp_mount["readOnly"] = True
    volumes.append(exp_mount)
    return volumes


@log_decorator
def create_job_manifest(
        job_name,
        env_variables,
        image_name,
        cpu,
        memory,
        resource_extra,
        execution_command,
        init_command,
        node_affinity_options,
        metering_info,
        resource_quota_full=False,
        envs=None,
        instance_id=None,
        plugin_id=None
):
    """
    create new job method
    Param:
        job_name
        env_variables
        image_name
        cpu
        memory
        resource_extra
        execution_command
        init_command
        node_affinity_options
        metering_info
        resource_quota_full=False
        envs
        instance_id
        plugin_id
    Return:
        pod
    """

    current_app.logger.debug(f"Inside create_job_manifest, job_name: {job_name}")
    log_dir = f"/snapshot/{instance_id}"

    # getting additional volumes and volume mounts
    volume_count_output, volume_mount_output = volumeVolumeMounts(g.user["mosaicId"], g.user["project_id"])

    # all job volumes
    volume_git = create_kubernetes_volume("git")
    volume_tmp = create_kubernetes_volume("tmp")
    volume_notebooks = create_kubernetes_volume("notebooks")
    volume_list = [volume_git, volume_tmp, volume_notebooks]
    job_volumes = get_volumes(
        project_id=g.user["project_id"],
        username=g.user["mosaicId"],
        volume_count_output=volume_count_output
    )
    job_volumes.extend(volume_list)

    # all job volume mounts
    job_volume_mounts = [
        client.V1VolumeMount(name=volume_git.name, mount_path="/git"),
        client.V1VolumeMount(name=volume_tmp.name, mount_path="/tmp"),
        client.V1VolumeMount(name=volume_notebooks.name, mount_path="/notebooks")
    ]
    job_volume_mounts.extend(
        get_volumes_mount(project_id=g.user["project_id"], username=g.user["mosaicId"],
                          resource_quota_full=resource_quota_full, volume_mount_output=volume_mount_output,
                          log_id=envs.get('log_id'), custom_plugin=True, envs=envs)
    )

    # lifecycle hooks
    lifecycle_hooks = job_lifecyclehooks(None, metering_info, "")

    # getting container execution command
    command_var = update_execution_command(execution_command, metering_info, log_dir)

    # container
    container = client.V1Container(
        name=job_name,
        image=image_name,
        image_pull_policy="IfNotPresent",
        ports=[client.V1ContainerPort(container_port=80)],
        volume_mounts=job_volume_mounts,
        env=env_variables,
        lifecycle=lifecycle_hooks,
        resources=client.V1ResourceRequirements(
            limits=fetch_resource_limitscaling_guarantee(
                cpu, memory, resource_extra, current_app.config["TEMPLATE_RESOURCE_CPU_LIMIT_PERCENTAGE"], current_app.config["TEMPLATE_RESOURCE_MEMORY_LIMIT_PERCENTAGE"]
            ),
            requests=fetch_resource_request_limit(
                cpu, memory, current_app.config["TEMPLATE_RESOURCE_CPU_REQUEST_PERCENTAGE"], current_app.config["TEMPLATE_RESOURCE_MEMORY_REQUEST_PERCENTAGE"], resource_extra)
        ),
        command=command_var,
    )

    # init Container
    init_container = client.V1Container(
        name="init-container",
        image=current_app.config["GIT_INIT_IMAGE"],
        image_pull_policy="IfNotPresent",
        command=[
            "/bin/sh",
            "-c",
            f"{init_command}"
        ],
        env=[client.V1EnvVar(name="user_name", value=g.user["mosaicId"]),
             client.V1EnvVar(name="PROJECT_ID", value=g.user["project_id"]),
             client.V1EnvVar(name="first_name", value=g.user["first_name"]),
             client.V1EnvVar(name="email_address", value=g.user["email_address"]),
             client.V1EnvVar(name="mode", value="RUN"),
             client.V1EnvVar(name="instance_id", value=str(instance_id))],
        volume_mounts=job_volume_mounts,
        resources=client.V1ResourceRequirements(
            limits=json.loads(current_app.config["GIT_INIT_CONTAINER_LIMIT"]),
            requests=json.loads(current_app.config["GIT_INIT_CONTAINER_REQUEST"]),
        )
    )

    # pod_template
    pod_template = template_manifest(
        job_name=job_name,
        init_containers=[init_container],
        containers=[container],
        share_process_namespace=True,
        volumes=job_volumes,
        node_affinity_options=node_affinity_options,
        user_impersonation=False,
        user_imp_data={},
        kernal_type=KernelType.python_plugin,
        envs=envs
    )

    # Spec
    spec_pod = client.V1JobSpec(
        ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600), backoff_limit=0, template=pod_template
    )

    # Pod
    pod = client.V1Job(
        kind="Job", metadata=client.V1ObjectMeta(name=job_name), spec=spec_pod
    )

    return pod


def create_kubernetes_volume(name):
    """
    Create Kubernetes Volumes
    Param:
    name: Volume name
    Return:
        volume
    """
    volume = client.V1Volume(
        name=name, empty_dir=client.V1EmptyDirVolumeSource(medium="")
    )
    return volume


def update_execution_command(execution_command, metering_info, log_dir):
    """
    update execution command
    Param:
    execution_command: Execution command
    metering_info: Metering info
    log_dir: log directory path
    Return:
        Container execution command
    """

    log_central_on_success = (
        "if sudo -S -p \"\" echo -n < /dev/null 2> /dev/null; then sudo pkill tail; else pkill tail; fi")
    log_central_on_fatal = f"mv {log_dir}/healthy {log_dir}/unhealthy; sleep 15;"
    terminate_now = ('if [ -z ${Terminate+x} ]; then echo "\nProgram Success";'
                     + log_central_on_success +
                     ' else echo "Program Failed";' + log_central_on_fatal + 'exit 1; fi; \n'
                     )

    command = f"{execution_command} \n" \
              f"{stop_metering_request(metering_info)} || " \
              f"({stop_metering_request(metering_info)} && echo \"metering error\" && exit 1); \n" \
              f"{terminate_now} \n" \
              f"exit 0;"

    command_var = [
        "/bin/bash",
        "-c",
        f"{command}"
    ]
    current_app.logger.debug(command_var)
    return command_var


@log_decorator
def retrieve_env_for_spark(pod_name, var_name, container_name='notebooks'):
    api_instance = client.CoreV1Api()
    namespace = DeploymentTemplateNames().get_default_namespace()
    pod = api_instance.read_namespaced_pod(name=pod_name, namespace=namespace)
    for c in pod.spec.containers:
         if c.name == container_name:
             current_app.logger.info(f"inside container notebooks")
             for env_var in c.env:
                 if env_var.name == var_name:
                     current_app.logger.info(f"{var_name} is {env_var.value}")
                     return env_var.value


@log_decorator
def select_nodeports_for_spark():
    """ This returns unique pair of nodeport number between range
        which is not already used in already created nodeport
    """
    nodeport_start = current_app.config['NODEPORT_START_RANGE']
    nodeport_end = current_app.config['NODEPORT_END_RANGE']
    nodeport_range = range(nodeport_start, nodeport_end)
    already_used_nodeports = find_already_used_nodeports(nodeport_range)
    unique_nodeports = random.sample(nodeport_range, 2)
    if already_used_nodeports and unique_nodeports[0] in already_used_nodeports and unique_nodeports[1] in already_used_nodeports:
        if len(already_used_nodeports) > current_app.config['MAX_ALLOWED_NODEPORTS']:
            raise ValueError(f"Invalid request: maximum no. of nodeports allowed limit reached")
        return select_nodeports_for_spark()
    else:
        return unique_nodeports[0], unique_nodeports[1]


@log_decorator
def find_already_used_nodeports(nodeport_range):
    v1 = client.CoreV1Api()
    services = v1.list_service_for_all_namespaces().items
    used_ports = set()
    for service in services:
        if service.spec.type == 'NodePort':
            for port in service.spec.ports:
                if port.node_port in nodeport_range:
                    used_ports.add(port.node_port)
    return list(used_ports)
