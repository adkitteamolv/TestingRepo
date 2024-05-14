"""
Docker Image Information : R - JupyterLab
"""
from flask import current_app as app

R_JUPYTER_LAB_TAG = "r-notebookV1.0.38"
R_JUPYTER_LAB_GPU_TAG = "r-notebookV1.0.38"

R_JUPYTERLAB_IMAGE = {
    "name": "R-Jupyterlab",
    "icon": "r-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "cran",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=36"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/r:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_JUPYTERLAB_IMAGE"],
        R_JUPYTER_LAB_TAG
    ),
    "gpu_docker_url": "{}{}/r:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_JUPYTERLAB_IMAGE"],
        R_JUPYTER_LAB_GPU_TAG),
    "kernel_type": "r",
    "container_uid": "1001"
}
