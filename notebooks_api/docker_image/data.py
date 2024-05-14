#! -*- coding: utf:8 -*-
""" Docker image data module """

import logging
from flask import current_app as app
from sqlalchemy.sql import or_
from .constants import PRE_BUILD, CUSTOM_BUILD, PRE_BUILD_SPCS, CUSTOM_BUILD_SPCS
from .models import DockerImage, DockerImageTag, db, Resource, DockerImageExtraAttribute
# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.docker_image")


# pylint: disable=R0912, too-many-statements
def insert_data(record, image):
    """ insert data in docker image table"""
    # pylint: disable=too-many-branches,too-many-statements
    if record is None:
        executor_resource_id = None
        if image["name"] == "SAS":
            resource_id = Resource.query.filter(Resource.name == "Large").first().id
        elif image["name"] == "Spark Distributed":
            resource_id = Resource.query.filter(Resource.name == "Small").first().id
            executor_resource_id = Resource.query.filter(Resource.name == "Medium").first().id
        else:
            resource_id = Resource.query.filter(Resource.name == "Medium").first().id
        # create image
        docker_image = DockerImage(
            name=image["name"],
            docker_url=image["docker_url"],
            gpu_docker_url=image["gpu_docker_url"],
            type=image.get('type', PRE_BUILD),
            description="Prebuilt image",
            icon=image["icon"],
            created_by="system",
            updated_by="system",
            kernel_type=image["kernel_type"],
            resource_id=resource_id,
            base_template=image.get("base_template", None),
            package_type=image.get("package_type", None),
            executor_resource_id=executor_resource_id,
            number_of_executors=image.get("number_of_executors", None)
        )
        db.session.add(docker_image)

        # create tags
        for tag in image["tags"]:
            docker_image_tag = DockerImageTag(
                docker_image=docker_image,
                tag=tag,
                created_by="system",
                updated_by="system"
            )
            db.session.add(docker_image_tag)
    else:
        # update data
        setattr(record, "name", image["name"])
        setattr(record, "icon", image["icon"])
        setattr(record, "docker_url", image["docker_url"])
        setattr(record, "gpu_docker_url", image["gpu_docker_url"])
        setattr(record, "kernel_type", image["kernel_type"])
        setattr(record, "type", image.get('type', PRE_BUILD))
        setattr(record, "description", "Prebuilt image")
        setattr(record, "created_by", "system")
        setattr(record, "updated_by", "system")
        setattr(record, "base_template", image.get("base_template", None))
        setattr(record, "package_type", image.get("package_type", None))
        setattr(record, "number_of_executors", image.get("number_of_executors", None))

        if image["name"] == "SAS":
            resource_id = Resource.query.filter(Resource.name == "Large").first().id
            setattr(record, "resource_id", resource_id)
        elif image["name"] == "Spark Distributed":
            resource_id = Resource.query.filter(Resource.name == "Small").first().id
            setattr(record, "resource_id", resource_id)
            executor_resource_id = Resource.query.filter(Resource.name == "Medium").first().id
            setattr(record, "executor_resource_id", executor_resource_id)
        else:
            resource_id = Resource.query.filter(Resource.name == "Medium").first().id
            setattr(record, "resource_id", resource_id)
        db.session.add(record)

        # Update tags
        for tag in image["tags"]:
            tag_record = (
                db.session.query(DockerImageTag).filter(
                    DockerImageTag.tag == tag,
                    DockerImageTag.docker_image_id == record.id).first()
            )
            if tag_record is None:
                docker_image_tag = DockerImageTag(
                    docker_image=record,
                    tag=tag,
                    created_by="system",
                    updated_by="system"
                )
                db.session.add(docker_image_tag)
            else:
                setattr(tag_record, "docker_image", record)
                setattr(tag_record, "tag", tag)
                setattr(record, "created_by", "system")
                setattr(record, "updated_by", "system")
                db.session.add(tag_record)


def insert_data_extra_attribute(record):
    """ Update /insert extra attrubute for docker image"""
    exists_already = (db.session.query(DockerImageExtraAttribute).filter(
                DockerImageExtraAttribute.base_image_id ==
                record.as_dict().get('base_image_id')).first())

    if exists_already:
        # update
        setattr(exists_already, "base_image_id", record.as_dict().get('base_image_id'))
        setattr(exists_already, "created_by", record.as_dict().get('created_by'))
        setattr(exists_already, "updated_by", record.as_dict().get('updated_by'))
        setattr(exists_already, "port", record.as_dict().get('port'))
        setattr(exists_already, "cmd", record.as_dict().get('cmd'))
        setattr(exists_already, "args", record.as_dict().get('args'))
        setattr(exists_already, "base_url_env_key", record.as_dict().get('base_url_env_key'))
        setattr(exists_already, "base_url_env_value", record.as_dict().get('base_url_env_value'))
        setattr(exists_already, "container_uid", record.as_dict().get('container_uid'))

        print("updating extra attribute for base_image_id : "
              "{0}".format(record.as_dict().get('base_image_id')))
        db.session.add(exists_already)
    else:
        # insert
        print("inserting extra attribute for base_image_id : "
              "{0}".format(record.as_dict().get('base_image_id')))
        db.session.add(record)


