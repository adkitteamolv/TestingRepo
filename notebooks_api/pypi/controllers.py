#! -*- coding: utf-8 -*-

""" Controllers associated with the common module """

import logging
from flasgger import swag_from
from flask import jsonify, request, current_app as app

from notebooks_api.docker_image.manager import read_docker_image
from notebooks_api.utils.exceptions import ErrorCodes
from notebooks_api.utils.tags import get_tag

from . import pypi_api
from .manager import search_versions_for_cran_package_in_jfrog
from .pypi_index import (search_package, search_package_version)
from .utils import (
    search_versions_for_r_package,
    search_versions_for_package)


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


@pypi_api.route("/v1/pypi/search/<string:package_name>", methods=["GET"])
@swag_from("swags/search.yaml")
def search_in_elastic(package_name):
    """ API for package auto completion with es """

    # lookup packages
    try:
        search_array_set = set(search_package(package_name, "python"))
        search_array = sorted(list(search_array_set))
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0003, 500

    return jsonify(search_array)


@pypi_api.route("/v1/pypi/version/<string:package_name>", methods=["GET"])
@swag_from("swags/version.yaml")
def get_versions(package_name):
    """ API to search versions for package """

    # parse input data
    base_image_id = request.args.get("base_image_id")
    if base_image_id:
        # get os and python info
        base_docker_image = read_docker_image(base_image_id)
        tags = base_docker_image['tags']
        _, pyversion = get_tag("pyversion", tags, True)
        # pylint: disable=invalid-name
        _, os = get_tag("os", tags, True)
    else:
        pyversion = request.args.get("pyversion")
        os = None
        log.debug(
            "Searching compatiable versions for %s with filters os=%s py=%s",
            package_name,
            os,
            pyversion)

    # lookup versions
    try:
        search_array = search_versions_for_package(package_name, os, pyversion)
        search_array.sort(reverse=True)
    # pylint: disable=broad-except
    except Exception as ex:
        logging.exception(ex)
        return ErrorCodes.ERROR_0004, 500

    return jsonify(search_array)


@pypi_api.route("/v1/cran/search/<string:package_name>", methods=["GET"])
@swag_from("swags/search.yaml")
def search_in_elastic_r(package_name):
    """ API for package auto completion with es """

    # lookup packages
    try:
        versions = sorted(search_package(package_name, 'r'))
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0003, 500

    return jsonify(versions)


@pypi_api.route("/v1/cran/version/<string:package_name>", methods=["GET"])
@swag_from("swags/version.yaml")
def get_versions_r(package_name):
    """ API to search versions for package """
    log.debug("Searching compatiable versions for %s", package_name)
    # lookup versions
    try:
        if app.config['ARTIFACTORY']:
            versions = search_versions_for_cran_package_in_jfrog(package_name)
        else:
            versions = search_versions_for_r_package(package_name)

        versions.sort(reverse=True)
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0004, 500

    return jsonify(versions)


@pypi_api.route("/v1/conda/search/<string:package_name>", methods=["GET"])
@swag_from("swags/search.yaml")
def search_package_conda_in_elastic(package_name):
    """ API for package auto completion with es """
    # lookup packages
    try:
        search_array = sorted(search_package(package_name, "conda"))
        search_array_set = set(search_array)
        search_array = sorted(list(search_array_set))
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0003, 500

    return jsonify(search_array)


@pypi_api.route("/v1/conda/version/<string:package_name>", methods=["GET"])
@swag_from("swags/version.yaml")
def get_versions_conda(package_name):
    """ API to search versions for package """
    log.debug("Searching compatiable versions for %s", package_name)
    # lookup versions
    try:
        # parse input data
        base_image_id = request.args.get("base_image_id")

        # get os and python info
        if base_image_id:
            base_docker_image = read_docker_image(base_image_id)
            tags = base_docker_image['tags']
            _, py_version = get_tag("pyversion", tags, True)
            py_version = "py"+str(py_version)
            log.debug("pyversion in conda package search: %s", py_version)
        else:
            py_version = "py"+str(request.args.get("pyversion"))

        versions = search_package_version(package_name, py_version, "conda")
        versions.sort(reverse=True)
    # pylint: disable=broad-except
    except Exception as ex:
        logging.exception(ex)
        return ErrorCodes.ERROR_0004, 500

    return jsonify(versions)


@pypi_api.route("/v1/conda-r/search/<string:package_name>", methods=["GET"])
@swag_from("swags/search.yaml")
def search_in_elastic_conda_r(package_name):
    """ API for package auto completion with es """

    # lookup packages
    try:
        search_array = sorted(search_package(package_name, 'conda-r'))
        search_array_set = set(search_array)
        search_array = sorted(list(search_array_set))
    # pylint: disable=broad-except
    except Exception as ex:
        log.error(ex)
        return ErrorCodes.ERROR_0003, 500

    return jsonify(search_array)
