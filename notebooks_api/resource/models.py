#! -*- coding: utf-8 -*-
"""Models for resources"""
from flask_sqlalchemy import SQLAlchemy

from notebooks_api.utils.models import ModelMixin
from .constants import ResourceStatus


# pylint: disable=invalid-name
db = SQLAlchemy()


# pylint: disable=too-few-public-methods
class Resource(db.Model, ModelMixin):
    """ Model for notebook """
    __tablename__ = "nb_resource"

    name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    cpu = db.Column(db.String(10), nullable=False)
    mem = db.Column(db.String(10), nullable=False)
    extra = db.Column(db.String(200))
    status = db.Column(
        db.Enum(
            ResourceStatus.ENABLED,
            ResourceStatus.DISABLED
            ),
        default=ResourceStatus.ENABLED
    )
