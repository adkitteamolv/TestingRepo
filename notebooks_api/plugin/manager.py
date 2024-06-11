#! -*- coding: utf-8 -*-
"""Plugin manager module"""

import logging
import os
import shutil
import zipfile
from flask import current_app as app, g
from sqlalchemy import text
import requests

from mosaic_utils.ai.headers.utils import generate_headers
from .models import CustomPlugins, db, CustomPluginsSettings
from .exceptions import ErrorCodes
from .constants import ENABLED, ResponseMessages, MODELS_PATH, NOTEBOOKS_PATH, RECIPE_PATH, DATA_PATH, SNAPSHOT_PATH, \
    RPluginMetadata, MosaicAI
from notebooks_api.notebook.manager import create_token
from ..utils.exceptions import PluginException
from ..constants import MonitorStatus

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.plugin")


def register_plugin(plugin_data):
    """
    register a new plugin
    """
    plugin = check_plugin_name_available(plugin_data["name"])

    if not plugin:
        return ErrorCodes.ERROR_0007
    # create plugin
    try:
        plugin_data = CustomPlugins(
            category=plugin_data["category"],
            name=plugin_data["name"],
            description=plugin_data["description"],
            type=plugin_data["type"],
            plugin_type=plugin_data["plugin_type"],
            status=plugin_data["status"],
            icon=plugin_data["icon"],
            width=plugin_data["width"],
            height=plugin_data["height"],
            color=plugin_data["color"],
            thumbnail=plugin_data["thumbnail"],
            multiInputNode=plugin_data["multiInputNode"],
            nodeBackgroundColor=plugin_data["nodeBackgroundColor"],
            input_form_type=plugin_data["input_form_type"],
            input_parameter_json=plugin_data["input_parameter_json"],
            input_parameter_file_name=plugin_data["input_parameter_file_name"],
            base_image_type=plugin_data["base_image_type"],
            plugin_code_source=plugin_data["plugin_code_source"],
            valid_sections=plugin_data["valid_sections"],
            execution_command=plugin_data["execution_command"],
            alert_parameters=plugin_data["alert_parameters"],
            created_by=g.user["mosaicId"],
            updated_by=g.user["mosaicId"],
        )

        db.session.add(plugin_data)
        db.session.commit()
        return plugin_data.as_dict()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ErrorCodes.ERROR_0003


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
        url = app.config["MONITOR_URL"] + "/monitor/jobinstance-status"
        resp = requests.put(url, data=querystring, headers=headers)
        log.info("Response Text - %s - Code %s", resp.text, resp.status_code)
        resp.raise_for_status()
    except Exception as ex:
        log.exception(ex)


def get_plugin_input_data(filter_value):
    """
    get plugin input data
    """
    try:
        plugin_data = None
        query = db.session.query(CustomPluginsSettings.id,
                                 CustomPluginsSettings.advanceSettings.
                                 label("input_parameter_json"),
                                 CustomPlugins.input_form_type,
                                 CustomPlugins.input_parameter_file_name,
                                 CustomPlugins.alert_parameters) \
            .join(CustomPlugins, CustomPlugins.id == CustomPluginsSettings.plugin_id) \
            .filter(CustomPluginsSettings.plugin_id == filter_value['plugin_id'])

        for i in filter_value:
            query = query.filter(text("object_info->>'" + i + "'='" + filter_value[i] + "'"))

        plugin_data = query.first()


        if not plugin_data:
            plugin_data = db.session.query(CustomPlugins.input_form_type,
                                           CustomPlugins.input_parameter_file_name,
                                           CustomPlugins.input_parameter_json,
                                           CustomPlugins.alert_parameters) \
                .filter(CustomPlugins.id == filter_value['plugin_id']).first()

        db.session.commit()
        return plugin_data._asdict()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        return ErrorCodes.ERROR_0008


