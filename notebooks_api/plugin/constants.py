#! -*- coding: utf-8 -*-
"""Plugin constants module"""

PRE_BUILD = "PRE_BUILD"
CUSTOM_BUILD = "CUSTOM_BUILD"

ENABLED = "enabled"
DISABLED = "disabled"
DATA_PATH = "/data"
MODELS_PATH = "/models"
NOTEBOOKS_PATH = "/notebooks"
SNAPSHOT_PATH = "/snapshot/{}"
RECIPE_PATH = "{}{}/custom_plugin/"


# pylint: disable=too-few-public-methods
class OutputFormats:
    """ Valid output formats """
    CSV = "csv"
    HTML = "html"
    NAS = "nas"
    JSON = "json"

class RPluginMetadata:
    """R Plugin Info"""
    R_PACKAGE_REPO = "http://cran.us.r-project.org"


# pylint: disable=too-few-public-methods
class InputFormats:
    """ Valid input formats """
    MODEL = "model"
    NOTEBOOK = "notebook"
    NAS = "nas"


# pylint: disable=too-few-public-methods
class RefractSections:
    """ Valid refract sections """
    MODEL = "model"
    NOTEBOOK = "notebook"
    DATA = "data"


# pylint: disable=too-few-public-methods
class ResponseMessages:
    """ Response Messages """
    SWITCH = "Plugin is {} now"
    SAVE_PLUGIN = "Plugin data saved"
    DELETE_PLUGIN = "Plugin deleted Successfully"
    RECIPE_UPDATE = "Zip file uploaded successfully"


class MosaicAI:
    """Mosaic ai backend"""
    MODEL_META = "/v1/ml-model/model-meta/{}/version/{}"
