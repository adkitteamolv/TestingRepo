#! -*- coding: utf-8 -*-

""" Database operations associated with docker_image module """
import logging
from flask import (
    current_app as app,
    g,
)
from mosaic_utils.ai.audit_log.utils import audit_logging
from .constants import CUSTOM_BUILD, KernelType, PRE_BUILD, CUSTOM_BUILD_SPCS
from .models import DockerImage, DockerImageTag, db, Resource, DockerImageExtraAttribute
from ..constants import Headers, PasswordStore
from .data import insert_data_extra_attribute

# pylint: disable=invalid-name
from ..utils.encryption import VaultEncrypter

log = logging.getLogger("notebooks_api.docker_image")


def fetch_docker_images(image_type, project):
    """
    Fetch docker images based on the tags

    Args:
        image_type (string): Type of the docker images. eg: jupyter, saas etc
        project (string): Project identifier of the docker image
    """

    type_tag = "type={}".format(image_type)
    project_tag = "project={}".format(project)

    project_images = db.session.query(DockerImage.id) \
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id) \
        .filter((DockerImageTag.tag == project_tag) | (DockerImageTag.tag == "default=true"))

    result_set = db.session.query(DockerImage) \
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id) \
        .filter(DockerImageTag.tag == type_tag) \
        .filter(DockerImage.id.in_(project_images))

    # prepare response
    log.debug(
        "Preparing response after fetched from db result_set=%s",
        result_set)

    docker_image_set = []
    for result in result_set:
        docker_image = result.as_dict()
        docker_image.update({"tags": [tag.tag for tag in result.tags]})
        docker_image = remove_password(docker_image)
        docker_image_set.append(docker_image)
    return docker_image_set


