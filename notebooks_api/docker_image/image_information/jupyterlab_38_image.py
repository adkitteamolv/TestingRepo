"""
Docker Image Information : Python 3.8 - JupyterLab
"""
from flask import current_app as app

JUPYTERLAB_38_TAG = "3.8V1.0.22"
JUPYTERLAB_38_GPU_TAG = "3.8V1.0.22"

JUPYTERLAB_38_IMAGE = {
    "name": "Jupyterlab-3.8",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=38", "version=3.8"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_38_IMAGE"],
        JUPYTERLAB_38_TAG),
    "gpu_docker_url": "{}/3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_38_IMAGE"],
        JUPYTERLAB_38_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"

}
