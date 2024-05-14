#! -*- coding: utf-8 -*-
"""Notebook models module"""

from datetime import datetime
from flask import g, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property

# pylint: disable=unused-import
from notebooks_api.docker_image.models import DockerImage, DockerImageTag, DockerImageExtraAttribute
from notebooks_api.resource.models import Resource
from notebooks_api.utils.defaults import default_resource
from notebooks_api.utils.models import ModelMixin
from notebooks_api.utils.defaults import default_id

from .constants import PodStatus, RepoStatus, RepoType, Accesstype, RepoAccessCategory
from ..utils.encryption import PasswordStoreFactory

# pylint: disable=invalid-name
db = SQLAlchemy()


# pylint: disable=too-few-public-methods
class DataSnapshot(db.Model, ModelMixin):
    """ Model for data snapshot """
    __tablename__ = "nb_data_snapshot"

    snapshot_name = db.Column(db.String(200), nullable=False)
    container = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.String(100), nullable=False)
    project_name = db.Column(db.String(100), nullable=False)
    git_repo = db.Column(db.String(100))
    commit_id = db.Column(db.String(100))
    branch = db.Column(db.String(100))
    snapshot_input_path = db.Column(db.String(200))
    snapshot_path = db.Column(db.String(200), nullable=False)
    snapshot_life = db.Column(db.Integer, default=90)
    access_type = db.Column(db.String(50))


# pylint: disable=too-few-public-methods
class Notebook(db.Model, ModelMixin):
    """ Model for notebook """
    __tablename__ = "nb_notebook"

    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(200))

    # relationships
    resource_id = db.Column(
        db.String(60),
        db.ForeignKey(
            Resource.id),
        default=default_resource)
    resource = db.relationship(Resource, backref="notebooks")

    docker_image_id = db.Column(db.String(60), db.ForeignKey(DockerImage.id))
    docker_image = db.relationship(DockerImage, backref="notebooks")


# pylint: disable=too-few-public-methods
class NotebookTag(db.Model, ModelMixin):
    """ Model for notebook tags """
    __tablename__ = "nb_notebook_tag"

    tag = db.Column(db.String(200), nullable=False, index=True)

    # relationships
    notebook_id = db.Column(
        db.String(60), db.ForeignKey(
            Notebook.id, ondelete="CASCADE"))
    notebook = db.relationship(Notebook, backref="tags")


# pylint: disable=too-few-public-methods
class NotebookPod(db.Model, ModelMixin):
    """ Model for NotebookPod """
    __tablename__ = "nb_notebook_pod"

    name = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(
            PodStatus.STARTING,
            PodStatus.RUNNING,
            PodStatus.STOPPING))

    notebook_id = db.Column(
        db.String(60), db.ForeignKey(
            Notebook.id, ondelete="CASCADE"))
    notebook = db.relationship(Notebook, backref="pod")


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class NotebookPodArchive(db.Model, ModelMixin):
    """ Model for notebook pod archive"""
    __tablename__ = "nb_notebook_pod_archive"

    name = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(
            PodStatus.STARTING,
            PodStatus.RUNNING,
            PodStatus.STOPPING))

    # relationships
    notebook_id = db.Column(
        db.String(60), db.ForeignKey(
            Notebook.id, ondelete="CASCADE"))
    notebook = db.relationship(Notebook, backref="pod_archive")


