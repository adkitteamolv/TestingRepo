"""
Docker Image Information : R Studio
"""
from flask import current_app as app

R_STUDIO_TAG = "1.2"
R_STUDIO_GPU_TAG = "1.2"

R_STUDIO_RHEL_4_1_3_IMAGE = {
    "name": "RStudio_RHEL-4.1",
    "icon": "r.svg",
    "base_template": "RStudio_RHEL-4.1",
    "package_type": "cran",
    "tags": ("type=rstudio", "default=true", "os=RHEL", "pyversion=38", "version=4.1"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/rstudio_rhel:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_STUDIO_RHEL_4_1_3_IMAGE"],
        R_STUDIO_TAG),
    "gpu_docker_url": "{}{}/rstudio_rhel:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_R_STUDIO_RHEL_4_1_3_IMAGE"],
        R_STUDIO_GPU_TAG),
    "kernel_type": "rstudio",
    "container_uid": "1000"
}
