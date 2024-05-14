#! -*- coding: utf-8 -*-
"""Resources module"""
from flask import Blueprint

# pylint: disable=invalid-name
resource_api = Blueprint('resource', __name__)

# pylint: disable=wrong-import-position
from . import controllers