def get_plugin_data_using_cpi(custom_plugin_id, plugin_id):
    """
    get plugin data using custom plugin id
    """
    try:
        query = db.session.query(CustomPluginsSettings.id,
                                 CustomPluginsSettings.advanceSettings.
                                 label("input_parameter_json"),
                                 CustomPlugins.input_form_type,
                                 CustomPlugins.input_parameter_file_name,
                                 CustomPlugins.alert_parameters) \
            .join(CustomPlugins, CustomPlugins.id == CustomPluginsSettings.plugin_id) \
            .filter(CustomPluginsSettings.id == custom_plugin_id)

        plugin_data = query.first()

        if not plugin_data:
            plugin_data = db.session.query(CustomPlugins.input_form_type,
                                           CustomPlugins.input_parameter_file_name,
                                           CustomPlugins.input_parameter_json,
                                           CustomPlugins.alert_parameters) \
                .filter(CustomPlugins.id == plugin_id).first()

        db.session.commit()
        return plugin_data._asdict()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        raise PluginException(msg_code="PLUGIN_ERROR_0001")


def switch_plugin_status(plugin):
    """
    Method to hide or show plugin base on status value
    """

    try:
        result = db.session.query(CustomPlugins).filter(CustomPlugins.id == plugin['id']).update(
            {"status": plugin['status']})
        db.session.commit()

        return ResponseMessages.SWITCH.format(plugin['status']) if result else ErrorCodes.ERROR_0008
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ErrorCodes.ERROR_0003


def update_plugin_data(plugin_data):
    """
    Method to update plugin data
    """
    try:
        db.session.query(CustomPlugins) \
            .filter(CustomPlugins.id == plugin_data['id']) \
            .update(plugin_data)
        db.session.commit()

        return plugin_data
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ErrorCodes.ERROR_0003


def delete_plugin(plugin):
    """
    Method to hide or show plugin base on status value
    """

    try:
        delete_all = (
            db.session.query(CustomPlugins)
            .filter(CustomPlugins.id == plugin['id'])
        )

        delete_all.delete()
        db.session.commit()

        return ResponseMessages.DELETE_PLUGIN
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ErrorCodes.ERROR_0004


def get_plugin_list(section):
    """
    Method to get the list of available plugins
    """
    if section == "all":
        plugin_data = db.session \
            .query(CustomPlugins.category, CustomPlugins.name, CustomPlugins.width,
                   CustomPlugins.height, CustomPlugins.color, CustomPlugins.type,
                   CustomPlugins.status, CustomPlugins.icon, CustomPlugins.id) \
            .filter(CustomPlugins.status == ENABLED) \
            .all()
    else:
        plugin_data = db.session \
            .query(CustomPlugins.category, CustomPlugins.name, CustomPlugins.width,
                   CustomPlugins.height, CustomPlugins.color, CustomPlugins.type,
                   CustomPlugins.status, CustomPlugins.icon, CustomPlugins.id) \
            .filter(CustomPlugins.status == ENABLED) \
            .filter(CustomPlugins.valid_sections == section) \
            .all()

    plugin_data = [row._asdict() for row in plugin_data]
    return plugin_data


def check_plugin_name_available(plugin_name):
    """
    Args:
        plugin_name (str):

    Returns:
        True if name is available else False
    """
    plugin_data = (
        db.session.query(CustomPlugins.name)
        .filter(CustomPlugins.name == plugin_name)
        .first()
    )

    if plugin_data is None:
        return True

    return False


def save_plugin_data(plugin_data):
    """
    Save plugin user data
    """
    # save data
    try:
        query = db.session.query(CustomPluginsSettings) \
            .filter(CustomPluginsSettings.plugin_id == plugin_data['object_info']["plugin_id"])

        for i in plugin_data['object_info']:
            query = query.filter(text("object_info->>'" + i + "'='" + plugin_data['object_info'][i] + "'"))

        query_result = query.update({"advanceSettings": plugin_data["advanceSettings"]}, synchronize_session=False)
        result = query.first()

        if query_result == 0:
            result = CustomPluginsSettings(
                plugin_id=plugin_data['object_info']["plugin_id"],
                object_info=plugin_data["object_info"],
                advanceSettings=plugin_data["advanceSettings"]
            )

            db.session.add(result)
        db.session.commit()
        return {"custom_plugin_id": result.id}
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ErrorCodes.ERROR_0003


