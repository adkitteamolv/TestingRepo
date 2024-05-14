#! -*- coding: utf-8 -*-
"""Plugin models module"""
# pylint: disable=unused-import
from flask_sqlalchemy import SQLAlchemy

# pylint: disable=unused-import
from notebooks_api.utils.models import ModelMixin
from notebooks_api.utils.defaults import default_id

from .constants import CUSTOM_BUILD, PRE_BUILD, ENABLED, DISABLED, RefractSections

# pylint: disable=invalid-name
db = SQLAlchemy()


# pylint: disable=too-few-public-methods
class PluginDockerImage(db.Model):
    """ Model for notebook """
    __tablename__ = "cp_docker_image"

    id = db.Column(db.String(60), primary_key=True, default=default_id)
    base_image_type = db.Column(db.String(100), unique=True, nullable=False)
    docker_url = db.Column(db.String(200), nullable=False)


# pylint: disable=too-few-public-methods
class CustomPlugins(db.Model, ModelMixin):
    """ Model for plugin data """
    __tablename__ = "cp_plugins"

    id = db.Column(db.String(60), primary_key=True, default=default_id)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(100))
    plugin_type = db.Column(db.Enum(PRE_BUILD, CUSTOM_BUILD), default='PRE_BUILD')
    type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(ENABLED, DISABLED))
    input_form_type = db.Column(db.String(10), nullable=False)
    input_parameter_json = db.Column(db.JSON, default={})
    input_parameter_file_name = db.Column(db.String(100), default="")
    base_image_type = db.Column(db.String(60), db.ForeignKey(PluginDockerImage.base_image_type))
    plugin_code_source = db.Column(db.String(100))
    valid_sections = db.Column(db.Enum(RefractSections.MODEL,
                                       RefractSections.NOTEBOOK, RefractSections.DATA))
    execution_command = db.Column(db.String(200), default="")
    # UI elements
    icon = db.Column(db.String(100))
    width = db.Column(db.String(100), default="48px")
    height = db.Column(db.String(100), default="48px")
    color = db.Column(db.String(100))
    thumbnail = db.Column(db.String(5))
    multiInputNode = db.Column(db.String(length=5), server_default="true")
    nodeBackgroundColor = db.Column(db.String(5))
    alert_parameters = db.Column(db.JSON, default={})
    package_name = db.Column(db.String(100))
    package_version = db.Column(db.String(100))
    model_required = db.Column(db.Boolean, default=False)

# pylint: disable=too-few-public-methods
class CustomPluginsSettings(db.Model):
    """ Model for notebook """
    __tablename__ = "cp_plugin_settings"

    id = db.Column(db.String(60), primary_key=True, default=default_id)
    plugin_id = db.Column(db.String(60), db.ForeignKey(CustomPlugins.id))
    object_info = db.Column(db.JSON)
    advanceSettings = db.Column(db.JSON)
