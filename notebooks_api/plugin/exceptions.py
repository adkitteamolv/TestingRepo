#! -*- coding: utf-8 -*-

""" This module contains different exceptions  """


# pylint: disable=too-few-public-methods
class ErrorCodes:
    """ Exceptions list """

    # Error message
    ERROR_0001 = "Invalid status value. Please use enabled / disabled."
    ERROR_0002 = "Plugin id is required"
    ERROR_0003 = "Plugin error / invalid payload"
    ERROR_0004 = "Unable to delete Plugin"
    ERROR_0005 = "Please provide plugin name"
    ERROR_0006 = "Name should only contain the following a-z A-z 0-9 _ . " \
                 "And should not start and end with _"
    ERROR_0007 = "Plugin name already exists"
    ERROR_0008 = "Plugin data error"
    ERROR_0009 = "remote_file_path is mandatory"
    ERROR_0010 = "Invalid file type. Please provide a zip file"
    ERROR_0011 = "Invalid filters list"