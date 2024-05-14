"""
Docker Image Information : Python 3.6 - Conda
"""
from flask import current_app as app

JUPYTER_36_TAG = "2.6.13"
JUPYTER_36_GPU_TAG = "2.6.13"

JUPYTER_36_IMAGE = {
    "name": "Python-3.6",
    "icon": "python.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=3.6"),
    "docker_url": "{}{}/3.6:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_36_IMAGE"],
        JUPYTER_36_TAG),
    "gpu_docker_url": "{}{}/jupyter/3.6{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_36_IMAGE"],
        JUPYTER_36_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
