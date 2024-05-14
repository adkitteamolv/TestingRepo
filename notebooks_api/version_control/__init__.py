# -*- coding: utf-8 -*-
# pylint: disable=no-member
"""VCS module."""
from flask import Blueprint

# pylint: disable=invalid-name
version_control_api = Blueprint("version_control", __name__)

# pylint: disable=wrong-import-position
from . import controllers
