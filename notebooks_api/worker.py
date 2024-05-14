#! -*- coding: utf-8 -*-

""" Celery app """
from celery.schedules import crontab
from notebooks_api.pypi.tasks import refresh, refresh_r
from . import make_celery


# pylint: disable=invalid-name
celery = make_celery()


celery.autodiscover_tasks([
    "notebooks_api.notebook",
    "notebooks_api.pypi",
])

#
# @celery.on_after_configure.connect
# # pylint: disable=unused-argument
# def setup_periodic_tasks(sender, **kwargs):
#     """Add periodic task"""
#     sender.add_periodic_task(
#         crontab(hour=3, minute=0),
#         refresh.s(),
#         name='refresh every three hour'
#     )
#
#
# @celery.on_after_configure.connect
# # pylint: disable=unused-argument
# def setup_periodic_tasks_r(sender, **kwargs):
#     """Add periodic task for r"""
#     sender.add_periodic_task(
#         crontab(hour=4, minute=0),
#         refresh_r.s(),
#         name='refresh every four hour'
#     )
