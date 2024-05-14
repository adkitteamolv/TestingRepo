#! -*- coding: utf-8 -*-
"""Mosaic project tags module"""

# pylint: disable=inconsistent-return-statements
def get_tag(key, tags, split=False):
    """
    Method to get the tag from list of tags

    Args:
        key (str) - name of the tag
        tags (list) - list of tags
        split (bool)

    Return:
        str
    """
    for tag in tags:
        if tag and tag.startswith(key):
            _, val = tag.split("=")
            if split:
                return key, val
            return tag




def get_tag_val(key, tags):
    """
    Method to get the tag value from the list of tags
    :param key:
    :param tags:
    :return:
    """
    tag_key = ""
    tag_val = ""
    if tags:
        tag = get_tag(key, tags, split=False)
        if tag:
            tag_key, tag_val = tag.split("=")
    return tag_key, tag_val


def get_project_val(project):
    """
    Method to get the project id value from the list of tags
    :param project:
    :return:
    """
    project_id = ''
    if project is not None:
        data = project.split("=")
        # return data at 1 mean it return project value
        if data is not None and len(data) > 1:
            project_id = data[1]
    return project_id
