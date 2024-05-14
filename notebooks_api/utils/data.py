#! -*- coding: utf-8 -*-
"""Utils data module"""
from flask import g


def remove_audit(data):
    """
    Method to remove audit records as input
    :param data:
    :return:
    """
    keys = ("created_on", "created_by", "updated_on", "updated_by")
    for key in keys:
        data.pop(key, None)
    return data


def add_audit(data, update=True):
    """
    Method to add audit records
    :param data:
    :param update:
    :return:
    """
    user_id = g.user["mosaicId"]
    if update:
        data.update({
            "updated_by": user_id,
        })
    else:
        data.update({
            "created_by": user_id,
            "updated_by": user_id,
        })
    return data


def clean_data(data, update=False):
    """
    Method to clean the input data
    :param data:
    :param update:
    :return:
    """
    data = remove_audit(data)
    data = add_audit(data, update=update)
    return data
