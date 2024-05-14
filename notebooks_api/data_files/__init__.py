#! -*- coding: utf-8 -*-
"""Module for data files"""
from flask import Blueprint

# pylint: disable=invalid-name
data_files_api = Blueprint('data_files', __name__)

# pylint: disable=wrong-import-position
from . import controllers
