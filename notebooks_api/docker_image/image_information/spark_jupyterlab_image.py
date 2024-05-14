"""
Docker Image Information : SPARK - JUPYTERLAB
"""
from flask import current_app as app

SPARK_JUPYTER_LAB_TAG = "1.1.26"
SPARK_JUPYTER_LAB_GPU_TAG = "1.1.26"

SPARK_JUPYTERLAB_IMAGE = {
    "name": "spark-Jupyterlab",
    "icon": "spark-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=3.6"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/spark:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_JUPYTERLAB_IMAGE"],
        SPARK_JUPYTER_LAB_TAG),
    "gpu_docker_url": "{}{}/spark:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_JUPYTERLAB_IMAGE"],
        SPARK_JUPYTER_LAB_GPU_TAG),
    "kernel_type": "spark",
    "container_uid": "1000"
}
