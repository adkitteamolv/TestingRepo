# -*- coding: utf-8 -*-
""" Exceptions module """


class AuthenticationError(Exception):
    """Authentication error method"""
    code = 401
    message = "Please login to continue"


class AuthorizationError(Exception):
    """Authorization error method"""
    code = 403
    message = "Access denied"
