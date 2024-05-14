# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Controllers for mosaic-kubespawner"""
import time
import traceback
import json
import uuid
import io
import os
import yaml
from typing import Generator, Dict, Tuple, Any
from datetime import datetime
import requests
from flasgger import swag_from
from flask import request, Response, jsonify, g, stream_with_context, current_app
from flask.views import MethodView
import pandas as pd
from kubernetes import client, config, watch
from kubernetes.stream import stream as k8_stream
from .manager import (
    execute_custom_hook,
    execute_custom_job_per_type,
    execute_custom_hook_with_docker,
    execute_custom_job_per_type_with_docker,
    execute_dbt_pod_with_docker,
    execute_dbt_pod,
    execute_experiment,
    get_pod_metrics,
    get_pod_metrics_range,
    get_pod_metrics_max,
    delete_job,
    create_k8_resources,
    delete_k8_resources,
    delete_k8_service_obj,
    delete_pod,
    create_k8_pod,
    get_pod_progress,
    delete_k8_resources_byoc,
    attach_metadata_lable_to_pod,
    log_decorator,
    list_namespaced_pod,
    get_volumes,
    create_cronjob_or_instantaneous_job,
    CronJob
)
from . import scheduler_api
from .job import ExecuteScheduledJob, ExecuteJob
from .manager import clean_env_variables
from notebooks_api.utils.exceptions import StatusCodes
from ..notebook.manager import register_snapshot


@scheduler_api.route("/v1/spawner/ping")
@swag_from("swags/ping.yaml")
def pong():
    """ Endpoint used to check the health of the service """
    return "pong"


@scheduler_api.route("/v1/spawner/execute-notebook", methods=["POST"])
@swag_from("swags/execute_schedule.yaml")
def execute_scheduled_job():
    """ Endpoint for executing the scheduled notebook

    JSON payload:
        {
          "file_path": Path of the notebook
          "pip_packages": Pip packages that need to be installed
          "repo_name": Name of the Repo
          "env": environment  variables
          "init_script": Executing Init-Script provided by user
          "kernel_type": Kernel type for determinig whether to submit jobs to livy
          "async": Deploying type for scheduled notebook
          "docker_url": Docker url of the notebook to be scheduled
          "CPU": CPU limit as per NB template
          "memory": Memory limit as per NB template
          "execution_command": Command for entrypoint to execute the job
        }

    """
    # parse data
    data = request.get_json()
    current_app.logger.debug(f"\nInside execute-notebook, data: {data}\n")
    if "bearer_token" in request.headers:
        data["bearer_token"] = request.headers["bearer_token"]
    else:
        data["bearer_token"] = ""
    # Executing the Scheduled Notebook
    try:
        execute_job = ExecuteScheduledJob(data)
        response_status, job_name = execute_job.execute_notebook()
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0002

    if response_status == "Fail":
        return StatusCodes.ERROR_0001, 429

    return job_name, 200


@scheduler_api.route("/v1/spawner/custom_job", methods=["POST"])
@swag_from("swags/custom_execute_schedule.yaml")
def execute_custom():
    """ Endpoint for executing the scheduled notebook

    JSON payload:
        {
            "repo_protocol":"Name of the repo protocol",
            "repo_name":"Name of the repo",
            "git_username":"Username of the repo",
            "git_access_token":"Access Token of the repo",
            "git_server":"Server of the repo",
            "git_namespace":"Namespace of the repo",
            "language":"Programming language of the repo"
            "job_instanceid":"Job Instance Id"
            "env":"Environment Variables"
        }
    """

    # parse data
    current_app.logger.debug("Fetching JSON Data")
    data = request.get_json()
    current_app.logger.debug(data)
    # Executing the Scheduled Notebook
    current_app.logger.info("Executing Scheduler Notebook")

    try:
        # pylint: disable=unused-variable
        container_ecosystem = current_app.config.get("CONTAINER_ECOSYSTEM", "kubernetes")
        if container_ecosystem == "docker": 
            response_status, job_name = execute_custom_hook_with_docker(data)
        else: 
            response_status, job_name = execute_custom_hook(data)

    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        print(ex)
        current_app.logger.error(ex)
        return ""

    return job_name, 200


@scheduler_api.route("/v1/spawner/custom_job_per_type", methods=["POST"])
@swag_from("swags/custom_job_per_type.yaml")
def execute_job_per_type():
    """ Endpoint for executing the scheduled notebook

    JSON payload:
        {
            "repo_protocol":"Name of the repo protocol",
            "repo_name":"Name of the repo",
            "entity_type":"Type of the entity"
            "git_username":"Username of the repo",
            "git_access_token":"Access Token of the repo",
            "git_server":"Server of the repo",
            "git_namespace":"Namespace of the repo",
            "language":"Programming language of the repo",
            "job_instanceid":"Job Instance Id",
            "attempt_id":"Job Attempt Id",
            "env":"Environment Variables"
        }
    """

    # parse data
    current_app.logger.debug("Fetching JSON Data")
    data = request.get_json()
    current_app.logger.debug(data)

    try:
        # pylint: disable=unused-variable
        container_ecosystem = current_app.config.get("CONTAINER_ECOSYSTEM", "kubernetes")
        if container_ecosystem == "docker":
            response_status, job_name = execute_custom_job_per_type_with_docker(data)
        else:
            response_status, job_name = execute_custom_job_per_type(data)
    except Exception as ex:
        current_app.logger.error(ex)
        return ""
    return job_name, 200


@scheduler_api.route("/v1/spawn_pod", methods=["POST"])
@swag_from("swags/dbt_execute_schedule.yaml")
def execute_dbt():
    """ Endpoint for executing the scheduled notebook

    JSON payload:
        {
            "sensitiveInfo":"sensitive information"
            "cloud_data_platform":"Cloud Data Platform"
            "env":"Environment Variables"
            "runConfiguration":"run configuration details"
            "podName":"flowname_Job_instanceId"
        }
    """

    # parse data
    current_app.logger.debug("Fetching JSON Data")
    data = request.get_json()
    # Executing the Scheduled Notebook

    try:
        # pylint: disable=unused-variable
        container_ecosystem = current_app.config.get("CONTAINER_ECOSYSTEM", "kubernetes")
        if container_ecosystem == "docker": response_status, job_name = execute_dbt_pod_with_docker(data)
        else: response_status, job_name = execute_dbt_pod(data)
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        print(ex)
        current_app.logger.error(ex)
        return ""

    return job_name, 200


