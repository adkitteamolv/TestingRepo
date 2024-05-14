#! -*- coding: utf-8 -*-

""" This module contains different exceptions used by the mosaic ai-logistics """


# pylint: disable=too-few-public-methods
class ErrorCodes:
    """ Exceptions used by mosaic ai-logistics """

    # Error message
    ERROR_0001 = "Unable to upload file. Kindly try again later !"
    ERROR_0002 = "Unable to fetch files. Kindly try again later !"
    ERROR_0003 = "Unable to delete file. Kindly try again later !"
    ERROR_0004 = "Unable to download file. Kindly try again later !"
    ERROR_0005 = "Unable to get the preview. Kindly try again later !"
    ERROR_0006 = "There is not enough space left for this operation to complete, " \
                 "Kindly contact Admin to increase your resource quota."
    ERROR_0007 = "File/Folder with same name already exists. Try with a different name"
    ERROR_0008 = "Unable to create folder !"
    ERROR_0009 = "Unable to rename file !"
    ERROR_0010 = "Unable to delete project data"
