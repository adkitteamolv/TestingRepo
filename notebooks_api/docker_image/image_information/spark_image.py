"""
Docker Image Information : SPARK
"""
from flask import current_app as app

SPARK_TAG = "1.1.26"
SPARK_GPU_TAG = "1.1.26"

SPARK_IMAGE = {
    "name": "Spark-3.6",
    "icon": "spark.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=3.6"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/spark:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_IMAGE"],
        SPARK_TAG),
    "gpu_docker_url": "{}{}/spark:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_IMAGE"],
        SPARK_GPU_TAG),
    "kernel_type": "spark",
    "container_uid": "1000"
}
