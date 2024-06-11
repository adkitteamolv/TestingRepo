"""Manager for data files"""

import logging
import tempfile
import shutil
import base64
import os
import glob
import codecs
import re
import requests
from requests.exceptions import ConnectionError
import time
import subprocess
import jwt
from flask import current_app as app
from flask import jsonify, g
import pandas as pd
from pathlib import Path
from mosaic_utils.ai.data_files.utils import (
    convert_size,
    convert_into_bytes)
from mosaic_utils.ai.file_utils import check_tar_zip

from .exceptions import ErrorCodes
from mosaic_utils.ai.audit_log.utils import audit_logging
from mosaic_utils.ai.headers.constants import Headers

from ..utils.exceptions import PreviewFileException, MosaicException

from notebooks_api.utils.exceptions import ServiceConnectionError, FetchProjectResourceQuotaError, MosaicException
# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")




def fetch_file_data(temp_dir, filename):
    """Method to fetch file data"""
    file_data = open(f'{temp_dir}/{filename}', 'rb')
    image_string = base64.b64encode(file_data.read())
    request_data = image_string.decode("utf-8")
    return request_data


def check_file_dir(fpath):
    """Method to check file or directory"""
    if os.path.isfile(fpath):
        return "file"
    if os.path.isdir(fpath):
        return "directory"
    return "unknown"


def fetch_files_in_dir(root):
    """Method to fetch files in directory"""
    file_paths = list()
    # pylint: disable=unused-variable
    for path, subdirs, files in os.walk(root):
        for name in files:
            file_paths.append(os.path.join(path, name))
    return file_paths


def data_for_file(file_name, data_files):
    """Method to fetch file data"""
    filename = file_name.split("/")[-1]
    # Creating temporary directory
    temp_dir = tempfile.mkdtemp()

    with open(f'{temp_dir}/{filename}', 'wb') as file_data:
        for data in data_files.stream(32 * 1024):
            file_data.write(data)

    request_data = fetch_file_data(temp_dir, filename)

    # remove directory
    shutil.rmtree(temp_dir)

    return request_data


def add_data_in_temp_dir(data_dict, folder_struct, attachment_name, temp_dir, folder_name):
    """
    This method is used for adding data files and folder in temp directory.
    :param data_dict
    :param folder_struct
    :param attachment_name
    :param temp_dir
    :param folder_name
    :return:
    """

    for key, value in data_dict.items():
        if folder_struct:
            if folder_name:
                request_data_file = f"/{temp_dir}/{folder_name}/{key}"
            else:
                request_data_file = f"/{temp_dir}/{key}"
        else:
            data_name = key.replace(attachment_name, "", 1)
            if folder_name:
                request_data_file = f"/{temp_dir}/{folder_name}/{data_name}"
            else:
                request_data_file = f"/{temp_dir}/{data_name}"

        os.makedirs(os.path.dirname(request_data_file), exist_ok=True)
        file = open(request_data_file, "wb")
        original_file = base64.b64decode(
            value.encode("utf-8")
        )
        file.write(original_file)
        file.close()


def create_zip_remove_temp_dir(temp_dir, folder_name):
    """
    This method is used to create the ZIP file from temporary location in which we have pushed our files,
    Once we make a zip we will delete the temp_dir.
    :param temp_dir
    :param folder_name
    :return:
    """
    zip_dir_name = f'{temp_dir}/{folder_name}'
    log.info("Zip directory name is : " + zip_dir_name)

    shutil.make_archive(zip_dir_name, 'zip', zip_dir_name)
    request_data = codecs.open(zip_dir_name + ".zip", 'rb').read()
    # remove directory
    shutil.rmtree(temp_dir)
    return request_data


def get_zip_data(data_dict, folder_struct, attachment_name):
    """
    Method to get zip data
    :param data_dict
    :param folder_struct
    :param attachment_name
    """
    folder_name = data_dict.pop("folder_name")
    # Creating temporary directory
    temp_dir = tempfile.mkdtemp()
    add_data_in_temp_dir(data_dict, folder_struct, attachment_name, temp_dir, folder_name)

    request_data = create_zip_remove_temp_dir(temp_dir, folder_name)

    return request_data


def fetch_paths(file_path):
    """Method to fetch paths"""
    regex = r'^(.+)\/([^/]+)$'
    extracted_names = re.match(regex, file_path)
    if extracted_names is None:
        return file_path, ""
    return extracted_names.group(1), extracted_names.group(2)


