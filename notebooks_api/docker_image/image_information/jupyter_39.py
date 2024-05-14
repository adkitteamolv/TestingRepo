"""
Docker Image Information : Python 3.9
"""
from flask import current_app as app

JUPYTER_39_TAG = "3.9V1.1.12"
JUPYTER_39_GPU_TAG = "3.9V1.1.12"

JUPYTER_39_IMAGE = {
    "name": "Python-3.9",
    "icon": "python.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=39", "version=3.9"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.9:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_39_IMAGE"],
        JUPYTER_39_TAG),
    "gpu_docker_url": "{}{}/3.9:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_39_IMAGE"],
        JUPYTER_39_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