# pylint: disable=inconsistent-return-statements
@scheduler_api.route("/v1/spawner/experiment", methods=["POST"])
@swag_from("swags/execute_experiment.yaml")
def execute_experiment_api():
    """ Endpoint for executing an experiment of auto ml
    JSON payload:
    :param payload: Dictionary containing
        experiment_name(str): name of the experiment (unique for a given project)
        experiment_description (str): description of experiment
        experiment_type(str): classification/regression
        dataset_name (str) : name of dataset
        id (str) :unique identifier
        upload_from_catalog (boolean): True or false whether data uploaded from catalog or not
        target_column (str): target column that is to be predicted
        feature_column(str): string of comma separated features selected by user
        data_mode:(str) whether text,image or tabular
        TOKEN(str): token id for project
        automl_style(str): the style in which you want automl to run(auto, quick, manual)
        recipe_params(dict): default none , in manual mode dictionary
            eg  {
                “recipe_id“:”123”,”recipe_name”:”TPOT”,
                ”Recipe_run_param”:{'svm': ' c=0.0.1, kernel = “linear“'},
                “recipe_docker_url“: “100“,recipe_run_params=””,
                recipe_nb_name="a.ipynb"
                }
        additional_dataset_params(dict): folder structure and other details if any
    :type payload: JSON
    """
    # fetch data
    experiment_data = request.get_json()
    current_app.logger.debug(experiment_data)
    experiment_id = experiment_data['id']
    token = experiment_data['TOKEN']
    current_app.logger.info("Execute experiment")
    try:
        response = execute_experiment(experiment_id, experiment_data, token)
        if response["job_name"]:
            return jsonify({"job_name": response["job_name"],
                            "snapshot_name": response["snapshot_name"]}), 201
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.exception(ex)
        return jsonify({"job_status": "failed"}), 201


@scheduler_api.route("/v1/spawner/metrics/pod-name/<string:pod_name>", methods=["GET"])
@swag_from("swags/fetch_pod_metrics.yaml")
def fetch_pod_metrics(pod_name):
    """Fetch pod metrics method"""
    service_name = current_app.config["PROMETHEUS_URL"]
    start = request.args.get('start')
    end = request.args.get('end')
    step = request.args.get('step')
    time_series_data = str(request.args.get('time_series_data', "false")).lower() == "true"

    try:
        if bool(start and end and step):
            current_app.logger.info("Fetching pod_metrics_range")
            metrics = get_pod_metrics_range(pod_name, service_name, float(start), float(end), int(step),
                                            time_series_data=time_series_data)
        else:
            metrics = get_pod_metrics(pod_name, service_name)
        return jsonify(metrics)
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0003, 500

@scheduler_api.route("/v1/spawner/pod_metrics_max/pod-name/<string:pod_name>", methods=["GET"])
@swag_from("swags/fetch_pod_metrics_max.yaml")
def fetch_pod_metrics_max(pod_name):
    """Api to Fetch Maximum CPU & Memory Utilization since the pod started"""
    service_name = current_app.config["PROMETHEUS_URL"]

    try:
        current_app.logger.info("Fetching pod_metrics_max")
        pod_metrics_max = get_pod_metrics_max(pod_name, service_name)
        return jsonify(pod_metrics_max)

    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0003, 500


def get_message(pod_name):
    """this function returns pod_metrics data """
    service_name = current_app.config["PROMETHEUS_URL"]
    metrics = get_pod_metrics(pod_name, service_name)
    return metrics


@scheduler_api.route("/v1/spawner/stream/pod-name/<string:pod_name>")
@swag_from("swags/fetch_pod_metrics.yaml")
def stream(pod_name):
    """Stream method"""

    def event_stream():
        """event stream method"""
        while True:
            time.sleep(5)
            metrics = get_message(pod_name)
            if isinstance(metrics, dict):
                yield "data: {}\n\n".format(metrics)
            else:
                break

    return Response(
        stream_with_context(event_stream()),
        content_type="text/event-stream",
        headers={"Connection": "keep-alive"},
    )


# pylint: disable=inconsistent-return-statements, invalid-name, redefined-builtin
@scheduler_api.route("/v1/spawner/pod-name/<string:id>", methods=["GET"])
@swag_from("swags/get_pod_name.yaml")
def get_pod_name(id):
    """Function to fetch pod name"""
    current_app.logger.debug("get_pod_name")
    try:
        headers = {"X-Auth-Username": g.user["first_name"]}
        service_name = current_app.config["MONITOR_URL"]
        url = f"{service_name}/logaggregator/list-active-pods"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            for pod_details in response.json():
                if id in pod_details["podName"]:
                    container_name = pod_details["podName"]
                    return container_name
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0004, 500


@scheduler_api.route("/v1/spawner/job-name/<string:job_name>", methods=["DELETE"])
def delete_job_by_name(job_name):
    """Function to delete job by name"""
    try:
        print("before delete job")
        data = delete_job(job_name, current_app.config["KUBERNETES_NAMESPACE"])
        return jsonify(data), 200
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0005, 500


@scheduler_api.route("/v1/spawner/create_k8_objects_knights_watch", methods=["POST"])
@swag_from("swags/create_k8_objects_knights_watch.yaml")
def create_k8_objects_knights_watch():
    """Method to create kubernetes objects knights watch"""
    data = request.get_json()
    try:
        pod_name = data.get("pod_name").replace("@", "")
        template_id = data.get("template_id")
        create_k8_resources(pod_name, template_id)
        return jsonify(msg="success"), 200
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0006, 500


@scheduler_api.route(
    "/v1/spawner/delete_k8_objects_knights_watch/<string:template_id>", methods=["DELETE"]
)
@swag_from("swags/delete_k8_objects_knights_watch.yaml")
def delete_k8_objects_knights_watch(template_id):
    """Method to delete kubernetes objects knights watch"""
    try:
        delete_successful = delete_k8_resources(template_id)
        if delete_successful:
            return jsonify(msg="success"), 200
        return StatusCodes.ERROR_0007, 500
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0007, 500


@scheduler_api.route(
    "/v1/spawner/delete_k8_service_objects", methods=["DELETE"]
)
@swag_from("swags/delete_k8_service_objects.yaml")
def delete_k8_service_objects():
    """This method is used to delete k8 objects from kubernetes cluster"""
    try:
        data = request.get_json()
        delete_obj_successful = delete_k8_service_obj(data)
        if delete_obj_successful:
            return jsonify(msg="success"), 200
        return StatusCodes.ERROR_0007, 500
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0007, 500

