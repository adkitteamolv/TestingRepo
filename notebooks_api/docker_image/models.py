#! -*- coding: utf-8 -*-
""" Docker image tables """
from flask_sqlalchemy import SQLAlchemy
from flask import current_app
from sqlalchemy.ext.hybrid import hybrid_property

from notebooks_api.resource.models import Resource
from notebooks_api.utils.defaults import default_resource
from notebooks_api.utils.models import ModelMixin

from .constants import CUSTOM_BUILD, PRE_BUILD, CUSTOM_BUILD_SPCS, PRE_BUILD_SPCS
from ..utils.encryption import PasswordStoreFactory

# pylint: disable=invalid-name
db = SQLAlchemy()


# pylint: disable=too-few-public-methods
class DockerImage(db.Model, ModelMixin):
    """ Model for docker image """
    __tablename__ = "nb_docker_image"

    type = db.Column(db.Enum(PRE_BUILD, CUSTOM_BUILD, PRE_BUILD_SPCS, CUSTOM_BUILD_SPCS))
    icon = db.Column(db.String(200))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    docker_url = db.Column(db.String(200), nullable=False)
    gpu_docker_url = db.Column(db.String(200), nullable=True)
    pip_packages = db.Column(db.Text)
    init_script = db.Column(db.Text)
    conda_packages = db.Column(db.Text)
    docker_file = db.Column(db.Text)
    kernel_type = db.Column(db.String(200), nullable=False)
    cran_packages = db.Column(db.JSON)
    index_url = db.Column(db.Text)
    auto_commit = db.Column(db.Boolean, default=True)
    _git_macros_config = db.Column('git_macros_config', db.Text, nullable=True)

    @hybrid_property
    def git_macros_config(self):
        """
        Getter
        :return:
        """
        return PasswordStoreFactory(current_app.config["PASSWORD_STORE"], self.__tablename__). \
            retrieve(self._git_macros_config, coerce_dtype=True)

    @git_macros_config.setter
    def git_macros_config(self, git_macros_config):
        """
        Setter
        :param git_macros_config:
        :return:
        """
        self._git_macros_config = PasswordStoreFactory(current_app.config["PASSWORD_STORE"],
                                                       self.__tablename__).store(git_macros_config)

    @git_macros_config.expression
    def git_macros_config(self):
        """
        :return:
        """
        return self._git_macros_config

    # relationships
    base_image_id = db.Column(
        db.String(60),
        db.ForeignKey("nb_docker_image.id"))
    base_image = db.relationship(
        "DockerImage",
        backref=db.backref("base_docker_image", remote_side="DockerImage.id")
    )

    resource_id = db.Column(
        db.String(60),
        db.ForeignKey(
            Resource.id),
        default=default_resource)
    resource = db.relationship(Resource, foreign_keys=[resource_id])
    template_tag = db.relationship("DockerImageTag", backref="tags")
    base_template = db.Column(db.String(100))
    package_type = db.Column(db.String(20))
    executor_resource_id = db.Column(
        db.String(60),
        db.ForeignKey(
            Resource.id),
        default=default_resource)
    number_of_executors = db.Column(db.Integer)
    executor_resource = db.relationship(Resource, foreign_keys=[executor_resource_id])
    spcs_data = db.Column(db.JSON, default={})



# pylint: disable=too-few-public-methods
class DockerImageTag(db.Model, ModelMixin):
    """ Model for docker image tags """
    __tablename__ = "nb_docker_image_tag"

    tag = db.Column(db.String(200), nullable=False, index=True)

    # relation ships
    docker_image_id = db.Column(
        db.String(60), db.ForeignKey(
            DockerImage.id, ondelete="CASCADE"))
    docker_image = db.relationship(DockerImage, backref="tags")


class DockerImageExtraAttribute(db.Model, ModelMixin):
    """ Model for docker image """
    __tablename__ = "nb_docker_image_extra_attributes"

    port = db.Column(db.String(10), nullable=False)
    cmd = db.Column(db.String(500), nullable=True)
    args = db.Column(db.String(500), nullable=True)
    base_url_env_key = db.Column(db.String(50), nullable=True)
    base_url_env_value = db.Column(db.String(50), nullable=True)
    container_uid = db.Column(db.String(6), nullable=False)

    # relationships
    base_image_id = db.Column(
        db.String(60),
        db.ForeignKey("nb_docker_image.id"))
