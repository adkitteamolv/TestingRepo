"""
Docker Image Information : Python 3.8
"""
from flask import current_app as app

JUPYTER_38_SNOW_TAG = "3.8-snowV1.0.6"
JUPYTER_38_SNOW_GPU_TAG = "3.8-snowV1.0.6"

JUPYTER_38_SNOW_IMAGE = {
    "name": "Python-3.8-Snowpark",
    "icon": "python_snowflake.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=38", "version=3.8"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.8-snowflake:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_38_SNOW_IMAGE"],
        JUPYTER_38_SNOW_TAG),
    "gpu_docker_url": "{}{}/3.8-snowflakes:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_38_SNOW_IMAGE"],
        JUPYTER_38_SNOW_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
