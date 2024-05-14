"""
Docker Image Information : R Jupyter
"""
from flask import current_app as app

R_JUPYTER_TAG = "r-notebookV1.0.38"
R_JUPYTER_GPU_TAG = "r-notebookV1.0.38"

R_JUPYTER_IMAGE = {
    "name": "R-Jupyter",
    "icon": "r.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "cran",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=36"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/r:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_JUPYTER_IMAGE"],
        R_JUPYTER_TAG),
    "gpu_docker_url": "{}{}/r:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_JUPYTER_IMAGE"],
        R_JUPYTER_GPU_TAG),
    "kernel_type": "r",
    "container_uid": "1001"
}