@scheduler_api.route("/v1/spawner/pod-name/<string:pod_name>", methods=["DELETE"])
def delete_pod_by_name(pod_name):
    """Function to delete pod by name"""
    try:
        data = delete_pod(pod_name, current_app.config["KUBERNETES_NAMESPACE"])
        return jsonify(data), 200
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0005, 500


@scheduler_api.route("/v1/spawner/create_k8_resources_byoc", methods=["POST"])
@swag_from("swags/create_k8_resources_byoc.yaml")
# pylint: disable-msg=too-many-locals
def create_k8_resources_byoc():
    """Method to create kubernetes objects for byoc"""
    data = request.get_json()
    project_id = request.headers.get('X-Project-Id')
    try:
        container_name = data.get("pod_name").replace("@", "")
        docker_image_name = data.get("docker_url")
        port_no = data.get("port")
        pod_resources = data.get("pod_resources")
        cmd = data.get("cmd")
        argument = data.get("argument")
        env = []
        envs = data.get("env")
        if envs:
            for key, val in clean_env_variables(envs).items():
                env_dict = {"name": key, "value": val}
                env.append(env_dict)

        ingress_url = data.get("ingress_url")
        commit_type = data.get("commit_type")
        kernel_type = data.get("kernel_type")
        cran_packages = data.get("cran_packages")
        pip_packages = data.get("pip_packages")
        conda_packages = data.get("conda_packages")
        init_script = data.get("init_script")
        node_affinity_options = data.get("node_affinity_options")
        enabled_repo = data.get("enabled_repo")
        snapshots = data.get("snapshots")
        metering_info = data.get("metering_info")
        git_macros_config = data.get("git_macros_config")
        current_app.logger.debug("calling create_k8_pod")
        resource_quota_full = data.get("resource_quota_full")
        user_imp_data = data.get("user_imp_data")
        version = data.get("version")
        create_k8_pod(container_name, docker_image_name, port_no, pod_resources,
                      cmd, argument, env, project_id, commit_type,
                      kernel_type, cran_packages, pip_packages, conda_packages, init_script,
                      node_affinity_options, enabled_repo, snapshots, metering_info,
                      git_macros_config, resource_quota_full, envs, user_imp_data, version)
        return jsonify(msg="success", port_no=port_no, ingress_url=ingress_url), 200
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0008, 500


@scheduler_api.route("/v1/spawner/progress/pod-name/<string:pod_name>")
@swag_from("swags/progress.yaml")
def progress(pod_name):
    """Stream method"""
    print("progress url called")
    port_no = request.args.get('port_no')
    ingress_url = request.args.get('ingress_url')
    kernel_type = request.args.get('kernel_type')
    current_app.logger.debug(port_no)
    current_app.logger.debug(ingress_url)
    call_instance = 0
    def event_stream(call_instance):
        """event stream method"""
        while True:
            try:
                print("event api progress while true")
                data = get_pod_progress(pod_name, port_no, ingress_url, kernel_type, call_instance)
                print("data is ", data)
                call_instance += 1
                if isinstance(data, dict):
                    if isinstance(data['message'], list):
                        for message in data['message']:
                            data['message'] = message
                            yield "data: {}\n\n".format(json.dumps(data))
                    else:
                        yield "data: {}\n\n".format(json.dumps(data))
                else:
                    break
            except Exception as e:
                exception_dict = {"message": str(e)}
                current_app.logger.error("Exeption occured while executing /progress api")
                current_app.logger.error(e)
                yield "data: {}".format(exception_dict)
                break

    return Response(
        stream_with_context(event_stream(call_instance)),
        content_type="text/event-stream",
        headers={"Connection": "keep-alive"},
    )


@scheduler_api.route(
    "/v1/spawner/delete_k8_objects_byoc/<string:pod_name>", methods=["DELETE"]
)
@swag_from("swags/delete_k8_objects_byoc.yaml")
def delete_k8_objects_byoc(pod_name):
    """Method to delete kubernetes objects byoc"""

    try:
        delete_successful = delete_k8_resources_byoc(pod_name)
        if delete_successful:
            return jsonify(msg="success"), 200
        return StatusCodes.ERROR_0007, 500
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0007, 500


@scheduler_api.route("/v1/spawner/create-cronjob", methods=["POST"])
@swag_from("swags/create_cronjob.yaml")
def create_k8s_cronjob():
    """Method to create cron job in kubernetes"""
    data = request.get_json()
    try:
        response = create_cronjob_or_instantaneous_job(data)
        if response == "success":
            return jsonify(response), 200
        return StatusCodes.ERROR_0010, 500
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0010, 500


@scheduler_api.route("/v1/spawner/delete-cronjob/<string:job_name>", methods=["DELETE"])
@swag_from("swags/delete_cronjob.yaml")
def delete_k8s_cronjob(job_name):
    """Method to delete cron job by name in kubernetes"""
    try:
        response = CronJob(job_name).delete()
        if response:
            return jsonify(response), 200
        return StatusCodes.ERROR_0011, 500
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0011, 500


@scheduler_api.route("/v1/spawner/cronjob-suspend-action", methods=["PATCH"])
@swag_from("swags/cronjob_suspend_action.yaml")
def cronjob_suspend_action():
    """Method to suspend or resume cron job in kubernetes"""
    job_name = request.args.get('job_name')
    action = request.args.get('action')
    try:
        response = CronJob(job_name).suspend_and_resume(action)
        if response:
            return jsonify(response), 200
    except Exception as ex:
        current_app.logger.error(ex)


@scheduler_api.route("/v1/spawner/update-cronjob", methods=["PATCH"])
@swag_from("swags/update_cronjob.yaml")
def update_k8s_cronjob():
    """Method to update cron expression and env variables on existing cron job in kubernetes"""
    data = request.get_json()
    job_name = data["jobName"]
    cron_schedule = data["cronExpression"]
    env_var = data["envVar"]
    try:
        response = CronJob(job_name).update(cron_schedule, env_var)
        if response:
            return jsonify(response), 200
        return StatusCodes.ERROR_0012, 500
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0012, 500


