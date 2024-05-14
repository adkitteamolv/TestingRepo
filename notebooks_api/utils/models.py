#! -*- coding: utf-8 -*-
"""utils for models"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

from notebooks_api.utils.defaults import default_id

# pylint: disable=invalid-name
db = SQLAlchemy()


class ModelMixin:
    """ Mixin for id and audit records """
    id = db.Column(db.String(60), primary_key=True, default=default_id)
    created_on = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_by = db.Column(db.String(60), nullable=False, index=True)
    updated_on = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow,
                           index=True)
    updated_by = db.Column(db.String(60), nullable=False, index=True)

    def __repr__(self):
        """ String representation """
        return "<{}: {}>".format(self.__class__.__name__, self.name)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
