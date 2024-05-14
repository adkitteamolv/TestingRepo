"""
Docker Image Information : Python 3.10 - JupyterLab
"""
from flask import current_app as app
from ..constants import PRE_BUILD_SPCS

JUPYTERLAB_SPCS_310_TAG = "python3.10"
JUPYTERLAB_SPCS_310_GPU_TAG = "python3.10"

JUPYTERLAB_310_SPCS_IMAGE = {
    "name": "Jupyterlab-3.10-SPCS",
    "icon": "python-jupyterlab.svg",
    "base_template": "JupyterLab",
    "package_type": "pip",
    "tags": ("type=jupyterlab", "default=true", "os=manylinux1_x86_64", "pyversion=310", "version=3.10"),
    "docker_url": "{}:{}".format(
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_SPCS_3_10_IMAGE"],
        JUPYTERLAB_SPCS_310_TAG),
    "gpu_docker_url": "{}:{}".format(
        app.config["REGISTRY_DIR_PATH_JUPYTERLAB_SPCS_3_10_IMAGE"],
        JUPYTERLAB_SPCS_310_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001",
    "type": PRE_BUILD_SPCS
}
