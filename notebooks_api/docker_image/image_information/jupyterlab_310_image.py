"""
Docker Image Information : Python 3.10 - JupyterLab
"""
from flask import current_app as app

JUPYTERLAB_310_TAG = "3.10V1.0.8"
JUPYTERLAB_310_GPU_TAG = "3.10V1.0.8"

JUPYTERLAB_310_IMAGE = {
    "name": "Jupyterlab-3.10",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=310", "version=3.10"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.10:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_3_10_IMAGE"],
        JUPYTERLAB_310_TAG),
    "gpu_docker_url": "{}{}/3.10:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_3_10_IMAGE"],
        JUPYTERLAB_310_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"

}