def create_base_template(data):
    """
    Creates base template (enters records in DockerImage, DockerImageTag and DockerImageExtraAttribute table)

     Args:
        data (dict): Dictionary of data
    """
    resource_id = Resource.query.filter(Resource.name == data["resource_name"]).first().id
    log.debug("** Resource id %s" ,resource_id)

    if data["kernel_type"] == "r" or data["kernel_type"] == "rstudio":
        index_url = "https://cran.us.r-project.org"
    else:
        index_url = "https://pypi.org/simple/"

    # create image
    docker_image = DockerImage(
        name=data["name"],
        docker_url=data["docker_url"],
        gpu_docker_url=data["gpu_docker_url"],
        type=data["type"],
        description="Prebuilt image",
        icon=data["icon"],
        created_by="system",
        updated_by="system",
        kernel_type=data["kernel_type"],
        resource_id=resource_id,
        base_template=data["base_template"],
        package_type=data["package_type"],
        index_url=index_url
    )
    try:
        # save docker image object
        db.session.add(docker_image)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    # create tags
    log.debug("Creating docker image tag=%s", data["tags"])
    for tag in data["tags"]:
        docker_image_tag = DockerImageTag(
            docker_image=docker_image,
            tag=tag,
            created_by="system",
            updated_by="system"
        )
        try:
            db.session.add(docker_image_tag)
        except Exception as e:
            log.exception(e)
            db.session.rollback()

    # Creating extra attributes for IDE
    record = (db.session.query(DockerImage).filter(
        DockerImage.name == data["name"], DockerImage.type == data["type"]).first())

    log.debug(": %s", data["base_template"])
    if data["base_template"] == "Jupyter Notebook":
        if data["kernel_type"] == 'spark':
            docker_image_extra_attribute = DockerImageExtraAttribute(
                created_by="system",
                updated_by="system",
                port='8889',
                cmd='["jupyter-notebook"]',
                args='["--NotebookApp.ip=''0.0.0.0''", '
                     '"--NotebookApp.port=8889", '
                     '"--NotebookApp.open_browser=False", '
                     '"--NotebookApp.token=''''", 
                                     "--NotebookApp.password=''''", '
                     '"--NotebookApp.allow_root=False", '
                     '"--NotebookApp.base_url=''BASE_URL_VALUE''", '
                     '"--NotebookApp.trust_xheaders=True", '
                     '"--NotebookApp.disable_check_xsrf=True", '
                     '"--NotebookApp.notebook_dir=''/notebooks/notebooks''"'
                     ']',
                base_image_id=record.as_dict().get("id"),
                container_uid="1000"

            )

        else:
            docker_image_extra_attribute = DockerImageExtraAttribute(
                created_by="system",
                updated_by="system",
                port='8889',
                cmd='["jupyter-server"]',
                args='["--ServerApp.ip=''0.0.0.0''", '
                     '"--ServerApp.port=8889", '
                     '"--ServerApp.open_browser=False", '
                     '"--ServerApp.token=''''", 
                         "--ServerApp.password=''''", '
                     '"--ServerApp.allow_root=False", '
                     '"--ServerApp.base_url=''BASE_URL_VALUE''", '
                     '"--ServerApp.trust_xheaders=True", '
                     '"--ServerApp.disable_check_xsrf=True", '
                     '"--ServerApp.notebook_dir=''/notebooks/notebooks''"'
                     ']',
                base_image_id=record.as_dict().get("id"),
                container_uid="1001"

            )
        insert_data_extra_attribute(docker_image_extra_attribute)
    elif data["base_template"] in ["RStudio-4", "RStudio-4.1", "RStudio_RHEL-4.1"]:
        docker_image_extra_attribute = DockerImageExtraAttribute(
            created_by="system",
            updated_by="system",
            port='8888',
            base_url_env_key='BASE_URL',
            base_url_env_value='BASE_URL_VALUE',
            base_image_id=record.as_dict().get("id"),
            container_uid="1000"
        )
        insert_data_extra_attribute(docker_image_extra_attribute)
    elif data["base_template"] == "SAS":
        docker_image_extra_attribute = DockerImageExtraAttribute(
            created_by="system",
            updated_by="system",
            port='8989',
            base_url_env_key='SERVER_SERVLET_CONTEXT_PATH',
            base_url_env_value='BASE_URL_VALUE',
            base_image_id=record.as_dict().get("id"),
            container_uid="1000"
        )
        insert_data_extra_attribute(docker_image_extra_attribute)
    elif data["base_template"] == "JupyterLab":
        if data["kernel_type"] == 'spark':
            docker_image_extra_attribute = DockerImageExtraAttribute(
                created_by="system",
                updated_by="system",
                port='8889',
                cmd='["jupyter-lab"]',
                args='["--ServerApp.ip=''0.0.0.0''", '
                     '"--ServerApp.port=8889", '
                     '"--ServerApp.open_browser=False", '
                     '"--ServerApp.token=''''", 
                                     "--ServerApp.password=''''", '
                     '"--ServerApp.allow_root=False", '
                     '"--ServerApp.base_url=''BASE_URL_VALUE''", '
                     '"--ServerApp.trust_xheaders=True", '
                     '"--ServerApp.disable_check_xsrf=True", '
                     '"--ServerApp.notebook_dir=''/notebooks/notebooks''"'
                     ']',
                base_image_id=record.as_dict().get("id"),
                container_uid="1000"
            )

        else:
            docker_image_extra_attribute = DockerImageExtraAttribute(
                created_by="system",
                updated_by="system",
                port='8889',
                cmd='["jupyter-lab"]',
                args='["--ServerApp.ip=''0.0.0.0''", '
                     '"--ServerApp.port=8889", '
                     '"--ServerApp.open_browser=False", '
                     '"--ServerApp.token=''''", 
                         "--ServerApp.password=''''", '
                     '"--ServerApp.allow_root=False", '
                     '"--ServerApp.base_url=''BASE_URL_VALUE''", '
                     '"--ServerApp.trust_xheaders=True", '
                     '"--ServerApp.disable_check_xsrf=True", '
                     '"--ServerApp.notebook_dir=''/notebooks/notebooks''"'
                     ']',
                base_image_id=record.as_dict().get("id"),
                container_uid="1001"
            )
        insert_data_extra_attribute(docker_image_extra_attribute)

    elif data["base_template"] == "VSCode":
        docker_image_extra_attribute = DockerImageExtraAttribute(
            created_by="system",
            updated_by="system",
            port='8080',
            base_url_env_key='BASE_URL',
            base_url_env_value='BASE_URL_VALUE',
            base_image_id=record.as_dict().get("id"),
            container_uid="1001"
        )
        insert_data_extra_attribute(docker_image_extra_attribute)

    db.session.flush()
    db.session.commit()

    # exit log
    log.debug("Base Docker Template created successfully")

    # return newly created object
    return docker_image



