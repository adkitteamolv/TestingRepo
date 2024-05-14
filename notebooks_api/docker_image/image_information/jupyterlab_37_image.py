"""
Docker Image Information : Python 3.7 - JupyterLab
"""
from flask import current_app as app

JUPYTERLAB_37_TAG = "3.7V1.19"
JUPYTERLAB_37_GPU_TAG = "3.7V1.19"

JUPYTERLAB_37_IMAGE = {
    "name": "Jupyterlab-3.7",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=37", "version=3.7"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.7:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_37_IMAGE"],
        JUPYTERLAB_37_TAG),
    "gpu_docker_url": "{}{}/3.7:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_37_IMAGE"],
        JUPYTERLAB_37_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"

}
