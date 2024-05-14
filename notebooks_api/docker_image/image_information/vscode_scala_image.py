"""
Docker Image Information : VSCODE - Scala
"""
from flask import current_app as app

VSCODE_SCALA_TAG = "2.0.4"
VSCODE_SCALA_GPU_TAG = "2.0.4"

VSCODE_SCALA_IMAGE = {
    "name": "VSCode-Scala2.12",
    "icon": "snowflake-vscode.svg",
    "base_template": "VSCode",
    "package_type": None,
    "tags": ("type=vscode", "default=true"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/scala-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_SCALA_IMAGE"],
        VSCODE_SCALA_TAG),
    "gpu_docker_url": "{}{}/scala-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_SCALA_IMAGE"],
        VSCODE_SCALA_GPU_TAG),
    "kernel_type": "scala",
    "container_uid": "1001"
}

# 1.0.1 - inital cut - with snowpark added to CLASSPATH
# 2.0.0 - Bumped vscode base version, and removed sensitive data