def filter_for_regex(data_files, folder_path):
    """filter for regex"""
    filtered_list = list()
    regex = re.compile(folder_path)
    for item in data_files:
        if regex.match(item[0]["name"]):
            filtered_list.append(item)
    return filtered_list



def data_upload_file(destination_path, file, project_id, uuid, is_eof, file_type, overwrite=False, upload_type="data"):
    """
    This method is used for uploading client file to our destination location
    :param destination_path
    :param file
    :param project_id
    :param uuid
    :param is_eof
    :param file_type
    :param overwrite
    :param upload_type: whether upload file in generic destination path or project data folder
    :return:
    """

    temp_dir = app.config['NOTEBOOK_MOUNT_PATH'] + app.config['MINIO_DATA_BUCKET'] + "/" + f"{uuid}"

    check_and_create_directory(temp_dir)

    if not overwrite or not os.path.exists(f"{temp_dir}/{file.filename}"):
        write_or_append_file_in_temp_location(file, temp_dir)

    if is_eof.lower() == "false":
        return "Chunk writing done, waiting for next chunk!"

    if upload_type and upload_type.lower() == "bucket":
        minio_shared_path = get_base_path("")
    else:
        minio_shared_path = get_base_path(project_id)
    # pylint: disable=too-many-function-args
    if file_type in ['application/zip', 'application/x-zip', 'application/x-zip-compressed', 'application/gzip']:
        new_filename = file.filename.split(".")[0]

        # Check if file is Tar/Zip/File
        if not overwrite or not os.path.exists(minio_shared_path + "/" + new_filename):
            file_type, updated_file_name = check_tar_zip(
                f"{temp_dir}/{file.filename}", temp_dir, file.filename, file_type)
        minio_shared_path = minio_shared_path + destination_path
        minio_shared_path = minio_shared_path.split(".")[0]
        minio_shared_path = minio_shared_path[0:minio_shared_path.rindex("/")]
    else:
        file_type = "file"
        minio_shared_path = minio_shared_path + destination_path

    log.info("Final shared path is : " + minio_shared_path)

    if file_type == "file":
        log.debug("Overwrite value")
        log.debug(overwrite)

        updated_destination_path = file.filename if destination_path == "" else destination_path
        log.info(updated_destination_path)
        minio_shared_path = minio_shared_path[0:minio_shared_path.rindex("/")]
        # Check if same name exists
        if not overwrite:
            if os.path.exists(f"{minio_shared_path}/{file.filename}"):
                raise Exception(ErrorCodes.ERROR_0007)
        else:
            if os.path.exists(f"{minio_shared_path}/{file.filename}"):
                os.remove(f"{minio_shared_path}/{file.filename}")
        log.info(minio_shared_path)
        check_and_create_directory(minio_shared_path)
        shutil.copy2(f"{temp_dir}/{file.filename}", minio_shared_path)
        os.chmod(f"{minio_shared_path}/{file.filename}", 0o777)
        shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        # Check if same name exists
        log.debug("Inside folder upload")
        new_filename = file.filename.split(".")[0]
        minio_shared_path = minio_shared_path + "/" + new_filename
        if not overwrite:
            if os.path.exists(f"{minio_shared_path}"):
                raise Exception(ErrorCodes.ERROR_0007)
        else:
            if os.path.exists(f"{minio_shared_path}"):
                shutil.rmtree(minio_shared_path, ignore_errors=True)
        check_and_create_directory(minio_shared_path)
        copytree(f"{temp_dir}/{new_filename}", minio_shared_path)
        change_access_of_folder_recursively(minio_shared_path)
        os.chmod(minio_shared_path, 0o777)
        shutil.rmtree(temp_dir, ignore_errors=True)
    response = "File uploaded successfully!"
    audit_logging(
        console_url=app.config['CONSOLE_BACKEND_URL'],
        action_type="CREATE",
        object_id=destination_path.strip(os.sep),
        object_name=destination_path.strip(os.sep),
        object_type="DATA_SECTION",
        headers={
            Headers.x_auth_username: g.user["first_name"],
            Headers.x_auth_email: g.user["email_address"],
            Headers.x_auth_userid: g.user["mosaicId"],
            Headers.x_project_id: g.user['project_id'],
        },
    )
    return response


