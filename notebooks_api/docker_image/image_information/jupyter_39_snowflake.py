"""
Docker Image Information : Python 3.9 - Snowflake
"""
from flask import current_app as app

JUPYTER_39_SNOW_TAG = "3.9-snowV1.2"
JUPYTER_39_SNOW_GPU_TAG = "3.9-snowV1.2"

JUPYTER_39_SNOW_IMAGE = {
    "name": "Python-3.9-Snowpark",
    "icon": "python_snowflake.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=39", "version=3.9"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/3.9-snowflake:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_39_SNOW_IMAGE"],
        JUPYTER_39_SNOW_TAG),
    "gpu_docker_url": "{}{}/3.9-snowflakes:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_JUPYTER_39_SNOW_IMAGE"],
        JUPYTER_39_SNOW_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