def delete_image(image):
    """ Remove image records from DB """
    log.debug("inside delete_image function")
    records = (db.session.query(DockerImage).filter(
        DockerImage.name == image,
        or_(DockerImage.type == PRE_BUILD,
            DockerImage.type == PRE_BUILD_SPCS),
        or_(DockerImage.base_image_id == None,
            DockerImage.base_image_id == DockerImage.id)).all())

    from .manager import delete_docker_image
    for record in records:
        custom_templates = (db.session.query(DockerImage).filter(
                            DockerImage.name == image,
                            or_(DockerImage.type == CUSTOM_BUILD_SPCS,
                                DockerImage.type == CUSTOM_BUILD),
                            or_(DockerImage.base_image_id == record.id,
                                DockerImage.base_image_id != DockerImage.id)).all())
        for custom in custom_templates:
            delete_docker_image(custom.id)
        delete_docker_image(record.id)
    log.debug("end of delete_image function")


def load_data():
    """ master records for docker image """
    # pylint: disable=import-outside-toplevel
    from .image_information.docker_images import DOCKER_IMAGES

    try:
        for image in DOCKER_IMAGES:
            record = (db.session.query(DockerImage).filter(
                DockerImage.name == image["name"],
                or_(DockerImage.type == PRE_BUILD,
                    DockerImage.type == PRE_BUILD_SPCS),
                or_(DockerImage.base_image_id == None,
                    DockerImage.base_image_id == DockerImage.id))).first()
            insert_data(record, image)
            db.session.flush()
            db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    try:
        for image in DOCKER_IMAGES:
            record = (db.session.query(DockerImage).filter(
                DockerImage.name == image["name"],
                or_(DockerImage.type == PRE_BUILD,
                    DockerImage.type == PRE_BUILD_SPCS),
                or_(DockerImage.base_image_id == None,
                    DockerImage.base_image_id == DockerImage.id))).first()
            # pylint: disable=bad-continuation, trailing-whitespace, line-too-long

            if record.as_dict().get("name") in ["Python-3.8-Snowpark", "Python-3.9-Snowpark"]:
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
                    container_uid=image.get("container_uid")

                )
                insert_data_extra_attribute(docker_image_extra_attribute)
            elif record.as_dict().get("name") in ["Python-3.8", "Python-3.9", "Python-3.10"]:
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
                    container_uid=image.get("container_uid")
                )
                insert_data_extra_attribute(docker_image_extra_attribute)
            elif record.as_dict().get("name") in ["RStudio-4.1"]:
                docker_image_extra_attribute = DockerImageExtraAttribute(
                    created_by="system",
                    updated_by="system",
                    port='8888',
                    base_url_env_key='BASE_URL',
                    base_url_env_value='BASE_URL_VALUE',
                    base_image_id=record.as_dict().get("id"),
                    container_uid=image.get("container_uid")
                )
                insert_data_extra_attribute(docker_image_extra_attribute)
            elif record.as_dict().get("name") == "SAS":
                docker_image_extra_attribute = DockerImageExtraAttribute(
                    created_by="system",
                    updated_by="system",
                    port='8989',
                    base_url_env_key='SERVER_SERVLET_CONTEXT_PATH',
                    base_url_env_value='BASE_URL_VALUE',
                    base_image_id=record.as_dict().get("id"),
                    container_uid=image.get("container_uid")
                )
                insert_data_extra_attribute(docker_image_extra_attribute)
            elif record.as_dict().get("name") in ["Jupyterlab-3.8", "Jupyterlab-3.9", "Jupyterlab-3.10"]:
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
                    container_uid=image.get("container_uid")
                )
                insert_data_extra_attribute(docker_image_extra_attribute)

            elif record.as_dict().get("name") in ["VSCode-JDK11", "VSCode-Python-3.9"]:
                docker_image_extra_attribute = DockerImageExtraAttribute(
                    created_by="system",
                    updated_by="system",
                    port='8080',
                    base_url_env_key='BASE_URL',
                    base_url_env_value='BASE_URL_VALUE',
                    base_image_id=record.as_dict().get("id"),
                    container_uid=image.get("container_uid")
                )
                insert_data_extra_attribute(docker_image_extra_attribute)

        db.session.flush()
        db.session.commit()
        if app.config["DEFAULT_HOST"] == "ga.fosfor.com" \
                or app.config["DEFAULT_HOST"] == "refract.fosfor.com":
            delete_image("SAS")
        delete_image("Ubuntu")
        delete_image("Zeppelin")
        delete_image("Tensorflow-3.6")
        delete_image("Scipy-3.6")

    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
