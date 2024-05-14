"""
Master Information of all docker images
"""
from .jupyter_38 import JUPYTER_38_IMAGE
from .jupyter_39 import JUPYTER_39_IMAGE
from .jupyter_310 import JUPYTER_310_IMAGE
from .jupyter_38_snowflake import JUPYTER_38_SNOW_IMAGE
from .jupyterlab_38_image import JUPYTERLAB_38_IMAGE
from .jupyterlab_39_image import JUPYTERLAB_39_IMAGE
from .jupyterlab_310_image import JUPYTERLAB_310_IMAGE
from .vscode_jdk_image import VSCODE_JDK_IMAGE
from .r_studio_4_1_2 import R_V4_1_2_STUDIO_IMAGE
from .jupyter_39_snowflake import JUPYTER_39_SNOW_IMAGE
from .vscode_python_39 import VSCODE_PYTHON_39_IMAGE

DOCKER_IMAGES = (
    JUPYTER_38_IMAGE,
    JUPYTER_39_IMAGE,
    JUPYTER_310_IMAGE,
    JUPYTER_38_SNOW_IMAGE,
    JUPYTER_39_SNOW_IMAGE,
    JUPYTERLAB_38_IMAGE,
    JUPYTERLAB_39_IMAGE,
    JUPYTERLAB_310_IMAGE,
    VSCODE_JDK_IMAGE,
    R_V4_1_2_STUDIO_IMAGE,
    VSCODE_PYTHON_39_IMAGE

)
