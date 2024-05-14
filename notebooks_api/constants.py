#! -*- coding: utf-8 -*-
""" Constants module """


# pylint: disable=too-few-public-methods
class Headers:
    """ Header constants """
    authorization = "Authorization"
    x_auth_userid = "X-Auth-Userid"
    x_auth_username = "X-Auth-Username"
    x_auth_email = "X-Auth-Email"
    x_project_id = "X-Project-Id"


# pylint: disable=too-few-public-methods
class KeycloakRoles:
    """ Keycloak roles constants"""
    view = 'view'
    modify = 'modify'


class PasswordStore:
    """
    Password Store
    """
    DB = "DB"
    VAULT = "VAULT"


class MonitorStatus:
    """
    Monitor Status
    """
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    KILLED = "KILLED"
    PAUSED = "PAUSED"
