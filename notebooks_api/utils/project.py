#! -*- coding: utf-8 -*-
"""Project utils module"""

import logging

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


# pylint: disable=unused-argument
def create_repo_name(project_label, project_id):
    """Create repo name method"""
    return project_id


def rename_repo(project_label, new_project_name, project_id):
    """Rename repo method"""
    return '{} {} {}'.format(project_label, new_project_name, project_id)
