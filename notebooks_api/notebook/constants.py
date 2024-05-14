#! -*- coding: utf-8 -*-
"""Notebooks constants module"""


# pylint: disable=too-few-public-methods
class PodStatus:
    """ Status of pod """
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


class SpawnerURL:
    """Notebook URL"""
    HUB_BASE_URL = "{}/users/{}/servers/{}"
    PROXY_PREFIX_URL = "{}/user/{}/{}"
    URL_PREFIX = "{}/v1/notebooks/{}/{}/progress"
    TERMINAL_URL = "{}/terminals/websocket/1"


class VcsURL:
    """VCS URL"""
    NOTEBOOK_URL = "{}/"
    PROGRESS = "{}/users/{}/servers/{}/progress"
    GIT_URL = "{}/repo/{}/file/{}"
    INFO_URL = "{}/info"
    DELETE_URL = "/repo/{}/branch/{}/file/{}"
    UPLOAD_FOLDER_URL = "/repo/{}/upload"
    DELETE_NB_URL = "/repo/{}/delete/notebook"
    UPLOAD_FOLDER_URL_CONTINUE = "/repo/{}/upload/temp_dir"
    READ_FILE_URL = "/repo/{}/file/{}/branch/{}?commit_type={}"
    COMMIT_ID = "{}/repo/commits/latest"
    REPO_BRANCHES = "/repo/{}/branch"
    CREATE_BRANCH = "/repo/branch"


class SchedulerURL:
    """Scheduler URL"""
    RESPONSE = "{}/{}/commits/master/notebooks/{}"
    ENDPOINT = "{}/scheduler/api/v1/job"
    UPDATE_ENDPOINT = "{}/scheduler/api/v1/job/{}"
    DELETE_POD = "/pod-name/{}"


class StringConstants:
    """String constants"""
    TOKEN = "Token {}"
    PROJECT = 'project={}'


class Headers:
    """Headers constants"""
    authorization = "Authorization"
    x_auth_userid = "X-Auth-Userid"
    x_auth_username = "X-Auth-Username"
    x_auth_email = "X-Auth-Email"


class MosaicAI:
    """Mosaic ai backend"""
    token_create = "/v1/token"


class KernelType:
    """Type of kernel"""
    r = "r"
    rstudio = "rstudio"
    python = "python"
    spark = "spark"
    spark_distributed = "spark_distributed"
    sas = "sas"
    default = "default"
    slash = "/"
    input = "input"
    snapshot = "snapshot"
    jdk11 = "jdk11"
    sas_batch_cli = "sas_batch_cli"
    vscode_python = "vscode_python"

class FileExtension:
    """File extension"""
    ipynb = ".ipynb"
    r = ".r"
    py = ".py"
    sas = ".sas"
    java = ".java"
    scala = ".scala"


class NotebookPath:
    """Notebook path"""
    nb_base_path = "/notebooks/notebooks/"


class ExperimentStyles:
    """ Experiment styles available in Auto ML"""
    auto = "auto"
    quick = "quick"
    manual = "manual"


class RepoStatus:
    """
    Repository status
    """
    Enabled = "Enabled"
    Disabled = "Disabled"


class RepoType:
    """
    Repository type
    """
    GIT = "Github"
    BITBUCKET = "Bitbucket"
    GITLAB = "Gitlab"
    AZUREDEVOPS = "Azuredevops"


class Accesstype:
    """
    Access type
    """
    OWNER = "OWNER"
    CONTRIBUTOR = "CONTRIBUTOR"
    VIEWER = "VIEWER"
    VALIDATOR = "VALIDATOR"


class RepoAccessCategory:
    """
    Access Type constants used for git repo
    """
    name = "access_category"
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class ReportFiles:
    """
    Report Files
    """
    notebooks_report = "nb_metring_report.csv"


class RepoMessages:
    """
    Contains Repository related Messages and Constants
    """
    ERROR_DETAILS = "error_details"
    ERROR_MESSAGE = "error_message"
    GENERIC_ERROR_MESSAGE = "Something went wrong, please contact admin"
