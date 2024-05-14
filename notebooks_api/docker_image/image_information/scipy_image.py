"""
Docker Image Information : SCIPY
"""
from flask import current_app as app

SCIPY_TAG = "1.1.4"
SCIPY_GPU_TAG = "1.1.4"

SCIPY_IMAGE = {
    "name": "Scipy-3.6",
    "icon": "scipy.svg",
    "base_template": "Jupyter Notebook",
    "package_type": "pip",
    "tags": ("type=jupyter", "default=true", "os=manylinux1_x86_64", "pyversion=36", "version=3.6"),
    # pylint: disable=line-too-long
    "docker_url": "{}/mosaic-ai-logistics/mosaic-notebooks-manager/mosaic-docker-build/scipy:{}".format(
        app.config["GIT_REGISTRY"],
        SCIPY_TAG),
    "gpu_docker_url": "{}/mosaic-ai-logistics/mosaic-notebooks-manager/mosaic-docker-build/scipy:{}".format(
        app.config["GIT_REGISTRY"],
        SCIPY_GPU_TAG),
    "kernel_type": "python",
    "container_uid": "1001"
}