@scheduler_api.route("/v1/spawner/execute-job", methods=["POST"])
@swag_from("swags/execute_job.yaml")
def execute_job():
    """
    Endpoint for executing the scheduled job.
    Request body should have the below params:
        "docker_url": Image used in container
        "cpu": Cpu limit in container
        "memory": Memory limit in container
        "resource_extra": Type of computing unit, cpu/gpu
        "execution_command": Execution command for container
        "init_command": Init command for container
        "node_affinity_options": node affinity option
        "subscriber_info": subscriber info
        "job_name": job name
        "instance_id": instance id generated from monitor
        "env": env variables to be initialised in container
        "resource_quota_full": Whether used is resource quota left in current project
        "plugin_id": plugin id
    """
    request_data = request.get_json()
    current_app.logger.info(f"\nInside execute-job, request_data: {request_data}\n")

    # Executing the Scheduled Job
    try:
        execute_jobs = ExecuteJob(request_data)
        response_status, job_name = execute_jobs.execute_job()
        current_app.logger.info(f"\nInside execute-job, response_status: "
                                f"{response_status}\njob_name: {job_name}\n")
    # pylint: disable=broad-except
    except Exception as ex:
        current_app.logger.error(ex)
        return StatusCodes.ERROR_0002

    if response_status == "Fail":
        return StatusCodes.ERROR_0001, 429  # Too Many request, kubernetes job creation limitation

    return job_name, 200


class LogCentralView(MethodView):
    """
    Log Central View Manages and streams logs present in central.log file.
    """
    methods = ['GET']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)
        self.stream_watcher = watch.Watch()

        self.pod_name = None
        self.container_name = None
        self.namespace = None

    # pylint: disable=too-many-arguments
    def log_stream(self,
                   tail_lines: int,
                   follow: bool = False,
                   previous: bool = False,
                   since_seconds: int = None,
                   testing: bool = False) -> Generator[str, None, None]:
        """
        This function defines generator for log streaming

        :param tail_lines:      Number of lines to return
        :param follow:          If True, sets to stream
        :param previous:        If True, logs are retrieved from terminated container.
        :param since_seconds:   Integer number of seconds to retrieve
        :param testing:         Bool
        :return:  << yield logs >>
        """

        current_app.logger.info(f"LogCentralView previous {previous} "
                                f"follow {follow} since {since_seconds} "
                                f"testing {testing}")

        _params = dict(name=self.pod_name,
                       namespace=self.namespace,
                       container=self.container_name,
                       tail_lines=tail_lines,
                       follow=follow,
                       previous=previous)

        if since_seconds:
            _params.update(dict(since_seconds=since_seconds))

        log_stream = self.stream_watcher.stream(self.api_instance.read_namespaced_pod_log,
                                                **_params)
        while True:
            for chunk_ in log_stream:
                if testing:
                    return jsonify({"message": True}), 200
                try:
                    yield f"data: {chunk_}\n\n"
                # pylint: disable=broad-except
                except Exception as ex:
                    current_app.logger.info(ex)

            if testing:
                break

        return jsonify({"message": True}), 200

    @swag_from("swags/fetch_log_central_contents.yaml")
    def get(self,
            pod_name: str,
            container_name: str) -> Generator[str, None, None]:
        """
        This method will fetch all the logs from the log central container
        :param pod_name: Name of the kubernetes pod
        :param container_name: Name of container to stream logs
        :return: << yield logs >>
        """

        self.pod_name = pod_name
        self.container_name = container_name
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]

        since_seconds = request.args.get('since_seconds', None)
        if since_seconds:
            since_seconds = int(since_seconds)

        tail_lines = int(request.args.get('tail_lines', 1))

        params_dict = {"follow": request.args.get('stream', False),
                       "previous": request.args.get('previous', False),
                       "testing": request.args.get('testing', True)
                       }

        for name_, value_ in params_dict.items():
            if not isinstance(value_, str):
                continue
            if value_.lower() == "true":
                params_dict[name_] = True
            elif value_.lower() == "false":
                params_dict[name_] = False

        current_app.logger.info(f"LogCentralView params: {params_dict}, "
                                f"tail_lines {tail_lines} "
                                f"since_seconds {since_seconds} ")

        return Response(
            stream_with_context(self.log_stream(tail_lines,
                                                params_dict["follow"],
                                                params_dict["previous"],
                                                since_seconds,
                                                params_dict["testing"])),
            content_type="text/event-stream",
            mimetype="text/event-stream",
            headers={"Connection": "keep-alive"},
        )


scheduler_api.add_url_rule('/v1/spawner/log_central/<string:pod_name>/<string:container_name>',
                           view_func=LogCentralView.as_view('log_central_view'))


