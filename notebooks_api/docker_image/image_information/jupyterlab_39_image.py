"""
Docker Image Information : Python 3.9 - JupyterLab
"""
from flask import current_app as app

JUPYTERLAB_39_TAG = "3.9V1.1.12"
JUPYTERLAB_39_GPU_TAG = "3.9V1.1.12"

JUPYTERLAB_39_IMAGE = {
    "name": "Jupyterlab-3.9",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=39", "version=3.9"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.9:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_39_IMAGE"],
        JUPYTERLAB_39_TAG),
    "gpu_docker_url": "{}{}/3.9:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_39_IMAGE"],
        JUPYTERLAB_39_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"

}