def parse_custom_input_json(input_json):
    """
    Parse user filled advance_Settings custom json
    Param:
        input_json
    Return:
        parsed_dict
    """
    try:
        parsed_dict = {}
        for elem in input_json['fields']:
            if elem.get("refract_source") in ["model", "notebook"]:
                parsed_dict[elem.get("field_id")] = elem.get("field_value")

        key_list = []
        value_list = []

        def parse_nested_json(data):
            """
            General nested json parsing login, logic can be improved further
            """
            for key, value in data.items():
                if str(key) in ['field_id']:
                    key_list.append(str(value))
                elif str(key) in ['field_value']:
                    value_list.append(str(value))

                if isinstance(value, dict):
                    parse_nested_json(value)
                elif isinstance(value, list):
                    for val in value:
                        if isinstance(val, str):
                            pass
                        elif isinstance(val, list):
                            pass
                        else:
                            parse_nested_json(val)
            return dict(zip(key_list, value_list))

        parsed_dict.update(parse_nested_json(input_json))
        return parsed_dict
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(f"Exception in parse_custom_input_json: {ex}")


def get_execute_command(plugin_code_source, recipe_run_command, log_path):
    """
    Can be used to run plugin recipe for different flavors,
    Can add the implementation here.
    Args:
        plugin_code_source:
        log_path:
        recipe_run_command:
    Returns:
        execution_command
    """
    terminate_flag = 'if [ ${PIPESTATUS[0]} -ne 0 ]; then Terminate=1; fi;'
    execution_command = f"echo \"======*$(date '+%d/%m/%Y %H:%M:%S')*======\" | tee -a {log_path}/central.log; \n" \
                        f". {NOTEBOOKS_PATH}/plugin_installation_script.sh 2>&1 | tee -a {log_path}/central.log; \n" \
                        f"cd /tmp{plugin_code_source}; \n" \
                        f"pwd | tee -a {log_path}/central.log; \n" \
                        f". init_script.sh 2>&1 | tee -a {log_path}/central.log; \n" \
                        f"echo ===== Plugin Recipe Execution START: " \
                        f"$(date '+%d/%m/%Y %H:%M:%S')  ===== | tee -a {log_path}/central.log; \n" \
                        f"{recipe_run_command} 2>&1 | tee -a {log_path}/central.log; \n {terminate_flag} \n" \
                        f"echo ===== Plugin Recipe Execution END: " \
                        f"$(date '+%d/%m/%Y %H:%M:%S')  ===== | tee -a {log_path}/central.log;"
    log.debug(f"execution_command: {execution_command}")
    return execution_command


def get_init_command(parsed_dict, log_path):
    """
    Can be used to have plugin recipe from different sources such as gitlab,
    Implementation can be added here.
    Args:
        parsed_dict:
        log_path:

    Returns:
        init_command
    """
    init_command = f"echo \"starting init-container - $(date '+%d/%m/%Y %H:%M:%S')\"; \n" \
                   f"mkdir -p {log_path}; \n" \
                   f"touch {log_path}/central.log {log_path}/healthy {log_path}/unhealthy; \n"
    # getting required notebook in pod
    if parsed_dict.get("notebook"):
        init_command = init_command + \
                       f"python script.py 2>&1 | tee -a {log_path}/central.log || true; \n" \
                       f"cp -r /git/notebooks/* {NOTEBOOKS_PATH} 2>&1 | tee -a {log_path}/central.log || true; \n"
    plugin_installation_command = get_plugin_install_command()
    init_command += f"echo '{plugin_installation_command}' > {NOTEBOOKS_PATH}/plugin_installation_script.sh 2>&1 | tee -a {log_path}/central.log || true; \n"
    init_command += f"echo \"ending init-container - $(date '+%d/%m/%Y %H:%M:%S')\"; \n"
    log.debug(f"init_command: {init_command}")
    return init_command

def get_plugin_install_command():
    install_script = '''
#!/bin/bash
sudo mkdir -p /tmp/custom_plugin
sudo chmod -R 777 /tmp/custom_plugin
pip install $package_name==$package_version -i $package_index_url  -t "/tmp/custom_plugin" --upgrade
'''
    return install_script