class TemplateStatus(db.Model):
    """Module for template status"""
    __tablename__ = "nb_template_status"
    id = db.Column(db.String(60), primary_key=True, default=default_id)
    created_by = db.Column(
        db.String(60),
        nullable=False,
        default=lambda: g.user['mosaicId'])
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, onupdate=datetime.utcnow, nullable=True)
    template_id = db.Column(db.String(60), db.ForeignKey(DockerImage.id))
    status = db.Column(
        db.Enum(
            PodStatus.STARTING,
            PodStatus.RUNNING,
            PodStatus.STOPPING))
    resource_id = db.Column(
        db.String(60),
        db.ForeignKey(
            Resource.id),
        default=default_resource)
    project_id = db.Column(db.String(60))
    pod_name = db.Column(db.Text)
    repo_id = db.Column(db.String(60))
    repo_name = db.Column(db.String(200))
    branch_name = db.Column(db.String(60))
    input = db.Column(db.String(200), nullable=True)
    output = db.Column(db.String(200), nullable=True)
    spcs_data = db.Column(db.JSON, default={})

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class GitRepo(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository"
    created_by = db.Column(db.String(100), default=lambda: g.user['mosaicId'])
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified_by = db.Column(db.String(100), default=lambda: g.user['mosaicId'])
    last_modified_on = db.Column(db.DateTime, default=datetime.utcnow)
    repo_id = db.Column(db.String(60), primary_key=True, default=default_id)
    project_id = db.Column(db.String(60))
    repo_url = db.Column(db.String(255))
    username = db.Column(db.String(60), nullable=True)
    _password = db.Column('password', db.Text)
    branch = db.Column(db.String(255))
    access_category = db.Column(db.Enum(RepoAccessCategory.PRIVATE, RepoAccessCategory.PUBLIC))
    proxy_details = db.Column('proxy_details', db.Text, nullable=True)

    @hybrid_property
    def password(self):
        """
        :return:
        """
        return PasswordStoreFactory(current_app.config["PASSWORD_STORE"],
                                    self.__tablename__).retrieve(self._password)

    @password.expression
    def password(self):
        """
        :return:
        """
        return self._password

    @password.setter
    def password(self, value):
        """
        :param value:
        :return:
        """
        self._password = PasswordStoreFactory(current_app.config["PASSWORD_STORE"],
                                              self.__tablename__).store(value)

    repo_name = db.Column(db.String(200))
    repo_status = db.Column(
        db.Enum(RepoStatus.Enabled,
                RepoStatus.Disabled),
        default=RepoStatus.Enabled)
    base_folder = db.Column(db.String(60))
    repo_type = db.Column(
        db.Enum(RepoType.GIT,
                RepoType.BITBUCKET,
                RepoType.GITLAB,
                RepoType.AZUREDEVOPS))

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class GitRepoActive(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository_active"
    id = db.Column(db.String(60), primary_key=True, default=default_id)
    repo_id = db.Column(
        db.String(60), db.ForeignKey(
            GitRepo.repo_id, ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    branch_id = db.Column(db.String(60), nullable=True)


class AdUser(db.Model):
    """
    Model for ad user
    """
    __tablename__ = "ad_user"
    user_id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_name = db.Column(db.String(120), nullable=False)
    mosaic_user = db.Column(db.String(120), nullable=False, unique=True)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}



class AdGroup(db.Model):
    """
    Model for ad group
    """
    __tablename__ = "ad_group"
    group_id = db.Column(db.Integer, primary_key=True, nullable=False)
    group_name = db.Column(db.String(120), nullable=False)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class AdMapping(db.Model):
    """
    Model for ad mapping
    """
    __tablename__ = "ad_mapping"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    group_id = db.Column(db.Integer, nullable=False)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class GitRepoBranches(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository_branches"
    branch_id = db.Column(db.String(60), primary_key=True, default=default_id)
    repo_id = db.Column(
        db.String(60), db.ForeignKey(
            GitRepo.repo_id, ondelete="CASCADE"), nullable=False)
    branch_name = db.Column(db.String(60), nullable=False)
    default_flag = db.Column(db.Boolean, default=False)
    freeze_flag = db.Column(db.Boolean, default=False)
    share_flag = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(100), default=lambda: g.user['mosaicId'])
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified_by = db.Column(db.String(100), default=lambda: g.user['mosaicId'])
    last_modified_on = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class NotebookPodMetrics(db.Model, ModelMixin):
    """ Model to store Notebookpod Metrics """

    __tablename__ = "nb_notebook_pod_metrics"

    max_memory = db.Column(db.Float, nullable=False)
    max_cpu = db.Column(db.Float, nullable=False)

    project_id = db.Column(db.String(100), nullable=False)
    template_id = db.Column(db.String(60), db.ForeignKey(TemplateStatus.id, ondelete="CASCADE"))
    template_status = db.relationship(TemplateStatus, backref="template_status")


class NotebookPodResources(db.Model):
    """
    Model to store the pod names having cpu and memory utilization
    greater than equal to 80%
    """
    __tablename__ = "nb_pod_resource_alerts"
    id = db.Column(db.String(60), primary_key=True, default=default_id)
    new_pods = db.Column(db.String(500), nullable=True)
    existing_pods = db.Column(db.String(500), nullable=True)
    usage_percent = db.Column(db.Float, nullable=True)
    resource_type = db.Column(db.String(100), nullable=True)
    project_id = db.Column(db.String(500), nullable=True)
    project_name = db.Column(db.String(500), nullable=True)
    template_name = db.Column(db.String(500), nullable=True)
    template_id = db.Column(db.String(500), nullable=True)
    user_name = db.Column(db.String(500), nullable=True)
    alert_status = db.Column(db.Boolean, default=False)
