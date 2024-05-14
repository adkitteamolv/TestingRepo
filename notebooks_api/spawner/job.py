# -*- coding: utf-8 -*-

"""Job module for mosaic kubespawner"""
import json
from flask import current_app, g
from mosaic_utils.ai.k8.utils import create_job_name
# from notebooks_api import get_application
from .manager import (
    create_environment_variables,
    new_create_job_manifest,
    create_job,
    replace_special_chars_with_ascii,
    create_package_installation,
    retry_create_namespaced_job,
    get_env_value,
    package_target_path,
    get_affinity_config,
    create_job_manifest,
    create_env_var

)
from notebooks_api.utils.exceptions import StatusCodes
from .validators import check_async_value
from .constants import KernelType
from .sparkbatch.sparkbatch import SparkLoader


# pylint: disable=too-many-instance-attributes, too-many-locals, too-few-public-methods, too-many-statements, too-many-branches
class ExecuteScheduledJob:
    """Executes scheduled jobs in mosaic kuubespawner"""

    def __init__(self, data):
        self.file_path = data.get("file_path")
        self.pip_packages = data.get("pip_packages")
        self.conda_packages = data.get("conda_packages")
        self.repo_name = data.get("repo_name")
        self.env = data.get("env")
        self.init_script = data.get("init_script")
        self.cran_packages = data.get("cran_packages")
        self.kernel_type = data.get("kernel_type")
        self.async_strategy = check_async_value(data)
        self.docker_url = data.get("docker_url")
        self.cpu = data.get("cpu")
        self.memory = data.get("memory")
        self.resource_extra = data.get("resource_extra")
        self.execution_command = data.get("execution_command")
        self.bearer = data.get("bearer_token")
        self.docker_image_id = data.get("docker_image_id")
        self.node_affinity_options = data.get("node_affinity_options")
        self.enabled_repo = data.get("enabled_repo")
        self.snapshots = data.get("snapshots")
        self.git_macros_config = data.get("git_macros_config")
        self.subscriber_info = data.get("subscriber_info")
        self.resource_quota_full = data.get("resource_quota_full")
        self.job_name = data.get("job_name")
        self.user_imp_data = data.get("user_imp_data")
        self.instance_id = data.get("instance_id")
        self.version = data.get("version")

        # Preparing the job_name if not exists
        if not self.job_name:
            current_app.logger.debug("Creating job name - since its not present in payload")
            self.job_name = create_job_name(self.file_path)

    def execute_notebook(self):
        """ Create a job for executing the scheduled notebook

        """
        project_id = g.user.get('project_id', self.enabled_repo.get('project_id', self.env.get('PROJECT_ID')))
        if project_id:
            node_affinity = get_affinity_config(project_id, gpu=True) if self.resource_extra in ["nvidia","amd"] else get_affinity_config(project_id)
            if node_affinity:
                self.node_affinity_options = node_affinity

        current_app.logger.debug("Job Name %s", self.job_name)
        # Appending the token to env
        self.env["bearer_token"] = self.bearer
        # Creating environment variables
        # docker_image_name = fetch_docker_image(self.kernel_type, self.async_strategy)
        self.env["MOSAIC_AI_SERVER"] = current_app.config["MOSAIC_AI_SERVER"]
        env_variables, jwt = create_environment_variables(self.env)

        nas_package_dir = ""
        template_id = get_env_value(env_variables, 'template_id')
        base_docker_image_name = get_env_value(env_variables, 'base_docker_image_name')
        nas_location = current_app.config['TEMPLATE_NAS_DIRECTORY']
        if self.kernel_type in [KernelType.python, KernelType.vscode_python, KernelType.spark]:
            current_app.logger.error("#Inside Python kernel : ")
            path_list = ['', package_target_path(nas_location, base_docker_image_name, template_id, self.version),
                         "/tmp/pip_packages"]
            nas_package_dir = package_target_path(nas_location, base_docker_image_name, template_id, self.version)
            pythonpath_dict = {"name": 'PYTHONPATH', "value": ":".join(path_list)}
            nas_package_dir_dict = {"name": 'nas_package_dir', "value": nas_package_dir}
            env_variables.insert(0, nas_package_dir_dict)
            env_variables.insert(0, pythonpath_dict)
        elif self.kernel_type in [KernelType.rstudio_kernel]:
            nas_package_dir = package_target_path(nas_location, base_docker_image_name, template_id, self.version)
            r_package_dir = {"name": 'R_PACKAGE_DIR',
                             "value": nas_package_dir}
            cran_packages = {"name": 'CRAN_PACKAGES',
                             "value": json.dumps(self.cran_packages)}
            env_variables.insert(0, r_package_dir)
            env_variables.insert(0, cran_packages)
        package_installation = create_package_installation(
            self.kernel_type, self.pip_packages, self.cran_packages,
            self.init_script, self.conda_packages, nas_package_dir, g.user["project_id"],
            log_id=get_env_value(env_variables, 'log_id'),
            experiment_name=get_env_value(env_variables, 'EXPERIMENT_NAME')
        )

        # pylint: disable=logging-too-many-args
        current_app.logger.debug("value of jwt %s", jwt)
        # Fetching docker images
        docker_image_name = self.docker_url
        url = current_app.config["GIT_URL"]
        username = current_app.config["GIT_USERNAME"]
        password = replace_special_chars_with_ascii(str(current_app.config["GIT_ACCESS_TOKEN"]))
        url_parts = url.split("//")
        remote_url = "{0}//{1}:{2}@{3}".format(
            url_parts[0], username, password, url_parts[1]
        )
        metering_info = {"user_id": g.user["mosaicId"],
                         "resource_key": self.subscriber_info["resource_key"],
                         "resource_request": self.subscriber_info["resource_request"],
                         "pod_id": self.job_name,
                         "description": self.job_name,
                         "project_id": g.user["project_id"],
                         "subscriber_id": self.subscriber_info["subscriber_id"]}
        automl_info = {"experiment_recipe_id": self.env['experiment_recipe_id'] \
                        if 'experiment_recipe_id' in self.env else None,
                       "PROJECT_ID": self.env['PROJECT_ID']}

        if self.kernel_type in [KernelType.spark_distributed]:
            # Add class spark loader
            current_app.logger.debug("creating sparkloader object")
            spark_loader_object = SparkLoader(
                self.job_name,
                self.repo_name,
                self.file_path,
                env_variables,
                jwt,
                self.pip_packages,
                self.cpu,
                self.memory,
                self.resource_quota_full,
                self.snapshots
            )
            current_app.logger.debug("calling submit spark app")
            response = spark_loader_object.submit_spark_app()
            current_app.logger.info("status code %s", response.status_code)
            current_app.logger.info("response spark operator %s", response.text)
            if response.status_code == 201:
                status, job_id = "Success", response.json()["metadata"]["name"] + "-driver"
            else:
                status, job_id = "Fail", response.json()
            current_app.logger.debug(f"status: {status}\njob_id: {job_id}")
            return status, job_id


        # Creating Job Manifest
        pod = new_create_job_manifest(
            jwt,
            self.job_name,
            env_variables,
            remote_url,
            self.repo_name,
            template_id,
            docker_image_name,
            self.cpu,
            self.memory,
            self.resource_extra,
            self.execution_command,
            package_installation,
            self.pip_packages,
            self.kernel_type,
            self.file_path,
            self.node_affinity_options,
            self.enabled_repo,
            self.snapshots,
            self.git_macros_config,
            metering_info,
            self.resource_quota_full,
            automl_info,
            self.env,
            self.user_imp_data,
            self.instance_id,
        )

        if self.async_strategy is True:
            try:
                current_app.logger.debug("Inside async true")
                current_app.logger.debug("starting create_namespaced_job")
                retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
                current_app.logger.debug("end create_namespaced_job")
                current_app.logger.debug(StatusCodes.MOSAIC_0002)
                current_app.logger.debug(self.job_name)
                return StatusCodes.MOSAIC_0002, self.job_name
            # pylint: disable=broad-except
            except Exception as ex:
                current_app.logger.error(ex)
                return "Fail", "Fail"

        else:
            status, job_id = create_job(pod, self.job_name)
            return status, job_id