class KYDCheckpointJob(MethodView):
    """
    KYDCheckpointJob creates Job for Checkpointing drift
    """
    # pylint: disable=too-many-instance-attributes

    methods = ['POST', 'DELETE']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.batch_client = client.BatchV1Api()
        self.batch_v1_client = client.BatchV1beta1Api()
        self.api_instance = client.CoreV1Api(self.api_client)

        self.model_id = None
        self.version_id = None
        self.pod_name = None
        self.container_name = None
        self.namespace = None
        self.image_to_use = None
        self.job_name = None
        self.memory = None
        self.cpu = None
        self.to_execute = None
        self.custom_env = {}
        self.job_frequency = None
        self.job_cron = None
        self.fetch_from_db = None
        self.snapshot_name = "Drift_{}".format(datetime.now().strftime("%b_%d_%Y_%H_%M"))

        self.jwt_token = None
        self.project_id = None
        self.init_script = None

        self.settings_url = "{}/v1/ml-model/{}/version/{}/kyd/settings"

    def set_jwt(self, headers):
        """
        Sets JWT token
        :param headers: Requests  Headers Information
        :return: None
        """
        request_url = "{}/v1/token".format(current_app.config["MOSAIC_AI_SERVER"])
        response = requests.post(request_url, json={}, headers=headers)
        self.jwt_token = response.content.decode("utf-8")

    # pylint: disable=too-many-locals
    def create_job_object(self, cron=False):
        """
        Creates Job Manifest For the K8 Job
        :return: Job
        """
        env_var = {"ML_MODEL_ID": self.model_id,
                   "ML_VERSION_ID": self.version_id,
                   "MY_JOB_NAME": self.job_name,
                   "MOUNT_PATH":  "/kyd_data",
                   "TOKEN": self.jwt_token,
                   "PROJECT_ID": self.project_id,
                   "MOSAIC_AI_SERVER": current_app.config["MOSAIC_AI_SERVER"],
                   "DATA_SNAPSHOT_NAME": self.snapshot_name
                   }
        env_var.update(self.custom_env)

        env_var_from = {"MY_POD_NAME": "metadata.name"}
        env = []

        for name, value in clean_env_variables(env_var).items():
            env.append(client.V1EnvVar(name=name, value=value))

        for name, value in clean_env_variables(env_var_from).items():
            from_ = client.V1EnvVarSource(
                field_ref=client.V1ObjectFieldSelector(field_path=value)
            )
            env.append(client.V1EnvVar(name=name, value_from=from_))

        current_app.logger.info(f"custom env  {self.custom_env}")
        try:
            # load the config template
            with open(os.path.join(os.path.dirname(__file__), "manifests/init-script-config.yaml")) as file:
                config_yaml = file.read()

            namespace = self.namespace
            # replace values
            config_yaml = config_yaml.format(
                script=self.init_script,
                namespace=self.namespace,
                name=self.job_name,
                labels=self.labels,
            )
            config_manifest = yaml.safe_load(config_yaml)
            k8s_beta = client.CoreV1Api()
            k8s_beta.create_namespaced_config_map(
                body=config_manifest, namespace=namespace
            )
            current_app.logger.info("Init-Script-Config for xai created.")
            # pylint: disable=broad-except
        except Exception as ex:
            current_app.logger.error(ex)
            return StatusCodes.ERROR_0006, 500

        volume_shared_code = client.V1Volume(
            name="code", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )

        volume_mounts = [client.V1VolumeMount(
            name=g.user["project_id"], mount_path="/output",
            sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}'
                     f'/{g.user["project_id"]}/'
                     f'{g.user["project_id"]}-Snapshot'
                     f'/{self.snapshot_name}'
        ),
            client.V1VolumeMount(
                name="tmp", mount_path="/tmp"),
            client.V1VolumeMount(
                name="init-script-expai", mount_path="/tmp_expai"),
            client.V1VolumeMount(name=volume_shared_code.name, mount_path="/code"),
            client.V1VolumeMount(name = g.user["project_id"], mount_path="/kyd_data",
                                sub_path=f'{current_app.config["MINIO_DATA_BUCKET"]}/'
                                          f'model-data'
                                 ),
        ]

        init_container = client.V1Container(
            name="init",
            image=current_app.config["GIT_IMAGE_NAME"],
            image_pull_policy="IfNotPresent",
            command=[
                "/bin/sh",
                "-c",
                "cp -r /shared_code/* /code/ ;"
                "touch /output/central.log; \n"
                "chmod -R 777 /output; \n"
                "chmod -R 777 /output/central.log; \n"
                "touch /output/healthy; \n"
                "chmod -R 777 /output/healthy; \n"
                "chmod -R 777 /output; \n"
                "echo \"===== * $(date '+%d/%m/%Y %H:%M:%S') * ===== \" >> /output/central.log; \n"
            ],
            volume_mounts=volume_mounts,
            resources=client.V1ResourceRequirements(
                limits=json.loads(current_app.config["GIT_INIT_CONTAINER_LIMIT"]),
                requests=json.loads(current_app.config["GIT_INIT_CONTAINER_REQUEST"]),
            )
        )

        container = client.V1Container(
            name=self.container_name,
            image=self.image_to_use,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=80)],
            env=env,
            command=self.to_execute,
            volume_mounts=volume_mounts,
            resources=client.V1ResourceRequirements(limits={"cpu": self.cpu,
                                                            "memory": self.memory}),
        )
        # pylint: disable=bad-continuation
        log_central = client.V1Container(
            name="log-central",
            image=self.image_to_use,
            image_pull_policy="IfNotPresent",
            volume_mounts=volume_mounts,
            liveness_probe=client.V1Probe(_exec=client.V1ExecAction(
                command=["cat",
                         "/output/healthy"
                         ]),
                initial_delay_seconds=5,
                period_seconds=5,
                timeout_seconds=1),
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

        configmap_volume = client.V1Volume(
            name="init-script-expai",
            config_map=client.V1ConfigMapVolumeSource(
                name=self.job_name,
                items=[client.V1KeyToPath(key="init-script.sh", path="init-script.sh")]
            )
        )
        volume_tmp = client.V1Volume(
            name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium="")
        )


        job_volume.append(configmap_volume)
        job_volume.append(volume_tmp)
        job_volume.append(volume_shared_code)

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=attach_metadata_lable_to_pod(self.job_name)),
            spec=client.V1PodSpec(restart_policy="Never",
                                  share_process_namespace=True,
                                  init_containers=[init_container],
                                  containers=[container, log_central],
                                  service_account_name=current_app.config['SERVICE_ACCOUNT_NAME'],
                                  image_pull_secrets=[client.V1LocalObjectReference(name=current_app.config["IMAGE_PULL_SECRETS"])],
                                  volumes=job_volume,
                                  )
        )

        spec = client.V1JobSpec(
            ttl_seconds_after_finished=current_app.config.get("TTL_SECONDS_AFTER_FINISHED", 3600),
            template=template,
            backoff_limit=0)

        if cron:
            job = self.create_cron_job(pod_template_spec=spec)
        else:
            job = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(name=self.job_name),
                spec=spec)

        service = client.V1Service()
        service.api_version = "v1"
        service.kind = "Service"
        service.metadata = client.V1ObjectMeta(name=f"{self.job_name}-svc")
        service_spec = client.V1ServiceSpec()
        service_spec.selector = {"app": self.job_name}
        service_spec.ports = [client.V1ServicePort(protocol="TCP",
                                                   port=80,
                                                   target_port=8080)]
        service.spec = service_spec

        self.api_instance.create_namespaced_service(
            body=service, namespace=current_app.config["KUBERNETES_NAMESPACE"]
        )

        return job

    def create_cron_job(self, pod_template_spec):
        """
        This method will create cron job object to run periodically.

        :return: object
        """
        cron_template = client.V1beta1JobTemplateSpec(
            metadata=client.V1ObjectMeta(labels=attach_metadata_lable_to_pod(self.job_name)),
            spec=pod_template_spec
        )

        cron_spec = client.V1beta1CronJobSpec(
            job_template=cron_template,
            schedule=self.job_cron,
            successful_jobs_history_limit=3,
            failed_jobs_history_limit=1,
        )

        cron_job = client.V1beta1CronJob(
            api_version="batch/v1beta1",
            kind="CronJob",
            metadata=client.V1ObjectMeta(name=self.job_name),
            spec=cron_spec
        )

        return cron_job

    @swag_from("swags/create_kyd_checkpoint.yaml")
    def post(self,
             model_id: str,
             version_id: str) -> Tuple[Any, int]:
        """
        Creates and executes a custom Job

        {
          "cpu": "2",
          "image_to_use": "jy_36_image",
          "job_prefix": "kyd-",
          "memory": "4Gi",
          "to_execute": ["/bin/sh", "-c", "/code/checkpoint_kyd.sh;"],
          "container_name": "container-name",
          "custom_env": {"RETRIEVE_PROD_DATA_FOR_WEEKS": "4",
                        "DATA_TO_USE":"current_version",
                        "KYD_STATS": "TRUE",
                        "BASELINE_DATA": "train_data",
                        "LOADED_FROM_DB": "FALSE",
                        "DS_ALGO": "ks",
                        "DS_P_VALUE": "0.05"
                        },
          "job_frequency": "on_demand",
          "fetch_params_from_db": false
        }

        """

        self.model_id = model_id
        self.version_id = version_id

        data = request.get_json()
        current_app.logger.info(data)
        self.fetch_from_db = data.get("fetch_params_from_db", None)
        self.settings_url = self.settings_url.format(
            current_app.config["MOSAIC_AI_SERVER"],
            self.model_id,
            self.version_id
        )

        self.init_script = data.get("init_script", "")
        if self.fetch_from_db:
            response = requests.get(self.settings_url, json={}, headers=request.headers)
            data = response.json()
            if isinstance(data, list):
                data = data[0]

        self.job_name = data.get("job_prefix") + str(uuid.uuid4().hex)[0:5]
        self.to_execute = data.get("to_execute", ["/code/kyd_checkpoint.sh"])
        self.container_name = data.get("container_name")
        self.image_to_use = data.get("image_to_use")
        self.memory = data.get("memory")
        self.cpu = data.get("cpu")
        self.job_frequency = data.get("job_frequency", "").lower()

        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
        self.project_id = request.headers.get("X-Project-Id")
        self.labels=attach_metadata_lable_to_pod(self.job_name)

        if self.fetch_from_db:
            current_app.logger.info(f"KYD JOB SETTINGS FROM DB: {data}")
            p_val_ = data.get("ds_config", {})
            env_ = {"RETRIEVE_PROD_DATA_FOR_WEEKS": "{}".format(data.get("past_weeks")),
                    "DATA_TO_USE": "{}".format(data.get("data_to_use")),
                    "KYD_STATS": "{}".format(data.get("data_stats", "TRUE")).upper(),
                    "BASELINE_DATA": "{}".format(data.get("baseline_data")),
                    "POT_OUTLIER_ALGO": "{}".format(data.get("outlier_algo")),
                    "POT_THRESHOLD": "{}".format(data.get("outlier_threshold")),
                    "POT_LOWER_QUARTILE": "{}".format(data.get("outlier_lower_quantile")),
                    "POT_UPPER_QUARTILE": "{}".format(data.get("outlier_upper_quantile")),
                    "LOADED_FROM_DB": "TRUE",
                    "DS_ALGO": "{}".format(data.get("ds_algorithm", "ks")),
                    "DS_P_VALUE": "{}".format(p_val_.get("p_value", "0.05")),
                    "IS_CRON": "{}".format(data.get("is_cron")),
                    "SETTINGS_ID": "{}".format(data.get("id"))
                    }
            self.custom_env = env_
        else:
            self.custom_env = data.get("custom_env", {})
            self.custom_env.update({"LOADED_FROM_DB": "FALSE"})
            if self.job_frequency.lower() == "on_demand":
                self.custom_env.update({"IS_CRON": "FALSE"})
            else:
                self.custom_env.update({"IS_CRON": "TRUE"})

        self.set_jwt(request.headers)
        if self.job_frequency.lower() == "on_demand":
            '''code to store in job'''
            current_app.logger.info("code to store in APi")
            request_url_run_history = "{}/v1/ml-model/{}/version/{}/kyd/history".format(
                current_app.config["MOSAIC_AI_SERVER"], self.model_id, self.version_id)
            json_data = {"pod_name": "",
                         "job_name": self.job_name,
                         "init": True,
                         "running": None,
                         "completed": None,
                         "message": "KYD job is initialized"
                         }

            response_run_history = requests.post(request_url_run_history, json=json_data, headers=request.headers)
            current_app.logger.info(f"request_url_run_history ===== > {response_run_history}")

            self.batch_client.create_namespaced_job(
                body=self.create_job_object(),
                namespace=self.namespace
            )
        else:
            # pylint: disable=implicit-str-concat-in-sequence
            if self.job_frequency in ["hourly", "daily" "weekly", "monthly", "yearly"]:
                self.job_cron = "@{}".format(self.job_frequency.lower())
            else:
                self.job_cron = self.job_frequency

            self.batch_v1_client.create_namespaced_cron_job(
                body=self.create_job_object(cron=True),
                namespace=self.namespace
            )
        snapshot = {"input": self.snapshot_name, "output": self.snapshot_name, "container_object": {"name": 'NA'}}
        enabled_repo = {"repo_name": "NA", "branch": "NA"}
        register_snapshot(snapshot, request.headers.get("X-Auth-Username"), request.headers.get("X-Project-Id"),
                          enabled_repo)
        try:
            pod_name = list_namespaced_pod(self.job_name)
        # pylint: disable=broad-except
        except Exception:
            pod_name = ""

        return jsonify(dict(job_name=self.job_name,
                            pod_name=pod_name,
                            snap_name=self.snapshot_name)), 200

    @log_decorator
    @swag_from("swags/delete_kyd_checkpoint.yaml")
    def delete(self,
               model_id,
               version_id) -> Tuple[Any, int]:
        """

        :param model_id:  Model ID
        :param version_id: Version Id
        :return:
        """

        _status_code = 200

        self.job_name = request.args.get('job_name')
        is_cron = request.args.get('cron')
        grace_period = int(request.args.get('grace_period', 5))

        _prop = request.args.get('propagation_policy', 'Foreground')
        propagation_policy = str(_prop).strip().title()
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]

        current_app.logger.info(f"DeleteKYDCheckpointView: {self.job_name} - Grace: {grace_period}")
        current_app.logger.info(f"DeleteKYDCheckpointView: Model:{model_id} Version:{version_id}")
        try:
            if is_cron.lower() == "false":
                api_response = self.batch_client.delete_namespaced_job(
                    name=self.job_name,
                    namespace=self.namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy=propagation_policy,
                        grace_period_seconds=grace_period))
            else:
                api_response = self.batch_v1_client.delete_namespaced_cron_job(
                    name=self.job_name,
                    namespace=self.namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy=propagation_policy,
                        grace_period_seconds=grace_period))

            _msg = api_response.message
            _status_code = api_response.code
            _reason = api_response.reason
        # pylint: disable=broad-except
        except Exception as e:
            _status_code = 400
            _reason = "NotFound"
            _msg = str(e)

        return jsonify(message=_msg, reason=_reason), _status_code


