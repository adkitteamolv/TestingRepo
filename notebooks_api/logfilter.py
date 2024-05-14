import logging
from flask import g


class ParameterFilter(logging.Filter):
    def filter(self, record):
        if "user" in g:
            data = {
                "user_id": g.user.get("mosaicId", None),
                "project_id": g.user.get("project_id", None),
                "url": g.user.get("url", None)
            }
        else:
            data = {
                "user_id": None,
                "project_id": None,
                "url": None
            }
        record.__dict__.update(data)
        return True
