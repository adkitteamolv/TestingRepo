#! -*- coding: utf-8 -*-
"""Pypi utils module"""
import contextlib
import json
import logging
import re

import urllib.request
import requests
from flask import current_app as app
from pip._internal import index
from bs4 import BeautifulSoup
from pip._internal.models.search_scope import SearchScope
from pip._internal.models.selection_prefs import SelectionPreferences
from pip._internal.models.target_python import TargetPython
from pip._internal.network.session import PipSession  # pylint: disable=E0611, E0401
from pip._internal.index import PackageFinder
from pip._internal.collector import LinkCollector
from urllib.parse import urlparse

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.pypi")


@contextlib.contextmanager
def indent_log(num=2):
    """Method for indent log"""
    yield num


# indent log is monkey patched to overcome the shortcoming of pip
# please see https://github.com/pypa/pip/issues/2553 for details
index.indent_log = indent_log

def string_to_tuple(string):
    """
    Convert a string to a tuple with three elements, where the first two elements are characters from the input string and
    the third element is either a '0' character or the third character of the input string.

    Args:
        string (str): A string with length 2, 3, or 4.

    Returns:
        tuple: A tuple with three elements, where the first two elements are characters from the input string and the
        third element is either a '0' character or the third character of the input string.

    Raises:
        ValueError: If the input string does not have length 2, 3, or 4.

    Examples:
        >>> string_to_tuple('39')
        ('3', '9', '0')

        >>> string_to_tuple('310')
        ('3', '10', '0')

        >>> string_to_tuple('3100')
        ('3', '10', '0')

        >>> string_to_tuple('38')
        ('3', '8', '0')

        >>> string_to_tuple('31')
        ('3', '1', '0')
    """

    if len(string) == 2:
        return string[0], string[1], '0'
    elif len(string) == 3:
        return string[0], string[1:], '0'
    elif len(string) == 4:
        return string[0], string[1:3], string[3]
    else:
        raise ValueError("Input string must have length 2, 3, or 4.")

def search_versions_for_package(package_name, os, pyversion):
    """ Fetch the versions available for the given package """

    pypi_url = app.config["PYPI_URL"]
    trusted_host = urlparse(pypi_url).hostname


    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    pf = PackageFinder.create(
        link_collector=LinkCollector(
            search_scope=SearchScope(find_links=[], index_urls=[pypi_url]),
            session=PipSession(trusted_hosts=[trusted_host]),
        ),
        selection_prefs=SelectionPreferences(allow_yanked=False),
        target_python=TargetPython(platform=os,
                                   py_version_info=string_to_tuple(pyversion),
                                   implementation='cp',
                                   abi='cp{}m'.format(pyversion)
                                   ),
    )

    pf.find_all_candidates(package_name)
    return list(
        {x.version.public for x in pf.find_all_candidates(package_name)})


def get_cran_package_details(package_name,details_key):
    '''This function returns essential details of cran package
    by accessing CRAN_VERSION_URL
    Version gives latest version available
    Depends gives depedency of package
    Maintainer gives name of maintainer
    Need to pass required info as details_key in argument of this function
    '''
    cran_package_details_url = app.config["CRAN_VERSION_URL"]
    html_page = urllib.request.urlopen(cran_package_details_url.format(package_name))
    soup = BeautifulSoup(html_page, "html.parser")
    table = soup.find("table")
    for row in table.find_all("tr"):
        for counter,td in enumerate(row.find_all("td")):
            if details_key.lower() in td.get_text().lower():
                return row.find_all("td")[counter+1].get_text()


def search_versions_for_r_package(package_name):
    """ Fetch the versions available for the given package
        CRAN_ALL_VERSION_PACKAGE url
    """
    get_all_version_url = app.config["CRAN_ALL_VERSION_PACKAGE"]
    try:
        html_page = urllib.request.urlopen(get_all_version_url.format(package_name))
    except:
        print('URL not found {0}'.format(get_all_version_url.format(package_name)))
        return []
    soup = BeautifulSoup(html_page, "html.parser")
    versionsarray = []
    for link in soup.findAll('a'):
        if link.get('href').endswith('.tar.gz'):
            package = link.get('href').split("_")[0]
            package_version = re.search('_(.*).tar', link.get('href')).group(1)
            versionsarray.append(package_version)
    latest_version = get_cran_package_details(package_name, 'version')
    if latest_version not in versionsarray:
        versionsarray.insert(0, latest_version)
    return versionsarray


