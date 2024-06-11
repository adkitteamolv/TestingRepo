"""Controllers for data files"""

import logging
import base64
import tempfile
import os
import subprocess
from flasgger import swag_from
from flask import (
    Response,
    jsonify,
    request,
    send_file,
    current_app as app,
    g
)
import re
from .constants import PREVIEW_PAYLOAD_PATTERN
from pathlib import Path
from ..utils.exceptions import UploadFileException, MosaicException, PreviewFileException


from mosaic_utils.ai.headers.utils import generate_headers

from . import data_files_api
from .exceptions import ErrorCodes
from .manager import (
    data_for_file,
    get_zip_data,
    data_upload_file,
    preview_dataset,
    add_data_in_temp_dir,
    create_zip_remove_temp_dir,
    get_list_of_files,
    get_list_of_all_files,
    check_and_create_directory,
    copy_data_under_folder,
    copy_file_folder,
    move_file_folder,
    remove_file_folder,
    get_base_path,
    get_space_occupied_by_file, remove_project_data, get_space_occupied_by_all_projects,
    get_project_resource_quota)

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


@data_files_api.route("/v1/data-files", methods=["GET"])
@swag_from("swags/list.yaml")
def list_api():
    """
    API to list data files
    """
    try:
        folder_path = "" if request.args.get(
            "folder_path") is None else request.args.get("folder_path")
        # fetch data files
        data_files, bucket_consumed_storage = get_list_of_all_files("", folder_path, True)
        # send response
        return jsonify({"data_files": data_files, "consumed_storage": bucket_consumed_storage}), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0002, 500


@data_files_api.route("/v1/data-files", methods=["POST"])
@swag_from("swags/create.yaml")
def upload_api():
    """
    API to create data files
    """
    try:
        file_name = request.form.get("file_name")
        if file_name.endswith(".exe"):
            raise UploadFileException(msg_code="UPLOAD_FILE_ERROR_0001")

        file = request.files.get("datafile")
        eof = request.form.get("eof")
        uuid = request.form.get("file_unique")
        file_type = request.form.get("file_content_type")


        # upload type can be bucket or data upload
        upload_type = request.args.get('upload_type')

        if not file_type:
            file_type = file.content_type

        total_size = float(request.args['total_size'])
        log.info(eof)
        log.info(uuid)
        log.info(file_type)

        project_quota, consumed_quota = get_project_resource_quota \
            (request.headers["X-Project-Id"], app.config["CONSOLE_BACKEND_URL"],
             generate_headers(g.user['mosaicId'], g.user['email_address'], g.user['first_name'], g.user['project_id']))

        if consumed_quota + total_size > project_quota:
            raise Exception(ErrorCodes.ERROR_0006)
        if request.args.get("destination_path") is not None and request.args.get(
                "destination_path") != "":
            destination_path = request.args.get("destination_path")
        else:
            destination_path = ""
        overwrite = request.args.get("overwrite", default=False, type=str) == "True"
        response = data_upload_file(
            destination_path, file, request.headers["X-Project-Id"], uuid, eof, file_type, overwrite, upload_type)
        return jsonify({"data_files": response}), 201
    # pylint: disable=broad-except

    except MosaicException as ex:
        log.exception(ex)
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files", methods=["DELETE"])
@swag_from("swags/delete.yaml")
def delete_api():
    """
    API to delete data files
    """
    try:
        filename = request.args.get("filename")
        if not filename:
            raise ValueError
        file_path = f'{get_base_path(request.headers["X-Project-Id"])}/{filename}'
        if os.path.exists(f"{file_path}"):
            remove_file_folder(filename, f'{request.headers["X-Project-Id"]}')
            data_file_status = "Files deleted successfully."
            return data_file_status, 200
        else:
            return "No such file found ! Kindly try again with a valid file name.", 200
        # send response
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0003, 500


@data_files_api.route("/v1/data-files/download", methods=["GET"])
@swag_from("swags/download.yaml")
def download_api():
    """
    API to download data files
    """
    try:
        filename = request.args.get("filename")
        folder_struct = request.args.get("folder_struct")
        file_path = os.path.join(get_base_path(""), folder_struct, filename)
        if os.path.isdir(file_path):
            temp_dir = tempfile.mkdtemp()
            request_data_file = f"{temp_dir}/AllData"
            os.mkdir(request_data_file, 0o777)
            copy_file_folder(file_path, request_data_file)
            zip_data = create_zip_remove_temp_dir(temp_dir, "AllData")
            return Response(
                zip_data,
                mimetype='application/octet-stream',
                headers={"Content-Disposition": f"attachment;filename=AllData.zip"}
            ), 200
        else:
            if os.path.exists(f"{file_path}"):
                with open(file_path, "rb") as data_files:
                    return Response(
                        data_files.read(),
                        mimetype='application/octet-stream',
                        headers={"Content-Disposition": f"attachment;filename={filename}"}
                    ), 200
            else:
                return "No such file found ! Kindly try again with a valid file name.", 400
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0004, 500


