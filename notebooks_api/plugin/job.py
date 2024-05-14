#! -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
""" job associated with the plugin module """

import logging
import json
from flask import g, current_app as app
import requests

from mosaic_utils.ai.headers.utils import generate_headers
from notebooks_api.resource.models import Resource
from notebooks_api.spawner.job import ExecuteJob
from .models import CustomPlugins, CustomPluginsSettings, PluginDockerImage, db
from .manager import parse_custom_input_json, get_execute_command, get_init_command, update_env_variables,additional_plugin_info
from .constants import DATA_PATH, NOTEBOOKS_PATH, SNAPSHOT_PATH
from ..notebook.manager import prepare_node_affinity_options, get_input_params
from ..notebook.decorators import validate_subscriber
from ..data_files.manager import get_project_resource_quota, get_base_path, check_and_create_directory
log = logging.getLogger("notebooks_api.plugin")


class ExecutePlugin:
    """
    Execute plugin class
    Param:
        plugin_id: plugin id from UI
        instance_id: instance id from monitor
        name: plugin name from UI
        resource_id: resource id from UI
        project_id: project id
    """

    def __init__(self, user, data):
        self.data = data
        self.headers = generate_headers(
            userid=user["mosaicId"],
            email=user["email_address"],
            username=user["first_name"],
            project_id=user["project_id"]
        )

    @validate_subscriber
    def execute_plugin(self, subscriber_info=None):
        """
        Execute notebook module
        Returns:
            jobName,
            applicationName,
            message
        """
        # Check for input_params
        try:
            log.debug(f"Inside execute_plugin\nSubscriber info: {subscriber_info}")

            # getting required details from DB
            custom_plugin_details = CustomPlugins.query.get(self.data["plugin_id"])
            base_image_type = custom_plugin_details.base_image_type
            plugin_code_source = custom_plugin_details.plugin_code_source
            recipe_run_command = custom_plugin_details.execution_command
            custom_plugin_settings = db.session.query(CustomPluginsSettings)\
                .filter(CustomPluginsSettings.plugin_id == self.data["plugin_id"])\
                .filter(CustomPluginsSettings.id == self.data["custom_plugin_id"]).first()
            advance_settings = custom_plugin_settings.advanceSettings
            docker_image_details = db.session.query(PluginDockerImage).filter(
                PluginDockerImage.base_image_type == base_image_type).first()
            docker_image_url = docker_image_details.docker_url
            resources = Resource.query.get(self.data.get("resource_id"))

            log.debug(f"advance_settings fetched from DB: {advance_settings}\n"
                      f"plugin_code_source path: {plugin_code_source}\n")

            # parsing custom input json
            parsed_dict = parse_custom_input_json(advance_settings)
            log.info(f"advance_settings parsed: {parsed_dict}")

            # create data and snapshot path if not present
            data_path = get_base_path(project_id=g.user['project_id'])
            snapshot_path = app.config["NOTEBOOK_MOUNT_PATH"] + app.config[
                "MINIO_DATA_BUCKET"] + "/" + f"{g.user['project_id']}/{g.user['project_id']}-Snapshot"
            check_and_create_directory(data_path)
            check_and_create_directory(snapshot_path)

            model_details = {k:v for d in advance_settings.get('fields', {}) for k, v in d.items()}
            docker_image_url, plugin_env = additional_plugin_info(custom_plugin_details,model_details,docker_image_url,
                                                                  self.headers)


            # updating env variables
            env_variables = get_input_params(None, None, self.headers, self.data['project_id'], None)
            env_variables.update({k: json.dumps(v) for d in advance_settings.get('fields', {}) for k, v in d.items()})
            env_variables.update(parsed_dict)
            env_variables.update(update_env_variables(self.data.get('instance_id'), plugin_code_source))
            env_variables.update(plugin_env)
            log.debug(f"env_variables: {env_variables}")

            # getting plugin code and creating init container command
            self.data["init_command"] = get_init_command(parsed_dict,
                                                         SNAPSHOT_PATH.format(self.data.get('instance_id')))

            # creating run command for plugin container
            self.data["execution_command"] = get_execute_command(plugin_code_source,
                                                                 recipe_run_command,
                                                                 SNAPSHOT_PATH.format(self.data.get('instance_id')))

            # Check if project resource quota exceeds
            project_quota, consumed_quota = get_project_resource_quota(
                g.user['project_id'], app.config["CONSOLE_BACKEND_URL"], self.headers)
            resource_quota_full = bool(project_quota < consumed_quota)
            job_data = {
                "docker_url": docker_image_url,
                "cpu": resources.cpu,
                "memory": resources.mem,
                "resource_extra": resources.extra,
                "execution_command": self.data["execution_command"],
                "init_command": self.data["init_command"],
                "node_affinity_options": prepare_node_affinity_options(),
                "subscriber_info": subscriber_info,
                "job_name": self.data["job_name"],
                "instance_id": self.data.get("instance_id"),
                "env": env_variables,
                "resource_quota_full": resource_quota_full,
                "plugin_id": self.data['plugin_id']
            }
            execute_jobs = ExecuteJob(job_data)
            status, job_name = execute_jobs.execute_job()
            log.info(f"response execute-job, response_status: {status}, job_name: {job_name}")

            if status == "Fail":
                message = "Failed"
                job_name = "Job not created"
                # rolling back the transaction on failure
                db.session.rollback()
            else:
                # committing to database as entire execution has completed successfully
                db.session.commit()
                message = "Success"

            return {
                "jobName": job_name,
                "applicationName": None,
                "message": message
            }
        except Exception as ex:
            log.exception(ex)
            db.session.rollback()
