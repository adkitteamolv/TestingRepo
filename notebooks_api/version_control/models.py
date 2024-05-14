import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import g

db = SQLAlchemy()


class Version(db.Model):
    __tablename__ = "version_metadata"
    id = db.Column(db.Integer, primary_key=True, )
    component_type = db.Column(db.String(255), unique=False, nullable=False)
    component_id = db.Column(db.String(255), unique=False, nullable=False)
    project_id = db.Column(db.String(255), unique=False, nullable=False)
    commit_id = db.Column(db.String(255), unique=False, nullable=False)
    commit_message = db.Column(db.String(255), unique=False, nullable=False)
    version_number = db.Column(db.String(255), unique=False, nullable=False)
    checked_in_by = db.Column(db.String(255),
                              unique=False,
                              nullable=False,
                              default=lambda: g.user['mosaicId'])
    checked_in_time = db.Column(db.DateTime(),
                                default=db.func.now(),
                                unique=False,
                                nullable=False)
    data = db.Column(db.JSON)

    def as_dict(self):
        """ Dict representation """
        return {c.name: str(getattr(self, c.name)) if isinstance(getattr(self, c.name), datetime.datetime) else getattr(self, c.name) for c in self.__table__.columns}
