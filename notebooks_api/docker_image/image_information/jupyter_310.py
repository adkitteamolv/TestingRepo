"""
Docker Image Information : Python 3.10
"""
from flask import current_app as app

JUPYTER_310_TAG = "3.10V1.0.8"
JUPYTER_310_GPU_TAG = "3.10V1.0.8"

JUPYTER_310_IMAGE = {
    "name": "Python-3.10",
    "icon": "python.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=310", "version=3.10"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.10:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_3_10_IMAGE"],
        JUPYTER_310_TAG),
    "gpu_docker_url": "{}{}/3.10:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_3_10_IMAGE"],
        JUPYTER_310_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