scheduler_api.add_url_rule('/v1/spawner/kyd/<string:model_id>/<string:version_id>/checkpoint',
                           view_func=KYDCheckpointJob.as_view('kyd_checkpoint_job_view'))


class FetchPackageView(MethodView):
    """
    FetchPackageView retrieves packages in job.
    """
    methods = ['GET']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)

        self.pod_name = None
        self.container_name = None
        self.namespace = None

    def exec(self, command_):
        """
        Executes command in kubernetes pod
        :param command_:  command to execute
        :return:  WSStream
        """
        return k8_stream(self.api_instance.connect_post_namespaced_pod_exec,
                         self.pod_name,
                         self.namespace,
                         container=self.container_name,
                         stderr=True,
                         stdin=True,
                         stdout=True,
                         command=["/bin/sh", "-c", command_])

    # pylint: disable=too-many-locals
    @swag_from("swags/fetch_pod_packages.yaml")
    def get(self,
            pod_name: str,
            container_name: str) -> Tuple[Any, int]:
        """
        This method will fetch all the logs from the log central container
        :param pod_name: Name of the kubernetes pod
        :param container_name: Name of container to stream logs
        :return: Dict[python_packages]
        """

        self.pod_name = pod_name
        self.container_name = container_name
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
        _total_py_package = 0
        _total_r_package = 0
        exhaustive_pkg_df = None

        kernel_type = request.args.get('kernel_type', None)
        current_app.logger.info(f"FetchPackageView: {self.pod_name} - {self.container_name}")
        try:
            if kernel_type in ["rstudio", "r", "R"]:
                cmd_r = """\"ip <- as.data.frame(installed.packages()[,c(1,3)])
                                    write.table(ip, sep = '==',row.names = FALSE)\""""
                pkg_commands = [('echo {} > /tmp/get_package.R \n'
                                 'Rscript /tmp/get_package.R \n'
                                 .format(cmd_r))]
                pkg_kernel = ["R"]
            else:
                pkg_commands = ["pip freeze"]
                pkg_kernel = ["Python"]

            for each_command, each_kernel in zip(pkg_commands, pkg_kernel):
                try:
                    pkg_raw = self.exec(each_command)
                    pkg_frame = pd.read_csv(io.StringIO(pkg_raw),
                                            header=None,
                                            names=["package_name"])
                    current_app.logger.info(f"DF :: {pkg_frame}")
                    pkg_frame[['pkg',
                               'version']] = pkg_frame.package_name.str.split("==",
                                                                              expand=True)
                    pkg_frame.drop(["package_name"], inplace=True, axis=1)
                    pkg_frame['type'] = each_kernel

                    if exhaustive_pkg_df is not None:
                        exhaustive_pkg_df = exhaustive_pkg_df.append(pkg_frame)
                    else:
                        exhaustive_pkg_df = pkg_frame
                # pylint: disable=broad-except
                except Exception as e:
                    msg_ = "FetchPackageView: Unsupported {} {}".format(each_kernel,
                                                                        str(e))
                    current_app.logger.warn(msg_)
                    current_app.logger.error(str(traceback.format_exc()))

            python_pkg_json = exhaustive_pkg_df.to_json(orient='records')
            _total_py_package = exhaustive_pkg_df[exhaustive_pkg_df["type"] == "Python"].shape[0]
            _total_r_package = exhaustive_pkg_df[exhaustive_pkg_df["type"] == "R"].shape[0]
        # pylint: disable=broad-except
        except Exception as e:
            python_pkg_json = "{}"
            current_app.logger.warn("FetchPackageView: {}".format(str(e)))
            current_app.logger.error(str(traceback.format_exc()))

        return jsonify(packages=json.loads(python_pkg_json),
                       total_py_package=_total_py_package,
                       total_r_package=_total_r_package
                       ), 200


