"""
Defines functions to perform CRUD operations on version_metadata table.
"""

import json
import logging
import os
import shutil
import tempfile

from flask import current_app
from flask_sqlalchemy import SQLAlchemy

from notebooks_api.utils.file_utils import git_chekout_commit, git_clone, replace_special_chars_with_ascii
from .models import db, Version


def create_version(version):
    """
    Saves given version object in DB
    :param version: Version object
    :return: TRUE if version created successfully else FALSE
    """
    try:
        db.session.add(version)
        db.session.flush()
        db.session.commit()
        return True
    except Exception as ex:
        current_app.logger.exception(ex)
        return False

def get_versions(project_id, component_type, component_id, offset, limit):
    """
    Get data for version for specified component
    :param project_id: Project id.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param component_id: Component id can be flow id, schedule id etc.
    :param offset: Start index
    :param limit: End index
    :return: Version number
    """
    versions = []
    try:
        versions = db.session.query(Version) \
            .filter_by(project_id=project_id) \
            .filter_by(component_type=component_type) \
            .filter_by(component_id=component_id) \
            .order_by(Version.id.desc()) \
            .offset(offset) \
            .limit(limit) \
            .all()
        return json.dumps([version.as_dict() for version in versions])
    except Exception as ex:
        current_app.logger.exception(ex)
        return json.dumps(versions)

def get_version(project_id, component_type, component_id, version_number):
    """
    Get data for version for specified component
    :param component_id: Component id can be flow id, schedule id etc.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param project_id: Project id.
    :param version_number: Version number
    :return: Version number
    """
    version = Version()
    try:
        version = db.session.query(Version) \
            .filter_by(project_id=project_id) \
            .filter_by(component_type=component_type) \
            .filter_by(component_id=component_id) \
            .filter_by(version_number=version_number) \
            .first()
        return version
    except Exception as ex:
        current_app.logger.exception(ex)
        return version

def create_new_version_record(component_id,
                              component_type,
                              project_id,
                              commit_id,
                              version_number,
                              commit_message,
                              data):
    """
    Creates new version for specified component
    :param component_id: Component id can be flow id, schedule id etc.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param project_id: Project id.
    :param commit_id: Commit id.
    :param version_number: Version number
    :param commit_message: Commit message
    :return: Version number
    """
    try:
        version = Version(
            component_type=component_type,
            component_id=component_id,
            project_id=project_id,
            commit_id=commit_id,
            commit_message=commit_message,
            version_number=version_number,
            data=data)
        if create_version(version=version):
            return version_number
        else:
            raise ValueError("Failed saving entry in database")
    except Exception as ex:
        current_app.logger.exception(ex)
        raise ValueError("Failed saving entry in database")

def get_max_version_number(component_id, component_type, project_id):
    """
    Get max version number for specified component
    :param component_id: Component id can be flow id, schedule id etc.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param project_id: Project id.
    :return: Max version number
    """
    try:
        version = db.session.query(Version) \
            .filter_by(project_id=project_id) \
            .filter_by(component_type=component_type) \
            .filter_by(component_id=component_id) \
            .order_by(Version.id.desc()) \
            .first()
        return version.version_number if version is not None else "V0"
    except Exception as ex:
        current_app.logger.exception(ex)
        return "V0"

def get_next_version_number(component_id, component_type, project_id):
    """
    Get next version number for specified component
    :param component_id: Component id can be flow id, schedule id etc.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param project_id: Project id.
    :return: version number
    """
    max_version_number = get_max_version_number(component_id, component_type, project_id)
    return "V" + str(int(max_version_number[1:]) + 1)

def get_version_with_data(project_id, component_type, component_id, version_number, branch):
    """
    Get version for given component id
    :param project_id: Project id.
    :param component_type: Component type can be flow, workflow, schedule etc.
    :param component_id: Component id can be flow id, schedule id etc.
    :param version_number: Version number.
    :return: Version object
    """
    version = {}
    try:
        current_app.logger.info("Fetching version for project=" + project_id + ", component=" +
                      component_type + ", id=" + component_id + ", version number=" +
                      version_number)

        version = get_version(
            project_id=project_id,
            component_type=component_type,
            component_id=component_id,
            version_number=version_number)

        if current_app.config["GIT_STORAGE_TYPE"] == "GIT":
            file_name = component_id + ".json"
            username = current_app.config["GIT_NAMESPACE"]
            password = replace_special_chars_with_ascii(str(current_app.config["GIT_PASSWORD"]))
            git_temp_dir = tempfile.mkdtemp()
            url = "{0}/{1}.git".format(current_app.config["REMOTE_URL"], project_id)
            url_parts = url.split("//")
            remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])

            git_clone(git_temp_dir, remote_url, branch)

            path = git_temp_dir + "/" + component_type + "s"
            if not os.path.exists(path):
                os.makedirs(path)

            git_chekout_commit(git_temp_dir, version.__getattribute__("commit_id"))

            with open(os.path.join(path, file_name), 'r') as temp_file:
                content = temp_file.read()

            response = {
                'data': json.loads(content)
            }

            json_merged = {**json.loads(json.dumps(version.as_dict())), **json.loads(json.dumps(response))}

            if content != '' and os.path.isdir(git_temp_dir):
                shutil.rmtree(git_temp_dir)
            return json.dumps(json_merged)

        json_merged = {**json.loads(json.dumps(version.as_dict()))}
        return json.dumps(json_merged)
    except Exception as ex:
        current_app.logger.exception(ex)
        return json.dumps(version)
