# #! -*- coding: utf-8 -*-
#
# """ Authorization helper """
#
# import base64
# import json
# import re
# import requests
# from flask import g, request
#
#
# def get_users_and_projects(mosaic_backend):
#     """
#     Fetch users and list of projects to which they have access
#
#     Args:
#         mosaic_backend (dict): dictionary containing mosaic auth endpoint, token etc
#
#     Returns:
#         dict
#     """
#     endpoint = mosaic_backend.get("endpoints", {}).get("user-projects")
#     content_type = mosaic_backend.get("headers", {}).get("content_type")
#     authorization = mosaic_backend.get("headers", {}).get("authorization")
#     headers = {
#         "Content-Type": content_type,
#         "Authorization": authorization
#     }
#     response = requests.get(endpoint, headers=headers, verify=False)
#     return response.json()
#
#
# class AuthorizationType:
#     """
#     Base class for different authorization implementation
#     """
#
#     def __init__(self, users_and_projects):
#         """
#         Constructor
#
#         Args:
#             users_and_projects (dict): dictionary containing users and their authorized projects
#         """
#         self.users_and_projects = users_and_projects
#
#     @property
#     def is_authorized(self):
#         """
#         Boolean representing whether user has access or not
#
#         Returns:
#             bool
#         """
#         if self.project_id:
#             user_id = g.user.get("mosaicId")
#             if user_id in self.users_and_projects:
#                 authorized_projects = self.users_and_projects[user_id]
#                 return self.project_id in authorized_projects
#         return True
#
#     @property
#     def project_id(self):
#         """
#         Method to parse project id from the request
#         """
#         raise NotImplementedError
#
#
# class QueryParamAuthorization(AuthorizationType):
#     """
#     Authorization based on query parameter
#     """
#     args = ("project",)
#
#     @property
#     def project_id(self):
#         """
#         Method to parse project id from the request
#
#         Returns:
#             int or None
#         """
#         for arg, val in request.args.items():
#             if arg in self.args:
#                 return int(val)
#
#
# class TagAuthorization(AuthorizationType):
#     """
#     Authorization based on tags
#     """
#     args = ("project",)
#
#     @property
#     def project_id(self):
#         """
#         Method to parse project id from the request
#
#         Returns:
#             int or None
#         """
#         tags = request.args.getlist("tags")
#         for tag in tags:
#             for arg in self.args:
#                 if tag.startswith(arg):
#                     _, val = tag.split("=")
#                     return int(val)
#
#
# class UrlParamAuthorization(AuthorizationType):
#     """
#     Authorization based on URL parameter
#     """
#
#     def __init__(self, users_and_projects, url_pattern):
#         """
#         Constructor
#
#         Args:
#             users_and_projects (dict): dict containing users and their authorized projects
#             url_pattern (str): regex to extract project id from the request path
#         """
#         self.url_pattern = url_pattern
#         super().__init__(users_and_projects)
#
#     @property
#     def project_id(self):
#         """
#         Method to parse project id from the request
#
#         Returns:
#             int or None
#         """
#         regex = re.compile(self.url_pattern)
#         match = regex.search(request.path).group(1)
#         return int(match)
#
#
# class Base64EncodedUrlParamAuthorization(UrlParamAuthorization):
#     """
#     Authorization based on base64 encoded URL parameter
#     """
#     args = ("project_id",)
#
#     @property
#     def project_id(self):
#         """
#         Method to parse project id from the request
#
#         Returns:
#             int or None
#         """
#         regex = re.compile(self.url_pattern)
#         match = regex.search(request.path).group(1)
#         match = str.encode(match)
#         match = base64.b64decode(match)
#         match = match.decode('utf-8')
#         match = json.loads(match)
#         for arg, val in match.items():
#             if arg in self.args:
#                return int(val)