scheduler_api.add_url_rule('/v1/spawner/package/<string:pod_name>/<string:container_name>/fetch',
                           view_func=FetchPackageView.as_view('fetch_package_view'))


class JOBCRUDView(MethodView):
    """
    DeleteJobView kills the specified job.
    """
    methods = ['DELETE', 'GET']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)
        self.batch_client = client.BatchV1Api()

        self.job_name = None
        self.grace_period = None
        self.propagation_policy = None
        self.namespace = None

    def stream_status(self,
                      testing: bool = False):
        """
        Streams Status of The Job
        :return:
        """
        status_, api_response = "UNKNOWN", "None"
        sleep_ = 5
        while True:
            try:
                api_response = self.batch_client.read_namespaced_job_status(
                    name=self.job_name,
                    namespace=self.namespace)
                if api_response.status.succeeded is not None:
                    status_ = "SUCCEEDED"
                elif api_response.status.failed is not None:
                    status_ = "FAILED"
                elif api_response.status.active is not None:
                    status_ = "ACTIVE"
                time.sleep(sleep_)

            # pylint: disable=broad-except
            except Exception as e:
                status_ = "NOTALIVE"
                current_app.logger.error("JOBStatusView: {}".format(str(e)))
            if testing:
                return "data: test\n\n"
            yield "data: {}\n\n".format(dict(status=status_, resp=api_response))

    @log_decorator
    @swag_from("swags/get_k8_jobs.yaml")
    def get(self,
            job_name: str) -> Dict[str, str]:
        """
        This Method Will Return Status of Job

        :param job_name: job name
        :return: Dict(status=status)
        """
        _status_code = 200

        self.job_name = job_name
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
        _test = request.args.get('test', False)
        if _test and _test.lower() == "true":
            _test = True
        elif _test and _test.lower() == "false":
            _test = False

        current_app.logger.info(f"JOBStatusView: {self.job_name} - Grace: {self.grace_period}")

        return Response(
            stream_with_context(self.stream_status(_test)),
            content_type="text/event-stream",
            mimetype="text/event-stream",
            headers={"Connection": "keep-alive"},
        )

    @log_decorator
    @swag_from("swags/delete_k8_jobs.yaml")
    def delete(self,
               job_name: str) -> Tuple[Any, int]:
        """
        This method will delete the job
        :param job_name: Name of the kubernetes job
        :return: Dict[status]
        """
        _status_code = 200

        self.job_name = job_name
        self.grace_period = int(request.args.get('grace_period', 5))

        _prop = request.args.get('propagation_policy', 'Foreground')
        self.propagation_policy = str(_prop).strip().title()
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]

        current_app.logger.info(f"DeleteJobView: {self.job_name} - Grace: {self.grace_period}")
        try:
            api_response = self.batch_client.delete_namespaced_job(
                name=self.job_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(
                    propagation_policy=self.propagation_policy,
                    grace_period_seconds=self.grace_period))
        # pylint: disable=broad-except
        except Exception as e:
            _status_code = 500
            api_response = str(e)
            current_app.logger.error("DeleteJobView: {}".format(str(e)))

        return jsonify(response=json.loads(json.dumps(api_response))), _status_code


