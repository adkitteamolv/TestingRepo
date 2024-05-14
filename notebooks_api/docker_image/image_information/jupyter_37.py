"""
Docker Image Information : Python 3.7
"""
from flask import current_app as app

JUPYTER_37_TAG = "3.7V1.19"
JUPYTER_37_GPU_TAG = "3.7V1.19"

JUPYTER_37_IMAGE = {
    "name": "Python-3.7",
    "icon": "python.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=37", "version=3.7"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.7:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_37_IMAGE"],
        JUPYTER_37_TAG),
    "gpu_docker_url": "{}{}/3.7:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_37_IMAGE"],
        JUPYTER_37_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
