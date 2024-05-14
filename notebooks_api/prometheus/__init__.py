#! -*- coding: utf-8 -*-
""" prometheus init module """

from flask import Blueprint

# pylint: disable=invalid-name
prometheus_api = Blueprint("prometheus", __name__)

# pylint: disable=wrong-import-position
from . import controllers