def decode_jwt(data):
    """Method to decode token"""
    secret = app.config["JWT_SECRET"]
    algorithm = app.config["JWT_ALGORITHM"]
    return jwt.decode(data, secret, algorithms=[algorithm])



def preview_dataset(local_file_path, dataset_name, file_type, sub_type, folder_structure, row_count=10, volume_path=None, filter_columns=None):
    """ To display data preview """

    try:
        if sub_type in ['xls', 'xlsx']:
            df = pd.read_excel(local_file_path, engine='xlrd' if sub_type == 'xls' else None)
        elif sub_type == 'csv':
            df = pd.read_csv(local_file_path)

        if filter_columns:
            filter_columns = filter_columns.split(',')
            df = df[filter_columns]
        sample_data = df.head(row_count)
        field_names = sample_data.columns.tolist()
        datatypes = [
            'STRING' if df[col].dtype == 'object' else 'BOOLEAN' if df[col].dtype == 'bool' else df[col].dtype.name.upper()
            for col in field_names]
        display_names = field_names
        sample_data_transposed = sample_data.transpose().values.tolist()
        response = {
            "data": {
                "datatype": datatypes,
                "display_name": display_names,
                "field_name": field_names,
                "local_file_path": str(local_file_path),
                "sample_data": sample_data_transposed,
                "total_record_count": len(df)
            },
            "message": "Data fetched successfully",
            "status": "success"
        }
        return response
    except FileNotFoundError:
        raise PreviewFileException(msg_code="FILE_NOT_FOUND_ERROR_0001")
    except pd.errors.EmptyDataError:
        raise PreviewFileException(msg_code="DATA_NOT_FOUND_ERROR_0001")
    except KeyError as e:
        raise PreviewFileException(msg_code="COLUMN_NOT_FOUND_ERROR_0001")
    except Exception as e:
        raise PreviewFileException(msg_code="PREVIEW_FILE_ERROR_0001")


def manipulate_sample_response(sample_data_response, dataset_name=None):
    """ Manipulate sample  result to display on UI """
    sample_data_list = []
    field_name_list = []
    display_name_list = []
    datatype_list = []
    if sample_data_response.status_code == 200:
        results = sample_data_response.json()["result"][0]["columnarFieldList"]
        for data in results:
            field_name_list.append(data['fieldName'])
            sample_data_list.append(data['sample'])
            display_name_list.append(data.get('displayName'))
            datatype_list.append(data.get('datatype'))
        if dataset_name:
            display_name_list = get_std_display_col_map(dataset_name, display_name_list)
        sample_response_dict = {
            "local_file_path": sample_data_response.json()["connectorParam"]["local_file_path"],
            "total_record_count": sample_data_response.json()["result"][0]["totalRecordCount"],
            "field_name": field_name_list,
            "sample_data": sample_data_list,
            "display_name": display_name_list,
            "datatype": datatype_list
            }
        response, status_code = response_handler(
            "Data fetched successfully",
            "success",
            200,
            sample_response_dict,
        )
    else:
        response, status_code = response_handler(
            "Error occurred while retrieving data: Failure in Connection API",
            "failed",
            500,
        )
    return jsonify(response), status_code


def get_std_display_col_map(dataset_name, display_name_list):
    try:
        lens_datasource_url = app.config["LENS_DATASOURCE"] +\
                              f"/data/datasource/fields/-1?datasourceName={dataset_name}"
        headers = {
            "x-auth-username": g.user['email_address'],
            "x-project-id": g.user['project_id']
        }
        log.info(f"Getting filed details from lens_datasource_url: {lens_datasource_url}, headers: {headers}")
        field_details = requests.get(lens_datasource_url, headers=headers).json()
        std_display_col_map = {}

        if not field_details:
            return display_name_list

        # We get list of filed details, thus taking only 1st element with index 0.
        for field in field_details[0]['fieldDetails']:
            std_display_col_map[field["fieldName"]] = field["displayName"]

        log.info(f"std_display_col_map: {std_display_col_map}")
        new_display_name_list = []
        for i in display_name_list:
            if i in std_display_col_map:
                new_display_name_list.append(std_display_col_map[i])
            else:
                new_display_name_list.append(i)
    except Exception as ex:
        log.error(f"Exception occurred in get_std_display_col_map: {ex}")
        return display_name_list
    return new_display_name_list