def create_docker_image(data):
    """
    Create docker image and tags

    Args:
        data (dict): Dictionary of data
    """

    # parse extra data
    user = g.user["mosaicId"]
    tags = data.pop("tags", [])
    she_bang = "\n#/bin/bash\necho 'Logs of Init-Script:'\n"
    data["init_script"] = she_bang + data["init_script"]

    # create docker image object
    log.debug("Creating docker image with data=%s", data)
    docker_image = DockerImage(**data)

    # handle custom build images
    if data.get("type", None) in [CUSTOM_BUILD, CUSTOM_BUILD_SPCS]:
        # fetch the base image
        base_image = read_docker_image(docker_image.base_image_id)
        # update details from base image
        docker_image.docker_url = base_image['docker_url']
        docker_image.gpu_docker_url = base_image['gpu_docker_url']
        docker_image.docker_file = base_image['docker_file']
        docker_image.kernel_type = base_image['kernel_type']

        if data.get("index_url") is None:
            if docker_image.kernel_type == "r" or docker_image.kernel_type == "rstudio":
                docker_image.index_url = "https://cran.us.r-project.org"
            else:
                docker_image.index_url = "https://pypi.org/simple/"

    try:
        # save docker image object
        db.session.add(docker_image)
        db.session.flush()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    # create docker image tag object
    log.debug("Creating docker image tag=%s", tags)
    docker_image_tags = []
    for tag in tags:
        tag = DockerImageTag(
            docker_image_id=docker_image.id,
            tag=tag,
            created_by=user,
            updated_by=user
        )
        docker_image_tags.append(tag)

    try:
        # save docker image tag object
        db.session.add_all(docker_image_tags)
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    # exit log
    log.debug("Docker image created successfully")

    # return newly created object
    return docker_image


def read_docker_image(docker_image_id):
    """
    Read docker image

    Args:
        docker_image_id (str): UUID of the docker_image
    """

    # fetch docker image object
    docker_image = DockerImage.query.get(docker_image_id)

    # fetch base image object
    base_image = {}
    if docker_image.base_image_id:
        base_image = docker_image.base_docker_image.as_dict()

    # fetch docker image tag object
    docker_image_tags = []
    for tag in docker_image.tags:
        docker_image_tags.append(tag.tag)

    # combine docker image, base image and docker image tag
    docker_image = docker_image.as_dict()
    docker_image.update({"tags": docker_image_tags})
    docker_image.update({"base_image": base_image})
    docker_image = remove_password(docker_image)


    return docker_image