scheduler_api.add_url_rule('/v1/spawner/jobs/<string:job_name>',
                           view_func=JOBCRUDView.as_view('delete_job_view'))


class JOBPODView(MethodView):
    """
    JOBPODView performs pod job pod specific operations.
    """
    methods = ['GET']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)
        self.batch_client = client.BatchV1Api()

        self.job_name = None
        self.namespace = None

    @log_decorator
    @swag_from("swags/get_job_pod_name.yaml")
    def get(self,
            job_name: str) -> Tuple[Any, int]:
        """
        This Method Will Return Job Pod Name

        :param job_name: job name
        :return: Dict(status=status)
        """
        _status_code = 200

        self.job_name = job_name
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
        resp = self.api_instance.list_namespaced_pod(self.namespace,
                                                     label_selector="job-name=" + self.job_name)

        current_app.logger.info(f"JOBPODView: {self.job_name}")

        return jsonify(details=f"{resp}"), _status_code


scheduler_api.add_url_rule('/v1/spawner/jobs/<string:job_name>/pods',
                           view_func=JOBPODView.as_view('job_pod_view'))


class ConsoleView(MethodView):
    """
    ConsoleView View provides interpreters for shell commands.
    """
    methods = ['POST']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)
        self.stream_watcher = watch.Watch()

        self.pod_name = None
        self.container_name = None
        self.namespace = None
        self.payload = None

    @swag_from("swags/exec_console_commands.yaml")
    def post(self,
             pod_name: str,
             container_name: str) -> Tuple[Any, int]:
        """
        This method will fetch all the logs from the log central container
        :param pod_name: pod_name
        :param container_name: container_name
        :return: Dict Result
        """

        self.pod_name = pod_name
        self.container_name = container_name
        self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
        self.payload = request.get_json()

        current_app.logger.info(f"ConsoleView: Command {self.payload['command']}")

        cmd_ = k8_stream(self.api_instance.connect_post_namespaced_pod_exec,
                         self.pod_name,
                         self.namespace,
                         container=self.container_name,
                         stderr=True,
                         stdin=True,
                         tty=True,
                         stdout=True,
                         command=[self.payload["command"]])

        return jsonify(output=cmd_), 200


scheduler_api.add_url_rule('/v1/spawner/console/<string:pod_name>/<string:container_name>',
                           view_func=ConsoleView.as_view('console_view'))


class JobPodDetailsForKYDRunHistory(MethodView):
    """
    JOBPODView performs pod job pod specific operations.
    """
    methods = ['POST']

    def __init__(self):
        config.load_incluster_config()
        self.api_client = client.ApiClient()
        self.api_instance = client.CoreV1Api(self.api_client)
        self.batch_client = client.BatchV1Api()

        self.job_name = None
        self.namespace = None

    @log_decorator
    @swag_from("swags/get_job_pod_for_run_history_and_update.yaml")
    def post(self, job_name: str) -> Tuple[Any, int]:
        """
        This Method Will Return Job Pod Name
        :param job_name: job name
        :return: Dict(status=status)
        """
        try:
            _status_code = 200
            payload = request.get_json()
            current_app.logger.info(f"\n payload: {payload}\n")
            id = payload['id']
            self.model_id = payload['model_id']
            self.version_id = payload['version_id']
            self.job_name = job_name
            self.namespace = current_app.config["KUBERNETES_NAMESPACE"]
            pod_name = ""
            snapshot_name = ""
            resp = self.api_instance.list_namespaced_pod(self.namespace,
                                                         label_selector="job-name=" + self.job_name)
            init = None
            running = None
            completed = None
            item = resp.items
            if len(item) > 0:
                item_0 = item[0]
                phase = item_0.status.phase
                message = str(item_0.status.conditions[0].message)
                pod_name = item_0.metadata.name
                if phase == "Pending":
                    init = True
                    if "Insufficient" in message:
                        msg = "KYD execution is pending due to insufficient memory and CPU, Try with low resource."
                    else:
                        msg = f"KYD execution is pending due to following issue : - {message}"
                elif phase == "Running":
                    init = True
                    running = True
                    msg = "Running"
                elif phase == "Succeeded":
                    init = True
                    running = True
                    completed = True
                    msg = "Completed Successfully."
                else:
                    init = True
                    running = True
                    completed = False
                    msg = "KYD Execution Failed."
            else:
                init = False
                running = False
                completed = False
                msg = "KYD Execution Failed, Unable To Start POD"

            request_url = "{}/v1/ml-model/{}/version/{}/kyd/history".format(current_app.config["MOSAIC_AI_SERVER"],
                                                                            self.model_id, self.version_id)
            request_data = {"job_name": self.job_name}
            get_response = requests.get(request_url, params=request_data, json=request_data, headers=request.headers)
            get_response = get_response.json()
            if len(get_response) > 0:
                get_data = get_response[0]
                current_app.logger.info(f"\nget_data : {get_data}\n")
                snapshot_name = get_data.get("snapshot_name", "")
            json_data = {
                "init": init,
                "running": running,
                "completed": completed,
                "message": msg,
                "pod_name": pod_name,
                "job_name": self.job_name,
                "id": id,
                "snapshot_name": snapshot_name
            }

            post_response = requests.post(request_url, json=json_data, headers=request.headers)
            post_response = post_response.json()
            current_app.logger.info(f"\npost_response: {post_response}\n")
            params = {"id": id}
            get_response = requests.get(request_url, params=params, json=params, headers=request.headers)
            get_response = get_response.json()
            return jsonify(msg=msg, data=get_response), _status_code
        except Exception as e:
            _status_code = 500
            print("_status_code  teste error ", str(e))
            current_app.logger.info("\nJobPodDetailsForKYDRunHistory: {}".format(str(e)))
            return jsonify(msg="Something went wrong"), _status_code


scheduler_api.add_url_rule('/v1/spawner/jobs/<string:job_name>/pods/details',
                           view_func=JobPodDetailsForKYDRunHistory.as_view('get_job_details'))