def response_handler(message, status, status_code, data=None):
    """ response handler function to generate json response"""
    response = {"message": message, "status": status}
    if data is not None:
        response["data"] = data
    if status == "success":
        return response, status_code
    return response, status_code


def get_new_data_dict(file_names, data_dict):
    data_dict_new = {}
    for key, value in data_dict.items():
        key_names = key.split("/")
        for filename in file_names:
            if len(key_names) > 1 and key_names[0] == filename:
                data_dict_new[key] = value
            else:
                if key_names[0] == filename:
                    data_dict_new[key] = value

    if len(data_dict_new) > 0:
        return data_dict_new
    else:
        return data_dict


def copytree(src, dst, symlinks=False, ignore=None):
    """
    This method is used for copy source folder and its content to destination folder
    :param src
    :param dst
    :param symlinks
    :param ignore
    :return:
    """
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

    return "Folder copied successfully!"


def check_and_create_directory(path):
    """
    Checking if folder exist if folder is not exist then it will create the folders
    :param path
    :return:file_path
    """
    path_array = path.split("/")
    directory = "/"
    for split_path in path_array:
        directory = directory + split_path + "/"
        if not os.path.isdir(directory):
            os.mkdir(directory, 0o777)
    os.chmod(path, 0o777)
    return "Folder created successfully!"

def check_and_create_log_directory(path):
    """
    Checking if folder exist if folder is not exist then it will create the folders
    :param path
    :return:file_path
    """
    path_array = path.split("/")
    directory = "/"
    for split_path in path_array:
        directory = directory + split_path + "/"
        if not os.path.isdir(directory):
            os.mkdir(directory, 0o777)
    package_file_path = path + 'package-installation.log'
    init_script_path = path + 'init-script.log'
    if os.path.exists(package_file_path):
        os.remove(package_file_path)
    if os.path.exists(init_script_path):
        os.remove(init_script_path)

    os.chmod(path, 0o777)
    return "Folder created successfully!"




def write_or_append_file_in_temp_location(file, location):
    """
    This method is used for appending the data into file
    :param file
    :param location
    :return:
    """
    begin = time.time()
    if not os.path.isdir(location):
        os.mkdir(location)

    with open(f"{location}/{file.filename}", 'ab') as file1:
        while True:
            data = file.stream.read(500000)
            if not data:
                break
            file1.write(data)
    end = time.time()
    log.info(f"Total runtime of the program is {end - begin}")
    return "Chunk uploaded successfully!"


def change_access_of_folder_recursively(location):
    """
    This method is used for changing the access of directory recursively
    :param location
    :return:
    """
    for root, dirs, files in os.walk(location):
        os.chmod(os.path.join(root, location), 0o777)
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o777)


def copy_data_under_folder(file_folder_name, temp_dir, project_id, destination_path, action_type):
    """
    This method is used for adding data files and folder in temp directory
    :param temp_dir
    :param file_folder_name
    :param project_id
    :return:
    """
    source_path = f'{get_base_path(project_id)}'f'{file_folder_name}'
    copy_file_folder(source_path, temp_dir)
    message = None if action_type == 'DOWNLOAD' else "User '{0}' '{3}' '{1}' data_section to '{2}'".format(g.user["email_address"],
                                                                    source_path.strip(os.sep),
                                                                    destination_path.strip(os.sep),
                                                                    'copyto')
    object_name = destination_path.strip(os.sep) if action_type == 'DOWNLOAD' else file_folder_name.strip(os.sep)
    audit_logging(
        console_url=app.config['CONSOLE_BACKEND_URL'],
        action_type=action_type,
        object_id=destination_path.strip(os.sep),
        object_name=object_name,
        object_type="DATA_SECTION",
        headers={
            Headers.x_auth_username: g.user["first_name"],
            Headers.x_auth_email: g.user["email_address"],
            Headers.x_auth_userid: g.user["mosaicId"],
            Headers.x_project_id: g.user['project_id'],
        },
        message=message,
    )


def copy_file_folder(source_path, destination_path):
    """
    This method is used for copying file or folder from one position to other
    :param source_path
    :param destination_path
    :return:
    """
    log.info(source_path)
    log.info(destination_path)
    check_and_create_directory(destination_path)
    if os.path.isdir(source_path):
        folder_name = source_path.split("/")[-1]
        check_and_create_directory(destination_path + "/" + folder_name)
        copytree(source_path, destination_path + "/" + folder_name)
        change_access_of_folder_recursively(destination_path + "/" + folder_name)
    else:
        shutil.copy2(source_path, destination_path)
        os.chmod(destination_path, 0o777)