def update_docker_image(docker_image_id, data):
    """
    Update docker image

    Args:
        docker_image_id (str): UUID of the docker_image to be updated
        data (dict): Dictionary of data
    """
    # parse tags
    user = g.user["mosaicId"]
    tags = data.pop("tags", [])

    # fetch docker image object
    docker_image = DockerImage.query.get(docker_image_id)


    # fetching docker image id before update
    current_docker_image_base_id = docker_image.base_image_id

    data = update_macros(data,docker_image)

    # update docker image object
    for key, val in data.items():
        setattr(docker_image, key, val)

    # fetching docker image id after update
    updated_docker_image_base_id=docker_image.base_image_id

    # checking whether base template has been changed
    if current_docker_image_base_id != updated_docker_image_base_id:
        base_image = read_docker_image(docker_image.base_image_id)
        docker_image.docker_url = base_image['docker_url']
        docker_image.gpu_docker_url = base_image['gpu_docker_url']
        docker_image.docker_file = base_image['docker_file']
        docker_image.kernel_type = base_image['kernel_type']
        log.debug("inside fetching base image details")
    try:
        # save docker image object
        db.session.add(docker_image)
        # remove existing docker image tag object
        for tag in docker_image.tags:
            db.session.delete(tag)

        # create new docker image tag object
        docker_image_tags = []
        for tag in tags:
            tag = DockerImageTag(
                docker_image_id=docker_image.id,
                tag=tag,
                created_by=user,
                updated_by=user
            )
            docker_image_tags.append(tag)
        db.session.add_all(docker_image_tags)

        # commit to db
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def update_macros(data, docker_image):
    """
    Function To update Macros Config.
    UI Does not send updated password if user has not changed any field.
    This function will get the old password from the old config, and update the payload.
    Also, in case of VAULT Store, Delete the old reference inside vault.
    :param data: Payload Sent From UI
    :param docker_image: Existing Database record.
    :return: data: Updated Data
    """
    # old reference stored in vault
    old_id = docker_image._git_macros_config  # pylint: disable=protected-access
    if data.get("git_macros_config"):
        old_macros = docker_image.git_macros_config
        old_passwords_dict = {}
        if old_macros:
            old_passwords_dict = {x["id"]: x["password"] for x in old_macros}

        for macro in data.get("git_macros_config"):
            if "password" not in macro:
                macro["password"] = old_passwords_dict.get(macro["id"])

        # delete the old id from vault, if it has been updated.
        delete_from_vault(docker_image.__tablename__, old_id)

    return data


def delete_docker_image(docker_image_id):
    """
    Delete docker image and tags

    Args:
        docker_image_id (str): UUID of the docker_image
    """

    log.debug(
        "Entering delete_docker_image with docker_image_id=%s",
        docker_image_id)

    # fetch docker image object
    docker_image = DockerImage.query.get(docker_image_id)

    try:
        from notebooks_api.notebook.models import TemplateStatus, NotebookPodMetrics
        # delete docker image object
        # we have to delete rows in below sequence to avoid foreign key violation
        # DockerImageTag ,DockerImageExtraAttribute, NotebookPodMetrics, TemplateStatus & finally DockerImage
        delete_tags = DockerImageTag.__table__.delete().where(DockerImageTag.docker_image_id == docker_image_id)
        db.session.execute(delete_tags)

        # Delete extra attributes if present DockerImageExtraAttribute
        delete_extra = DockerImageExtraAttribute.__table__.delete().where(
            DockerImageExtraAttribute.base_image_id == docker_image_id)
        db.session.execute(delete_extra)
        template_ids = db.session.query(TemplateStatus.id).\
            filter(TemplateStatus.template_id == docker_image_id).all()
        for each_template_id in template_ids:
            delete_pod_metrics = NotebookPodMetrics.__table__.delete().\
                where(NotebookPodMetrics.template_id == each_template_id)
            db.session.execute(delete_pod_metrics)

        delete_template_status = TemplateStatus.__table__.delete().where(TemplateStatus.template_id == docker_image_id)
        db.session.execute(delete_template_status)
        db.session.delete(docker_image)
        db.session.commit()
        delete_from_vault(docker_image.__tablename__, docker_image._git_macros_config) # pylint: disable=protected-access

    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def list_docker_images(image_type, kernel_type, project):
    """ List docker images method """
    project_tag = "project={}".format(project)
    type_tag = "type={}".format(image_type)

    project_images = db.session.query(DockerImage.id)\
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id)\
        .filter((DockerImageTag.tag == project_tag) | (DockerImageTag.tag == "default=true"))\
        .filter(DockerImage.kernel_type == kernel_type)

    result_set = db.session.query(DockerImage)\
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id)\
        .filter(DockerImageTag.tag == type_tag)\
        .filter(DockerImage.id.in_(project_images))

    # prepare response
    log.debug(
        "Preparing response after fetched from db result_set=%s",
        result_set)

    docker_image_set = []
    for result in result_set:
        docker_image = result.as_dict()
        docker_image = remove_password(docker_image)
        docker_image_set.append(docker_image)
    return docker_image_set


