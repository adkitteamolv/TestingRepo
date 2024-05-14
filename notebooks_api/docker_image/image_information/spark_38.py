"""
Docker Image Information : SPARK
"""
from flask import current_app as app

SPARK_TAG = "1.0.2"
SPARK_GPU_TAG = "1.0.2"

SPARK_38_IMAGE = {
    "name": "Spark-3.8",
    "icon": "spark.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=38", "version=3.8"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/spark-3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_38_IMAGE"],
        SPARK_TAG),
    "gpu_docker_url": "{}{}/spark-3.8:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_38_IMAGE"],
        SPARK_GPU_TAG),
    "kernel_type": "spark",
    "container_uid": "1000"
}