def move_file_folder(source_path, destination_path, project_id, action_type):
    """
    This method is used for moving file or folder from one position to other
    :param source_path
    :param destination_path
    :param project_id
    :return:
    """
    log.info(source_path)
    log.info(destination_path)
    minio_path = get_base_path(project_id)
    log.info("Adding file from location : " + minio_path)
    shutil.move(minio_path + source_path, minio_path + destination_path)
    message = "User '{0}' '{3}' '{1}' data_section to '{2}'".format(g.user["email_address"],
                                                                  source_path.strip(os.sep),
                                                                  destination_path.strip(os.sep),
                                                                  'renamed' if action_type=='RENAME' else 'moveto')
    audit_logging(
        console_url=app.config['CONSOLE_BACKEND_URL'],
        action_type=action_type,
        object_id=source_path.strip(os.sep),
        object_name=source_path.strip(os.sep),
        object_type="DATA_SECTION",
        message=message,
        headers={
            Headers.x_auth_username: g.user["first_name"],
            Headers.x_auth_email: g.user["email_address"],
            Headers.x_auth_userid: g.user["mosaicId"],
            Headers.x_project_id: g.user['project_id'],
        },
    )


def remove_file_folder(file_path, project_id):
    """
    This method is used for removing file or folder
    :param file_path
    :param project_id
    :return:
    """

    minio_path = get_base_path(project_id)

    if os.path.isdir(minio_path + file_path):
        shutil.rmtree(minio_path + file_path)

    else:
        os.remove(minio_path + file_path)
    audit_logging(
            console_url=app.config['CONSOLE_BACKEND_URL'],
            action_type="DELETE",
            object_id=file_path.strip(os.sep),
            object_name=file_path.strip(os.sep),
            object_type="DATA_SECTION",
            headers={
                Headers.x_auth_username: g.user["first_name"],
                Headers.x_auth_email: g.user["email_address"],
                Headers.x_auth_userid: g.user["mosaicId"],
                Headers.x_project_id: g.user['project_id'],
            },
        )

def remove_log_dir(template_id, project_id):
    """
    This method is used for removing file or folder
    :param file_path
    :param project_id
    :return:
    """
    try:
        log_dir = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/log/" + f'{project_id}' + "/" + f'{template_id}'

        if os.path.isdir(log_dir):
            shutil.rmtree(log_dir)
    except Exception as ex:
        log.error(f"Exception occurred in removing log directory: {ex}")


def get_base_path(project_id, exp_name=None):
    """
    This method is used for getting the base directory path
    :param project_id
    :param exp_name
    :return:
    """
    if project_id:
        base_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/" + f'{project_id}/{project_id}-Data'
        if exp_name:
            mlflow_artifact_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
                'MINIO_DATA_BUCKET'] + "/" + f'{project_id}/{project_id}-mlflow'
            check_and_create_directory(mlflow_artifact_path)
    else:
        base_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET']

    check_and_create_directory(base_path)
    return f'{base_path}/'


def get_space_occupied_by_file(project_id, folder_path):
    """
    This method is used for getting total consume memory by particular folder
    :param project_id
    :param folder_path
    :return:
    """
    path = get_base_path(project_id) + folder_path
    return convert_size(int(subprocess.check_output(['du', '-sb', path]).split()[0].decode('utf-8')))


def get_list_of_files(project_id, folder_path, size_flag=False):
    """
    This method is used for getting files and folder list under particular folder
    :param project_id
    :param folder_path
    :return:
    """
    folder_files = []
    path = get_base_path(project_id) + folder_path
    if os.path.isdir(path):
        arr = os.listdir(path)
        for file_path in arr:
            is_dir = os.path.isdir(path + "/" + file_path)
            complete_path = path + "/" + file_path
            detail = {
                "last_modified": get_last_modified_file_time(path + "/" + file_path),
                "name": file_path,
                "size": convert_size(os.path.getsize(path + "/" + file_path)) if not is_dir else
                get_space_occupied_by_file(project_id, folder_path + "/" + file_path),
                "type": "Folder" if is_dir else "File"
            }
            folder_files.append(detail)
        if size_flag:
            size = get_space_occupied_by_file("", folder_path)
            return folder_files, size

    return folder_files


