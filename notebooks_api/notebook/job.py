""" Notebooks job module """
import logging
import json
import time
import requests

from flask import (
    current_app as app,
    g,
    request,
)
from mosaic_utils.ai.headers.utils import generate_headers
from .decorators import validate_subscriber
from .manager import (
    get_input_params,
    get_envs,
    create_token, get_execute_command, prepare_node_affinity_options,
    register_snapshot, fetch_base_image_details_for_custom_build,
    get_base_image_os,
    base_version_tag
)
from .models import (
    DockerImage,
    db,
    Resource,
)
from .constants import KernelType, ExperimentStyles, NotebookPath
from ..notebook.manager import get_user_impersonation_details
from ..data_files.manager import get_base_path, check_and_create_directory, check_and_create_log_directory, get_project_resource_quota

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


# pylint: disable=too-few-public-methods
class ExecuteNotebook:
    """ Execute notebook class """
    def __init__(self, user, data, async_strategy):
        self.data = data
        self.headers = generate_headers(
            userid=user["mosaicId"],
            email=user["email_address"],
            username=user["first_name"],
            project_id=user["project_id"]
        )
        self.jwt = create_token()
        self.is_scheduled_job = True
        self.async_strategy = async_strategy

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements, line-too-long
    @validate_subscriber
    def execute_notebook(self, subscriber_info=None):
        """Execute notebook module"""
        # Check for input_params
        try:
            log.debug("Inside execute_notebook")
            log.debug("Subscriber info")
            log.debug(subscriber_info)
            env_variables = get_input_params(self.data["docker_image_id"], self.jwt, self.headers, self.data['project_id'], self.is_scheduled_job)

            env_variables.update(get_envs(self.data["docker_image_id"], self.jwt, self.headers, self.data['project_id'], self.is_scheduled_job))
            # Changes done to handle the recipe triggering
            if "auto_ml_trigger" in self.data["input_params"]:
                experiment_style = self.data["input_params"]["experiment_style"]
                if experiment_style in [ExperimentStyles.manual, ExperimentStyles.quick]:
                    # input params provided during recipe trigger
                    input_param_provided = self.data["input_params"]["recipe_param"]
                    # replace the params in template with user provided values
                    env_variables.update(input_param_provided)


            if "input_params" in self.data:
                env_variables.update(self.data["input_params"])
            if "recipe_param" in env_variables:
                env_variables["recipe_param"] = json.dumps(env_variables["recipe_param"])
            if "auto_ml_trigger" in env_variables:
                self.headers.update({"automl_check": "True"})
                env_variables.pop("auto_ml_trigger")
            log.debug(env_variables)
            docker_image_details = DockerImage.query.get(
                self.data["docker_image_id"])

            # Fetching PIP packages and Init-Script for installing in the Scheduled
            # container
            pip_packages_list = docker_image_details.pip_packages
            conda_package_list = docker_image_details.conda_packages
            cran_packages_list = docker_image_details.cran_packages
            git_macros_config = docker_image_details.git_macros_config
            init_script = docker_image_details.init_script
            docker_url = docker_image_details.docker_url
            file_path = self.data['file_path']
            enabled_repo = self.data['enabled_repo']
            project_id = self.data['project_id']

            user_impersonation_flag = app.config['USER_IMPERSONATION_FLAG']
            user_impersonation = bool(user_impersonation_flag and "automl_check" not in self.headers)

            if 'execution_command' not in self.data and 'instance_id' in self.data:
                nb_arguments = self.data.get('nb_arguments')
                instance_id = self.data['instance_id']
                self.data["execution_command"] = get_execute_command(
                    docker_image_details.kernel_type,
                    file_path,
                    project_id,
                    instance_id,
                    enabled_repo,
                    user_impersonation,
                    nb_arguments
                )
            if docker_image_details.kernel_type in ["sas", "sas_batch_cli"]:
                env_variables["DEPLOYMENT_NAME"] = app.config["DEPLOYMENT_NAME"]
            resource_id = self.data["resource_id"]
            resources = Resource.query.get(resource_id)
            if resources.extra != "cpu":
                docker_url = docker_image_details.gpu_docker_url
            snapshot_time = str(self.data.get("instance_id", int(time.time())))

            if self.data.get('output') is None or self.data.get('output') == KernelType.default:
                self.data["output"] = KernelType.snapshot + snapshot_time
            if self.data.get('input') is None or self.data.get('input') == KernelType.default:
                self.data["input"] = KernelType.snapshot + snapshot_time

            if self.data.get('input') == KernelType.slash:
                self.data["input"] = KernelType.input
            snapshots = {}
            snapshots["input"] = self.data["input"]
            snapshots["output"] = self.data["output"]
            base_image_id = docker_image_details.base_image_id if docker_image_details.base_image_id else docker_image_details.id
            version = base_version_tag(base_image_id)
            payload = {
                "file_path": self.data["file_path"],
                "pip_packages": pip_packages_list,
                "cran_packages": cran_packages_list,
                "conda_packages": conda_package_list,
                "repo_name": self.data["recipe_project_id"] if "automl_check" in self.headers else self.data["project_id"],
                "init_script": init_script,
                "kernel_type": docker_image_details.kernel_type,
                "async": self.async_strategy,
                "docker_url": docker_url,
                "cpu": resources.cpu,
                "memory": resources.mem,
                "resource_extra": resources.extra,
                "execution_command": self.data["execution_command"],
                "docker_image_id": self.data["docker_image_id"],
                "node_affinity_options": prepare_node_affinity_options(),
                "enabled_repo": self.data["enabled_repo"],
                "snapshots": snapshots,
                "git_macros_config": git_macros_config,
                "subscriber_info": subscriber_info,
                "job_name": self.data["job_name"],
                "instance_id": self.data.get("instance_id"),
                "version": version
            }

            # Preparing URL
            url = app.config["MOSAIC_KUBESPAWNER_URL"]

            # creating empty folder if it doesnot exist on nfs drive

            # create data and snapshot path if not present
            data_path = get_base_path(project_id=project_id, exp_name=self.data.get("experiment_name", None))
            snaphot_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
                'MINIO_DATA_BUCKET'] + "/" + f'{project_id}/{project_id}-Snapshot/{self.data["output"]}/'

            check_and_create_directory(data_path)
            check_and_create_directory(snaphot_path)

            log_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
                'MINIO_DATA_BUCKET'] + "/" + "log/" + f'{project_id}' + "/" + str(self.data.get("instance_id")) + "/"
            check_and_create_log_directory(log_path)
            env_variables["log_id"] = str(self.data["job_name"])
            env_variables["LOG_DIRECTORY"] = app.config["LOG_DIRECTORY"]
            log.info(str(self.data.get("instance_id")))

            snapshots["container_object"] = {"name": 'NA'}
            register_snapshot(snapshots, g.user["mosaicId"], project_id, self.data["enabled_repo"])
            # call to create token
            log.debug("Call to create token")
            env_variables["PROJECT_ID"] = self.data['project_id']
            # for scheduler backend url is different because scheduler is in
            # different namespace
            env_variables["MOSAIC_AI_SERVER"] = app.config['MOSAIC_AI_SERVER_SCHEDULER']
            env_variables["NOTEBOOKS_API_SERVER"] = app.config['NOTEBOOKS_API_SERVER']
            env_variables["MOSAIC_ID"] = g.user["mosaicId"]
            env_variables["R_PACKAGE_REPO"] = app.config["R_PACKAGE_REPO"]
            env_variables["PYPI_PACKAGE_REPO"] = app.config["PYPI_URL"]
            env_variables["CONDA_PACKAGE_REPO"] = app.config["CONDA_PYTHON_URL"]
            env_variables["CONDA_R_PACKAGE_REPO"] = app.config["CONDA_R_URL"]
            env_variables["repo_id"] = enabled_repo["repo_id"]
            env_variables["repo_name"] = enabled_repo["repo_name"]
            env_variables["branch_name"] = enabled_repo["branch"]
            env_variables["branch_id"] = enabled_repo.get("branch_id", None)
            env_variables["template_id"] = docker_image_details.id
            env_variables["EXPERIMENT_NAME"] = self.data.get("experiment_name")
            env_variables["EXPERIMENT_DETAILS"] = json.dumps(self.data.get("experiment_details"))
            env_variables["MLFLOW_TRACKING_URL"] = app.config.get("MLFLOW_TRACKING_URL", "http://mlflow-server")
            base_image_id = docker_image_details.base_image_id if docker_image_details.base_image_id else docker_image_details.id
            env_variables["os"] = get_base_image_os(base_image_id)
            try:
                env_variables["number_of_executors"] = str(docker_image_details.number_of_executors)
                env_variables["executor_resource_cpu"] = str(docker_image_details.executor_resource.cpu) if docker_image_details.executor_resource else None
                env_variables["executor_resource_mem"] = str(docker_image_details.executor_resource.mem) if docker_image_details.executor_resource else None
            except Exception as ex:
                log.info(f"Exception in reading executor configurations or number of executors, ex: {ex}")

            # Get base image name for custom template
            if docker_image_details.type == "PRE_BUILD":
                env_variables["base_docker_image_name"] = docker_image_details.name if docker_image_details.name != "Spark Distributed" else "Python-3.6"
            elif docker_image_details.type == "CUSTOM_BUILD":
                base_image_details = fetch_base_image_details_for_custom_build(
                    docker_image_details.base_image_id)
                env_variables["base_docker_image_name"] = base_image_details.get('name') if base_image_details.get('name') != "Spark Distributed" else "Python-3.6"

            env_variables['DOCKER_REGISTRY'] = app.config.get("GIT_REGISTRY", "registry.lti-aiq.in:443")
            kernal_type = docker_image_details.kernel_type

            if kernal_type and kernal_type.lower() in [KernelType.sas]:
                env_variables['SAS_WORDIR'] = app.config.get("SAS_TMP_WORDIR", "/output") + "/sas_tmp/"

            # user impersonation
            user_imp_data = None
            if kernal_type and kernal_type.lower() in [KernelType.sas, KernelType.python, KernelType.r,
                                                       KernelType.rstudio, KernelType.jdk11, KernelType.sas_batch_cli, KernelType.vscode_python]:

                if user_impersonation:
                    env_variables['USER_IMPERSONATION'] = "true"
                    env_variables, user_imp_data = get_user_impersonation_details(g.user["mosaicId"], env_variables)

                    if kernal_type and kernal_type.lower() in [KernelType.sas]:
                        env_variables['RUN_MODE'] = app.config['RUN_MODE']
                        env_variables['SASDEMO_HOME'] = NotebookPath.nb_base_path

            payload["env"] = env_variables
            log.debug(env_variables)

            # Check if project resource quota exceeds
            project_quota, consumed_quota = get_project_resource_quota \
                (project_id, app.config["CONSOLE_BACKEND_URL"], self.headers)
            resource_quota_full = bool(project_quota < consumed_quota)
            payload["resource_quota_full"] = resource_quota_full
            payload["user_imp_data"] = user_imp_data

            temp_head = self.headers
            temp_head.update({"bearer_token": self.data["bearer_token"]})
            response = requests.post(url, json=payload, headers=temp_head)
            log.debug(response)

            response_job = response.text
            if response.status_code != 200:
                message = "Failed"
                response_job = "Job not created"
                # rolling back the transaction on failure
                db.session.rollback()
            else:
                # committing to database as entire execution has completed successfully
                db.session.commit()
                message = "Success"
            log.debug(response_job)

            log.debug("Exiting execute_notebook")
            if "automl_check" in temp_head:
                return {
                    "jobName": response_job,
                    "applicationName": None,
                    "message": message,
                    "snapshot_name": snapshots["output"]
                }
            return {
                "jobName": response_job,
                "applicationName": None,
                "message": message
            }
        except Exception as ex:
            log.exception(ex)
            db.session.rollback()

    @staticmethod
    def get_async_strategy(request_, data):
        if "async" not in request_.args and "async" not in data:
            async_strategy = False
        # adding for automl trigger recipe
        elif "async" in data:
            async_strategy = data["async"]
        else:
            async_strategy = request_.args["async"]
            if async_strategy in ['True', 'true']:
                async_strategy = True
            elif async_strategy in ['False', 'false']:
                async_strategy = False
            else:
                raise ValueError("Parameter async need to be boolean !")

        return async_strategy