@data_files_api.route("/v1/data-files/preview/<string:file_type>/<string:sub_type>/"
                      "<string:dataset_name>", methods=["GET"])
@swag_from("swags/preview.yaml")
def preview_api(file_type, sub_type, dataset_name):
    """
    API to preview data files
    """
    try:
        if file_type!='FILE':
            raise PreviewFileException(msg_code="FILE_TYPE_NOT_SUPPORTED")
        folder_structure = request.args.get("folder_structure", default=None)
        volume_path = request.args.get("volume_path", default=None)
        row_count = int(request.args.get("row_count", 10))
        filter_columns = request.args.get("filterColumns", default=None)
        folder_structure = str(folder_structure) + "/" if folder_structure else ""
        if folder_structure and not PREVIEW_PAYLOAD_PATTERN.match(folder_structure):
            raise PreviewFileException(msg_code="INVALID_INPUT_FILE_PREVIEW")

        minio_data_path = app.config["NOTEBOOK_MOUNT_PATH"]
        bucket_name = app.config["MINIO_DATA_BUCKET"]
        if dataset_name:
            if not PREVIEW_PAYLOAD_PATTERN.match(dataset_name):
                 raise PreviewFileException(msg_code="INVALID_INPUT_FILE_PREVIEW")

        if sub_type not in ["raw", "csv", "xlsx", "xls"]:
            raise PreviewFileException(msg_code="FILE_SUBTYPE_NOT_SUPPORTED")

        if not volume_path:
            local_file_path = f"{minio_data_path}{bucket_name}/{folder_structure}{dataset_name}"
        else:
            local_file_path = f"{folder_structure}{dataset_name}"

        if sub_type == "raw":
            return send_file(local_file_path, mimetype='text/html')
        else:
            previewed_data = preview_dataset(local_file_path, dataset_name, file_type, sub_type, folder_structure, row_count, volume_path, filter_columns)
            return jsonify(previewed_data)

    except MosaicException as ex:
        log.exception(ex)
        return jsonify(ex.message_dict()), ex.code
    except Exception as ex:
        log.exception(ex)
        return jsonify(str(ex)), 500


@data_files_api.route("/v1/data-files/delete_files", methods=["DELETE"])
@swag_from("swags/delete_files.yaml")
def delete_files_api():
    """
    API to delete data files
    """
    try:
        filenames = request.get_json()
        data_file_status = "Files deleted successfully."
        # delete data files
        for filename in filenames:
            remove_file_folder(filename, f'{request.headers["X-Project-Id"]}')

        # send response
        return data_file_status, 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0003, 500


@data_files_api.route("/v1/data-files/create_folder", methods=["POST"])
@swag_from("swags/create_folder.yaml")
def create_folder_api():
    """
    API to create new folder in bucket
    """
    try:
        create_status = "Folder created successfully."
        folder_name = request.args.get('folder_name')
        folder_name = get_base_path(f'{request.headers["X-Project-Id"]}') + f'{folder_name}'
        log.info("Folder name is : " + folder_name)
        check_and_create_directory(folder_name)

        # send response
        return create_status, 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0008, 500


@data_files_api.route("/v1/data-files/rename", methods=["POST"])
@swag_from("swags/rename_file.yaml")
def rename_file_api():
    """
    API to create new folder in bucket
    """
    try:
        old_filename = request.args.get('old_filename')
        new_filename = request.args.get('new_filename')
        rename_status = "File renamed successfully."

        move_file_folder(old_filename, new_filename, f'{request.headers["X-Project-Id"]}', 'RENAME')
        # send response
        return rename_status, 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0009, 500


@data_files_api.route("/v1/data-files/download_files", methods=["POST"])
@swag_from("swags/download_multiples.yaml")
def download_multiples_api():
    """
    API to download multiple data files
    """
    try:
        file_names = request.get_json()
        # Creating temporary directory
        temp_dir = tempfile.mkdtemp()
        request_data_file = f"{temp_dir}/AllData"
        os.mkdir(request_data_file, 0o777)

        for filename in file_names:
            copy_data_under_folder(filename, request_data_file, f'{request.headers["X-Project-Id"]}', filename, 'DOWNLOAD')

        zip_data = create_zip_remove_temp_dir(temp_dir, "AllData")
        return Response(
            zip_data,
            mimetype='application/octet-stream',
            headers={"Content-Disposition": f"attachment;filename=AllData.zip"}
        ), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return ErrorCodes.ERROR_0004, 500


