#! -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

"""Constants for mosaic-kubespawner"""


# pylint: disable=too-few-public-methods
class KernelType:
    """Constants for kernel type"""

    spark = "spark"
    spark_distributed = "spark_distributed"
    python = "python"
    r_kernel = "r"
    rstudio_kernel = "rstudio"
    sas = "sas"
    default = "default"
    jdk11 = "jdk11"
    python_plugin = "python_plugin"
    vscode_python = "vscode_python"

class JobStatus:
    """Constants for job status"""

    running = "RUNNING"
    successful = "SUCCESSFUL"
    failed = "FAILED"


class Metering:
    """Constants for metering"""

    create_request = "/v1/subscriber/{subscriber_id}/request"
    update_usage = "/v1/usage/{pod_id}?is_last_update=True"


class Notebooks:
    """Constants for noteboooks-api"""

    update_pod_status = "/templates/{template_id}/stop-db"
    delete_pod = "/templates/{template_id}/stop"

class Automl:
    """"Constants for Automl"""

    update_recipe_status = "/v1/ml-experiment-recipe/experiment_recipe/{experiment_recipe_id}"


class Cron:
    """Constants for cronjob"""

    action_dict = {"SUSPEND": True, "RESUME": False}
