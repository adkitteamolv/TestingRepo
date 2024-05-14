"""
Docker Image Information : SPARK DISTRIBUTED
"""
from flask import current_app as app

SPARK_DISTRIBUTED_TAG = "1.0.4"
SPARK_DISTRIBUTED_GPU_TAG = "1.0.4"

SPARK_DISTRIBUTED_IMAGE = {
    "name": "Spark Distributed",
    "icon": "spark.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=38", "version=3.6"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/spark-dist:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_DISTRIBUTED_IMAGE"],
        SPARK_DISTRIBUTED_TAG),
    "gpu_docker_url": "{}{}/spark-dist:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_SPARK_DISTRIBUTED_IMAGE"],
        SPARK_DISTRIBUTED_GPU_TAG),
    "kernel_type": "spark_distributed",
    "container_uid": "1000",
    "number_of_executors": 2
}
