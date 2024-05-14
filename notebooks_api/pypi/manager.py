#! -*- coding: utf-8 -*-
"""Module for pypi manager"""

import logging
import re
import requests
from lxml import html
from flask import jsonify, request, current_app as app

from notebooks_api import get_application

from .models import Package


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


def get_packages(language='python'):
    """ populate available packages from the pip registry """
    app = get_application()
    if language == 'r':
        registry = app.config["CRAN_URL"]
    elif language == 'conda':
        registry = app.config["CONDA_PYTHON_URL_ES"]
    elif language == "conda-r":
        registry = app.config["CONDA_R_URL_ES"]
    else:
        registry = app.config["PYPI_URL"]
    response = requests.get(registry) 
    response.raise_for_status()
    html_tree = html.fromstring(response.content)

    if app.config['ARTIFACTORY'] is False and language == 'r':
        # pylint: disable=unnecessary-comprehension
        packages = [generate_packages(package, app.config['ARTIFACTORY'], language)
                    for package in html_tree.xpath('//span[@class="CRAN"]')
                    if generate_packages(package, app.config['ARTIFACTORY'], language) is not None]
    else:
        # pylint: disable=unnecessary-comprehension
        packages = [generate_packages(package, app.config['ARTIFACTORY'], language)
                    for package in html_tree.xpath('//a/text()')
                    if generate_packages(package, app.config['ARTIFACTORY'], language) is not None]

    # Remove redundant packages & versions pair
    if language == 'conda':
        packages = [i for n, i in enumerate(packages) if i not in packages[n + 1:]]
    return packages


# pylint: disable=inconsistent-return-statements
def generate_packages(package, artifactory, language):
    """ generate dict object for all the packages """
    if artifactory and language == 'r':
        if package.endswith('.tar.gz'):
            package_name = package.split("_")[0]
            package_version = re.search('_(.*).tar', package).group(1)
            return {"name": package_name, "version": package_version}
    elif language in ["conda", "conda-r"]:
        if package.endswith('tar.bz2'):
            package_name_list = package.split("-")
            build_name = package_name_list[-1]
            package_version = package_name_list[-2]
            package_name = "-".join(package_name_list[:-2])
            py_version = re.search("(py[0-9]{2})+", build_name)
            py_version = py_version.group() if py_version else "NA"
            if language == "conda":
                return {"name": package_name, "version": package_version, "python_version": py_version}
            return {"name": package_name}
    elif language == 'r':
        return {"name": package.text}
    else:
        return {"name": package}

# PACKAGES = get_packages()


def get_latest_cran_version_jfrog(package_name):
    '''This function returns essential details of cran package
    by accessing CRAN_VERSION_URL
    Version gives latest version available
    '''
    cran_package_details_url = app.config['CRAN_URL']
    response = requests.get(cran_package_details_url)
    response.raise_for_status()
    html_tree = html.fromstring(response.content)
    for package in html_tree.xpath('//a/text()'):
        packagename = package.split("_")[0]
        if packagename == package_name:
            package_version = re.search('_(.*).tar', package).group(1)
            return package_version


def search_versions_for_cran_package_in_jfrog(package_name):
    latest_version = get_latest_cran_version_jfrog(package_name)
    get_all_version_url = app.config["CRAN_ALL_VERSION_PACKAGE"]
    response = requests.get(get_all_version_url.format(package_name))
    response.raise_for_status()
    html_tree = html.fromstring(response.content)
    packages_info = [generate_packages(package, True, 'r')
                     for package in html_tree.xpath('//a/text()')
                     if generate_packages(package, True, 'r') is not None]

    versionsarray = [x.get('version') for x in packages_info]
    versionsarray.sort(reverse=True)
    if latest_version not in versionsarray:
        versionsarray.insert(0, latest_version)
    return versionsarray
