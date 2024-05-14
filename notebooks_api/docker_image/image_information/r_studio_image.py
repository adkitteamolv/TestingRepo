"""
Docker Image Information : R Studio
"""
from flask import current_app as app

R_STUDIO_TAG = "rs3.52-readonly"
R_STUDIO_GPU_TAG = "gpu-rs3.50"

R_STUDIO_IMAGE = {
    "name": "RStudio-4",
    "icon": "r.svg",
    "base_template": "RStudio-4",
    "package_type": "cran",
    "tags": ("type=rstudio", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=4"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/rstudio:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_STUDIO_IMAGE"],
        R_STUDIO_TAG),
    "gpu_docker_url": "{}{}/rstudio:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_STUDIO_IMAGE"],
        R_STUDIO_GPU_TAG),
    "kernel_type": "rstudio",
    "container_uid": "1000"
}
