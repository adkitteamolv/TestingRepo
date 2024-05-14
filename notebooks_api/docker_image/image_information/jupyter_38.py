"""
Docker Image Information : Python 3.8
"""
from flask import current_app as app

JUPYTER_38_TAG = "3.8V1.0.27"
JUPYTER_38_GPU_TAG = "3.8V1.0.27"

JUPYTER_38_IMAGE = {
    "name": "Python-3.8",
    "icon": "python.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=38", "version=3.8"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_38_IMAGE"],
        JUPYTER_38_TAG),
    "gpu_docker_url": "{}{}/3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_38_IMAGE"],
        JUPYTER_38_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