def remove_password(docker_image: dict) -> dict:
    """
    Method to remove password key from git_macros_config in docker_image_dict
    :param docker_image(dict)
    :return: docker_image(dict)
    """
    macros = docker_image.get("git_macros_config")
    if macros:
        for macro_ in macros:
            macro_.pop("password", None)

    return docker_image


def list_all_docker_images(project):
    """
    Fetch docker images based on the tags

    Args:
        project (string): Project identifier of the docker image
    """

    project_tag = "project={}".format(project)

    project_images = db.session.query(DockerImage)\
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id)\
        .filter((DockerImageTag.tag == project_tag) | (DockerImageTag.tag == "default=true"))

    # prepare response
    log.debug(
        "Preparing response after fetched from db result_set=%s",
        project_images)

    docker_image_set = []
    for result in project_images:
        docker_image = result.as_dict()
        tag_list = []
        for tag in result.tags:
            if tag.tag.startswith("project=") and tag.tag != project_tag:
                pass
            else:
                tag_list.append(tag.tag)
        docker_image.update({"tags": tag_list})
        docker_image = remove_password(docker_image)
        docker_image_set.append(docker_image)
    return docker_image_set


def list_docker_images_type(image_type):
    """
    Fetch  docker images of specified type
    """

    log.info("Fetching all docker images of specified type")
    project_images = db.session.query(DockerImage)\
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id)\
        .filter((DockerImage.type == image_type))

    # prepare response
    log.debug(
        "Preparing response after fetched from db result_set=%s",
        project_images)

    docker_image_set = []
    for result in project_images:
        docker_image = result.as_dict()
        docker_image.update({"tags": [tag.tag for tag in result.tags]})
        docker_image = remove_password(docker_image)
        docker_image_set.append(docker_image)

    return docker_image_set


def delete_template(template_id):
    """ Delete template method """
    docker_image = DockerImage.query.get(template_id)

    try:
        # delete docker image object
        db.session.delete(docker_image)
        db.session.commit()
        delete_from_vault(docker_image.__tablename__, docker_image._git_macros_config) # pylint: disable=protected-access
        audit_logging(
            console_url=app.config['CONSOLE_BACKEND_URL'],
            action_type="DELETE",
            object_id=template_id,
            object_name=docker_image.name,
            object_type="TEMPLATE",
            headers={
                Headers.x_auth_username: g.user["first_name"],
                Headers.x_auth_email: g.user["email_address"],
                Headers.x_auth_userid: g.user["mosaicId"],
                Headers.x_project_id: g.user['project_id'],
            },
        )
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


# pylint: disable=redefined-builtin
def jupyter_nb_convert_command(type, data):
    """ Jupyter notebook convert command method """
    if ".py" in data["file_path"] or ".r" in data["file_path"]:
        command = "jupyter nbconvert --to={} {}".format(
            type,
            data["file_path"]
        )
        return command
    if type == "python":
        prefix = "python"
        extension = "py"
    else:
        prefix = "Rscript"
        extension = "r"
    if ".ipynb" in data["file_path"]:
        file_name = data["file_path"].strip(".ipynb")
    else:
        file_name = data["file_path"]

    command = "jupyter nbconvert --to={} {} \n {} {}.{}".format(
        type,
        data["file_path"],
        prefix,
        file_name,
        extension
    )
    return command


