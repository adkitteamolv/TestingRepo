#! -*- coding: utf-8 -*-
"""Module for pypi"""
from flask import Blueprint

# pylint: disable=invalid-name
pypi_api = Blueprint("pypi", __name__)

# pylint: disable=wrong-import-position
from . import controllers
