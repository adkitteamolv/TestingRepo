"""
Docker Image Information : VSCODE - JDK
"""
from flask import current_app as app

VSCODE_JDK_TAG = "2.0.4"
VSCODE_JDK_GPU_TAG = "2.0.4"

VSCODE_JDK_IMAGE = {
    "name": "VSCode-JDK11",
    "icon": "java-vscode.svg",
    "base_template": "VSCode",
    "package_type": None,
    "tags": ("type=vscode", "default=true"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/jdk11-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_JDK_IMAGE"],
        VSCODE_JDK_TAG),
    "gpu_docker_url": "{}{}/jdk11-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_JDK_IMAGE"],
        VSCODE_JDK_GPU_TAG),
    "kernel_type": "jdk11",
    "container_uid": "1001"
}


# 1.0.0 - initial cut
# 2.0.0 - Bumped vscode base version, and removed sensitive data