@data_files_api.route("/v1/data-files/big_size_file", methods=["POST"])
@swag_from("swags/create.yaml")
def upload_big_size_file_api():
    """
    API to upload big size data files
    """
    try:
        # upload the file to S3
        file = request.files.get("datafile")
        eof = request.form.get("eof")
        uuid = request.form.get("file_unique")
        file_type = request.form.get("file_content_type")

        log.info(eof)
        log.info(uuid)
        log.info(file_type)

        if request.args.get("destination_path") is not None and request.args.get(
                "destination_path") != "":
            destination_path = request.args.get("destination_path")
        else:
            destination_path = ""
        overwrite = request.args.get("overwrite", default=False, type=str) == "True"
        response = data_upload_file(
            destination_path, file, request.headers["X-Project-Id"], uuid, eof, file_type, overwrite)
        return jsonify({"data_files": response}), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files/copy_files", methods=["POST"])
@swag_from("swags/copy_move.yaml")
def copy_api():
    """
    This api is used for copying file from one location to other
    """
    try:
        json = request.get_json()
        file_names = json["source_files"]
        destination_path = json["destination_path"]
        minio_path = get_base_path(f'{request.headers["X-Project-Id"]}')
        size = 0
        for filename in file_names:
            if os.path.isdir(minio_path+filename):
                size += int(subprocess.check_output(['du', '-sb', minio_path+filename]).split()[0].decode('utf-8'))
            else:
                size += os.path.getsize(minio_path+filename)
        project_quota, consumed_quota = get_project_resource_quota \
            (request.headers["X-Project-Id"], app.config["CONSOLE_BACKEND_URL"],
             generate_headers(g.user['mosaicId'], g.user['email_address'], g.user['first_name'], g.user['project_id']))
        if consumed_quota + size > project_quota:
            raise Exception(ErrorCodes.ERROR_0006)
        for filename in file_names:
            copy_data_under_folder(filename, minio_path + destination_path, f'{request.headers["X-Project-Id"]}',
                                   destination_path, 'COPYTO')

        response = "File copied successfully."

        return jsonify({"data_files": response}), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files/move_files", methods=["POST"])
@swag_from("swags/copy_move.yaml")
def move_api():
    """
    This api is used for copying file from one location to other
    """
    try:
        json = request.get_json()
        log.info(json)
        file_names = json["source_files"]
        destination_path = json["destination_path"]
        for filename in file_names:
            move_file_folder(filename, destination_path, f'{request.headers["X-Project-Id"]}', 'MOVETO')

        response = "File moved successfully."

        return jsonify({"data_files": response}), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files/consumer_size", methods=["GET"])
@swag_from("swags/list.yaml")
def consume_size():
    """
    This api is used for finding the total consumed space by specific project
    """
    try:
        consumed_quota, assigned_quota = get_project_resource_quota\
            (request.headers["X-Project-Id"], app.config["CONSOLE_BACKEND_URL"],
             generate_headers(g.user['mosaicId'], g.user['email_address'], g.user['first_name'], g.user['project_id']),
             original_format=True)
        return jsonify({"consumed_quota": consumed_quota, "assigned_quota": assigned_quota}), 201
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files/file_lists", methods=["GET"])
@swag_from("swags/list.yaml")
def list_files_api():
    """
    This api is used for finding the total consumed space by specific project
    """
    try:
        folder_path = request.args.get("folder_path", "")
        data_files = get_list_of_files(f'{request.headers["X-Project-Id"]}', folder_path)
        return jsonify({"data_files": data_files}), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500


@data_files_api.route("/v1/data-files/delete_project", methods=["DELETE"])
@swag_from("swags/delete_project_data.yaml")
def delete_project_api():
    """
    API to delete data files for project
    """
    try:
        project_data_deletion_status = "Project data deleted successfully."
        # delete project data
        remove_project_data(f'{request.headers["X-Project-Id"]}')
        # send response
        return project_data_deletion_status, 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0010, 500


@data_files_api.route("/v1/data-files/consumer_size/all", methods=["GET"])
@swag_from("swags/consume.yaml")
def consume_size_all():
    """
    This api is used for finding the total consumed space and total allocated to all projects combined in the platform
    """
    try:
        consumed_project_quota, allocated_project_quota = get_space_occupied_by_all_projects()
        return jsonify({"consumed_project_quota": consumed_project_quota, "allocated_project_quota": allocated_project_quota}), 200
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return str(ex), 500