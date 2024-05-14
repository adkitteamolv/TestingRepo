#! -*- coding: utf-8 -*-
"""Notebook module"""

from flask import Blueprint

# pylint: disable=invalid-name
notebook_api = Blueprint("notebook", __name__)

# pylint: disable=wrong-import-position
from . import controllers
