"""
Docker Image Information : VSCODE - JDK
"""
from flask import current_app as app

VSCODE_PYTHON_39_TAG = "1.0.2"
VSCODE_PYTHON_39_TAG_GPU_TAG = "1.0.2"

VSCODE_PYTHON_39_IMAGE = {
    "name": "VSCode-Python-3.9",
    "icon": "python-vscode.svg",
    "base_template": "VSCode",
    "package_type": "pip",
    "tags": ("type=vscode", "default=true", "os=manylinux1_x86_64", "pyversion=39", "version=3.9"),
    # pylint: disable=line-too-long
    "docker_url": "{}{}/python-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_PYTHON_39_IMAGE"],
        VSCODE_PYTHON_39_TAG),
    "gpu_docker_url": "{}{}/python-vscode:{}".format(
        app.config["GIT_REGISTRY"],
        app.config["REGISTRY_DIR_PATH_VSCODE_PYTHON_39_IMAGE"],
        VSCODE_PYTHON_39_TAG_GPU_TAG),
    "kernel_type": "vscode_python",
    "container_uid": "1001"
}

