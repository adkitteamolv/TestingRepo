#! -*- coding: utf-8 -*-
"""Pypi tables module"""
from flask_sqlalchemy import SQLAlchemy
from notebooks_api.utils.defaults import default_id
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

# pylint: disable=invalid-name
db = SQLAlchemy()


# pylint: disable=too-few-public-methods
class Package(db.Model):
    """ Model for package """
    __tablename__ = "nb_external_package"

    id = db.Column(db.String(60), primary_key=True, default=default_id, unique=True)
    package_name = db.Column(db.String(200), nullable=False, index=True)
    package_version = db.Column(db.String(200), nullable=True)
    language = db.Column(db.String(200), nullable=False)
    language_version = db.Column(db.String(200), nullable=True)


# pylint: disable=too-few-public-methods
class PackageVersion(db.Model):
    """ Model for package version  """
    __tablename__ = "nb_external_package_version"

    id = db.Column(db.String(60), primary_key=True, default=default_id)
    version = db.Column(db.Text, nullable=False)

    # relationships
    package_id = db.Column(db.String(60), db.ForeignKey(Package.id, ondelete="CASCADE"), index=True)
    package = db.relationship(Package, backref="version")