def update_env_variables(instance_id, plugin_code_source):
    """
    Used to add env variables in plugin pod
    Args:
        instance_id:
        plugin_code_source:
    Returns:
        env dict
    """
    env = {
        "output_path": SNAPSHOT_PATH.format(instance_id),
        "data_path": DATA_PATH,
        "notebooks_path": NOTEBOOKS_PATH,
        "app_path": plugin_code_source,
        "PROJECT_ID": g.user['project_id'],
        "CONNECTOR_PYTHON_HOST": app.config["CONNECTOR_PYTHON_HOST"],
        "CONNECTOR_PYTHON_PORT": app.config["CONNECTOR_PYTHON_PORT"],
        "PYTHONPATH": f":/tmp{plugin_code_source}:/tmp/pip_packages",
        "TOKEN": create_token(),
        "MOSAIC_AI_SERVER": app.config["MOSAIC_AI_SERVER"]
    }
    return env


def data_upload_file(path, file):
    """
    This method is used for uploading client file to our destination location
    :param path
    :param file
    :return:
    """
    target_dir = RECIPE_PATH.format(app.config['NOTEBOOK_MOUNT_PATH'], app.config['MINIO_DATA_BUCKET'])

    chunk_size = 1024 * 1024  # 1 MB

    destination_path = os.path.join(target_dir, path)
    file_name = os.path.join(destination_path, file.filename)

    if os.path.exists(destination_path):
        shutil.rmtree(destination_path)
    os.makedirs(destination_path)

    with open(file_name, 'wb') as f:
        while True:
            data = file.read(chunk_size)
            if not data:
                break
            f.write(data)

    with zipfile.ZipFile(file_name, 'r') as zip_ref:
        zip_ref.extractall(destination_path)
    os.unlink(file_name)

    return ResponseMessages.RECIPE_UPDATE


def get_package_installation_path(model_id,version_id,kernal_type):
    env = {}
    if kernal_type and kernal_type.lower() == "python":
        venv_path = os.path.join("/packages", "Python", str(model_id), str(version_id.split("-")[0]))
        env['PYTHONPATH'] = "$PYTHONPATH" + ":/tmp/pip_packages:" + venv_path
        env["model_id"] = str(model_id)
        env["version_id"] = str(version_id)
        
    elif kernal_type and kernal_type.lower() in ['r','rstudio']:
        venv_path = os.path.join("/packages", "R", str(model_id), str(version_id.split("-")[0]))
        env['R_PACKAGE_DIR'] = str(venv_path)
        env['R_PACKAGE_REPO'] = RPluginMetadata.R_PACKAGE_REPO
        env["model_id"] = str(model_id)
        env["version_id"] = str(version_id)
    
    return env


def additional_plugin_info(plugin_info, model_details, plugin_docker_url, headers):
    env_info = {}
    try:
        if plugin_info.model_required:
            model_id = [item["field_value"] for item in model_details["model_details"] if item["field_id"]=="model_id"][0]
            version_id = [item["field_value"] for item in model_details["model_details"] if item["field_id"]=="version_id"][0]
            docker_image_url = [item["field_docker_image_url"] for item in model_details["model_details"] if item["field_id"]=="version_id"][0]
            kernal_type = [item["field_kernel_type"] for item in model_details["model_details"] if item["field_id"]=="version_id"][0]
            env_info = get_package_installation_path(model_id,version_id,kernal_type)
            env_info["package_name"] = plugin_info.package_name
            env_info["package_version"] = plugin_info.package_version
            env_info["package_index_url"] = app.config["PYPI_URL"]
            try:
                request_url = app.config["MOSAIC_AI_SERVER"] + MosaicAI.MODEL_META.format(model_id, version_id)
                response = requests.get(request_url, headers=headers)
                model_meta = response.json()
                env_info["MODEL_FLAVOUR"] = model_meta['flavour']
            except Exception as e:
                log.exception(e)
            return docker_image_url,env_info
        else:
            env_info["package_name"] = plugin_info.package_name
            env_info["package_version"] = plugin_info.package_version
            env_info["package_index_url"] = app.config["PYPI_URL"]
            return plugin_docker_url,env_info
        
    except Exception as msg:
        print(msg)
        raise Exception("additional plugin info fetching failed")
