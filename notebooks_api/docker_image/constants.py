#! -*- coding: utf-8 -*-
""" Docker image constants module """
PRE_BUILD = "PRE_BUILD"
CUSTOM_BUILD = "CUSTOM_BUILD"
PRE_BUILD_SPCS = "PRE_BUILD_SPCS"
CUSTOM_BUILD_SPCS = "CUSTOM_BUILD_SPCS"


# pylint: disable=too-few-public-methods
class KernelType:
    """ Kernel type constants """
    r = "r"
    rstudio = "rstudio"
    python = "python"
    spark = "spark"


class PodStatus:
    """ Status of pod """
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


class InvalidNames:
    """ Invalid Directory Names"""
    LINUX_DIRECTORIES = ["bin", "boot", "cdrom", "dev", "etc", "git", "lib", "lost+found", "media",
                         "mnt", "notebooks", "inputs", "outputs", "opt", "proc", "root", "run",
                         "sbin", "scheduler", "selinux", "srv", "sys", "tmp", "usr", "var"]


class ConfigKeyNames:
    """
    This class stores the config key name
    """
    PROXY_ENABLED_GIT_PROVIDER = "PROXY_ENABLED_GIT_PROVIDER"
    PROXY_DETAILS = "PROXY_DETAILS"
