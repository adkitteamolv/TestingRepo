"""
Docker Image Information : Python 3.6 - JupyterLab
"""
from flask import current_app as app

JUPYTER_LAB_TAG = "2.6.13"
JUPYTER_LAB_GPU_TAG = "2.6.13"

JUPYTERLAB_IMAGE = {
    "name": "Jupyterlab-3.6",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=3.6"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.6:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_IMAGE"],
        JUPYTER_LAB_TAG),
    "gpu_docker_url": "{}{}/3.6:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_IMAGE"],
        JUPYTER_LAB_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"

}
