#! -*- coding: utf-8 -*-
""" Project init module """

from flask import Blueprint

# pylint: disable=invalid-name
project_api = Blueprint("project", __name__)

# pylint: disable=wrong-import-position
from . import controllers
