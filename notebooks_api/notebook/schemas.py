# -*- coding: utf-8 -*-
"""Schemas for mosaic ai backend views"""
from marshmallow import fields, schema, validates_schema, ValidationError

# pylint: disable=too-few-public-methods
class GitRepo(schema.Schema):
    """Schema for GitRepo save"""
    repo_url = fields.Str(required=True, error_messages={"required": "repo_url is required"})
    branch = fields.Str(required=True, error_messages={"required": "branch is required"})
    repo_name = fields.Str(required=True, error_messages={"required": "repo_name is required"})
    username = fields.Str()
    password = fields.Str()
    base_folder = fields.Str()
    repo_type = fields.Str()
    project_id = fields.Str()
    access_category = fields.Str()
    repo_id = fields.Str()

    @validates_schema
    def validation(self, data, **kwargs):
        if len(data['branch']) == 0 or data['branch'].isspace():
            raise ValidationError("branch is required")
        if len(data['repo_name']) == 0 or data['repo_name'].isspace():
            raise ValidationError("repo_name is required")
