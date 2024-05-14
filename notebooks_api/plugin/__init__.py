#! -*- coding: utf-8 -*-
"""Plugin module"""
from flask import Blueprint

# pylint: disable=invalid-name
plugins_api = Blueprint("plugin", __name__)

# pylint: disable=wrong-import-position
from . import controllers
