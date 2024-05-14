#! -*- coding: utf-8 -*-
""" Application module """

from . import create_app

# pylint: disable=invalid-name
application = create_app(metrics_flag=True)