class ExecuteJob:
    """ Executes scheduled job in mosaic kubespawner
        Param:
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

    def __init__(self, data):
        self.docker_url = data.get("docker_url")
        self.cpu = data.get("cpu")
        self.memory = data.get("memory")
        self.resource_extra = data.get("resource_extra")
        self.execution_command = data.get("execution_command")
        self.init_command = data.get("init_command")
        self.node_affinity_options = data.get("node_affinity_options")
        self.subscriber_info = data.get("subscriber_info")
        self.job_name = data.get("job_name")
        self.instance_id = data.get("instance_id")
        self.env = data.get("env")
        self.resource_quota_full = data.get("resource_quota_full")
        self.bearer_token = data.get("bearer_token")
        self.plugin_id = data.get("plugin_id")

    def execute_job(self):
        """
        Create a job for execution
        """

        project_id = g.user.get('project_id')
        if project_id:
            node_affinity = get_affinity_config(project_id, gpu=True) if self.resource_extra in ["nvidia","amd"] else get_affinity_config(project_id)
            if node_affinity:
                self.node_affinity_options = node_affinity

        # Creating environment variables
        env_variables = create_env_var(self.env)

        metering_info = {
                "user_id": g.user["mosaicId"],
                "resource_key": self.subscriber_info["resource_key"],
                "resource_request": self.subscriber_info.get("resource_request"),
                "pod_id": self.job_name,
                "description": self.job_name,
                "project_id": g.user["project_id"],
                "subscriber_id": self.subscriber_info.get("subscriber_id")
            }

        # Creating Job Manifest
        pod = create_job_manifest(
            self.job_name,
            env_variables,
            self.docker_url,
            self.cpu,
            self.memory,
            self.resource_extra,
            self.execution_command,
            self.init_command,
            self.node_affinity_options,
            metering_info,
            self.resource_quota_full,
            self.env,
            self.instance_id,
            self.plugin_id
        )

        current_app.logger.debug(f"pod: {pod}")

        try:
            current_app.logger.info("starting retry_create_namespaced_job")
            retry_create_namespaced_job(current_app.config["KUBERNETES_NAMESPACE"], pod)
            current_app.logger.info(f"end retry_create_namespaced_job, "
                                    f"job_name: {self.job_name}, {StatusCodes.MOSAIC_0002}")
            return StatusCodes.MOSAIC_0002, self.job_name
        # pylint: disable=broad-except
        except Exception as ex:
            current_app.logger.error(ex)
            return "Fail", "Fail"
