# #! -*- coding: utf-8 -*-
#
# """ Celery tasks associated with plugin module """
# import logging
# from flask import g, current_app
# import requests
#
# from mosaic_utils.ai.headers.utils import generate_headers
# # from notebooks_api import make_celery
# # from notebooks_api import get_config
# # from notebooks_api import get_application
# from ..constants import MonitorStatus
# from .job import ExecutePlugin
#
# # pylint: disable=invalid-name
# # app = get_application()
# # celery = make_celery(app=app)
# # app_config = get_config()
#
# # pylint: disable=invalid-name
# log = logging.getLogger("notebooks_api.plugin")
#
#
# def async_execute_plugin(user, product_id, request_json):
#     """
#     Execute plugin in async
#     :param: user
#     :param: product_id
#     :param: request_json
#     :param: async_strategy
#     :return: None
#     """
#     try:
#         g.user = user
#         g.product_id = product_id
#         log.debug(f"Inside async_execute_plugin\n"
#                   f"Setting G Variables, user: {user}, product_id: {product_id}")
#         execute_plugin = ExecutePlugin(user, request_json)
#         response = execute_plugin.execute_plugin()
#         log.debug(f"Inside async_execute_plugin\n"
#                   f"execute_plugin - Response {response}")
#     except Exception as ex:
#         log.exception(ex)
#         update_job_status(request_json["instance_id"], user, MonitorStatus.FAILED)
#         raise
#
#
# def update_job_status(job_instance_id, user, status=MonitorStatus.FAILED):
#     """
#     To update run status in monitor service
#     :param user:
#     :param job_instance_id:
#     :param status: MonitorStatus - Use Constants from this class
#     :return:
#     """
#     try:
#         log.info("Updating job-id %s to %s", job_instance_id, status)
#         headers = generate_headers(
#             userid=user["mosaicId"],
#             email=user["email_address"],
#             username=user["first_name"],
#             project_id=user["project_id"]
#         )
#         querystring = {
#             "jobInstanceId": str(job_instance_id),
#             "jobStatus": str(status),
#         }
#         url = current_app.config["MONITOR_URL"] + "/monitor/jobinstance-status"
#         resp = requests.put(url, data=querystring, headers=headers)
#         log.info("Response Text - %s - Code %s", resp.text, resp.status_code)
#         resp.raise_for_status()
#     except Exception as ex:
#         log.exception(ex)
#         raise