def get_list_of_all_files(project_id, folder_path, size_flag=False):
    """
    This method is used for getting all files recursively under particular folder
    :param project_id
    :param folder_path
    :return:
    """
    folder_files = []
    path = get_base_path(project_id) + folder_path
    if os.path.isdir(path):
        # Get all files inside directory & subdirectory
        for dir_path, folder_list, file_list in os.walk(path):
            for file in file_list:
                file_path = (os.path.join(dir_path, file))
                detail = {
                    "last_modified": get_last_modified_file_time(file_path),
                    "name": file_path.split(path + '/')[-1],
                    "size": convert_size(os.path.getsize(file_path)),
                    "type": "File"
                }
                folder_files.append(detail)
        if size_flag:
            size = get_space_occupied_by_file("", folder_path)
            return folder_files, size

    return folder_files


def get_last_modified_file_time(file_path):
    """
    This method is used for getting last modified time of particular path
    :param file_path
    :return:
    """
    mod_timesince_epoc = os.path.getmtime(file_path)
    # Convert seconds since epoch to readable timestamp
    modification_time = time.strftime('%a, %d %b %Y %H:%M:%S', time.localtime(mod_timesince_epoc))
    return modification_time


def get_project_base_path(project_id):
    """
    This method is used for getting the base directory path
    :param project_id
    :return:
    """
    base_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
        'MINIO_DATA_BUCKET'] + "/" + f'{project_id}'

    return f'{base_path}/'


def remove_project_data(project_id):
    """
    This method is used for removing project data
    :param project_id
    :return:
    """
    project_path = get_project_base_path(project_id)
    # "ignore_errors=True" as below, this will delete the folder at the given if found or do nothing if not found**
    shutil.rmtree(project_path, ignore_errors=True)


def formatFileSizeToGb(size):
    '''
    Convert file size to GB of a string representing its value in different file sizes.
    '''
    if 'KB' in size:
        sizeInKB = float(size.split('K')[0])
        return float(sizeInKB/1024.0**2)
    elif 'MB' in size:
        sizeInMB = float(size.split('M')[0])
        return float(sizeInMB/1024.0)
    elif 'GB' in size:
        sizeInGB = float(size.split('G')[0])
        return sizeInGB


def get_space_occupied_by_all_projects():
    """
    This method is used for getting total consume memory by all projects in platform

    :return:
    """
    #Getting list of all projects present in the platform
    url = app.config["CONSOLE_BACKEND_URL"] + "/api/v2/projects?all=true"
    headers = {
        "X-Auth-Userid": g.user['mosaicId'],
        "X-Auth-Username": g.user['first_name']
    }

    response = requests.get(url, headers=headers)
    project_list = response.json()

    #Calculating allocated resource quota to each project present in platform
    allocated_project_quota = str(sum(formatFileSizeToGb(project['resourceQuota']) for project in project_list['data'])) + " GB"
    log.info(allocated_project_quota)

    #Getting consumed resource quota by all projects in the platform
    consumed_project_quota = get_space_occupied_by_file(None, "")
    log.info("consumed_project_quota")
    log.info(consumed_project_quota)

    return str(consumed_project_quota), str(allocated_project_quota)


def get_project_resource_quota(project_id, console_url, headers, required_allocated = True, original_format = False):
    """
    get project quota and consumed quota
    """
    try:
        total_consumed_quota = get_space_occupied_by_file(project_id, "")
        total_consumed_quota_bytes = convert_into_bytes(total_consumed_quota)
        if required_allocated :
            project_details_url = f"{console_url}/secured/api/project/v1/resource/{project_id}"
            log.debug(f"Fetching project details ")
            response = requests.get(project_details_url, headers=headers)
            if response.status_code == 200:
                response_json = response.json()
                project_quota = response_json.get("resourceQuota")
                if original_format:
                    return total_consumed_quota, project_quota
                quota_in_bytes = convert_into_bytes(project_quota)
                return quota_in_bytes, total_consumed_quota_bytes
            raise FetchProjectResourceQuotaError
        else:
            return  total_consumed_quota_bytes
    except ConnectionError as ex:
        log.exception(ex)
        raise ServiceConnectionError(msg_code="SERVICE_CONNECTION_ERROR_001")
    except MosaicException as ex:
        log.exception(ex)
        raise ex
    except Exception as ex:
        log.exception(ex)
        raise FetchProjectResourceQuotaError