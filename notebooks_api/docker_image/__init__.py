#! -*- coding: utf-8 -*-
""" Docker image init module """
from flask import Blueprint

# pylint: disable=invalid-name
docker_image_api = Blueprint('docker_image', __name__)

# pylint: disable=wrong-import-position
from . import controllers