def fetch_spark_execution_commands(data):
    """ Fetch spark execution command method """
    if ".py" in data["file_path"]:
        command = "mv {} $MY_POD_NAME.py \n " \
                  "python /scheduler/spark/async/execute-file.py"\
            .format(data["file_path"])

    else:
        notebook_name = data["file_path"].strip(".ipynb")
        command = "jupyter nbconvert --to=python {} \n " \
                  "mv {}.py $MY_POD_NAME.py \n " \
                  "python /scheduler/spark/async/execute-file.py"\
            .format(data["file_path"], notebook_name)
    return command


def fetch_commands_for_scheduling(docker_image, data):
    """ Fetch commands for scheduling """
    commands = []

    if docker_image["kernel_type"] == KernelType.python:
        commands.append("python {}".format(data["file_path"]))
        commands.append(jupyter_nb_convert_command("python", data))
    elif docker_image["kernel_type"] == KernelType.r:
        commands.append(jupyter_nb_convert_command("script", data))
    elif docker_image["kernel_type"] == KernelType.rstudio:
        commands.append("Rscript {}".format(data["file_path"]))
        commands.append(jupyter_nb_convert_command("script", data))
    elif docker_image["kernel_type"] == KernelType.spark:
        spark_execution_command = fetch_spark_execution_commands(data)
        commands.append(spark_execution_command)
    else:
        return "Invalid Kernel Type detected"
    return commands


def list_all_template_resources():
    """
    Fetch all docker images info
    """
    project_images = db.session.query(DockerImage) \
        .join(DockerImageTag, DockerImage.id == DockerImageTag.docker_image_id) \
        .filter(DockerImage.created_by == "system") \
        .filter(DockerImageTag.tag == "default=true")

    # prepare response
    log.debug(
        "Preparing response after fetched from db result_set=%s",
        project_images)

    base_template_type = []
    for result in project_images:
        docker_image = result.as_dict()
        if docker_image['base_template'] not in ["", None]:
            base = {
                "base_template": docker_image['base_template'],
                "name": docker_image['name'],
                "icon": docker_image['icon'],
                "kernel_type": docker_image['kernel_type'],
                "base_image_id": docker_image['id'],
                "package_type": docker_image['package_type'],
                # pylint: disable=line-too-long
                "tags_type": next((tag.tag[5:] for tag in result.tags if tag.tag.startswith("type=")))

            }
            base_template_type.append(base)

    response = {}

    for image in base_template_type:
        base_template = image['base_template']

        if base_template in response.keys():
            response[base_template].append(image)
        else:
            response[base_template] = [image]

    return response


def delete_from_vault(tablename, key):
    """
    Function To delete key from vault
    :param tablename:
    :param key:
    :return:
    """
    if app.config["PASSWORD_STORE"] == PasswordStore.VAULT:
        VaultEncrypter(prefix_path=tablename).delete(key)


def toggle_docker_image_status(docker_image_id, show:bool):
    """
    Method to hide or show default templates base on default=true tag
    :param docker_image_id:
    :return:
    """
    default_tag = db.session.query(DockerImageTag).filter(
        DockerImageTag.docker_image_id == docker_image_id
    ).filter(DockerImageTag.tag.contains("default=")).first()

    if default_tag is None:
        raise Exception("Invalid Base Image ID Specified")

    default_tag.tag = "default=true" if show else "default=false"
    db.session.add(default_tag)
    db.session.commit()

    if not show:
        try:
            delete_tags = DockerImageTag.__table__.delete().where(DockerImageTag.docker_image_id == docker_image_id).where(DockerImageTag.tag.startswith("project"))
            db.session.execute(delete_tags)
            db.session.commit()
        except Exception as e:
            log.exception(e)
            db.session.rollback()

    return True


