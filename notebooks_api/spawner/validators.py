# -*- coding: utf-8 -*-

"""validators module for mosaic kubespawner"""


def check_async_value(data):
    """Method to check async value"""
    if "async" not in data:
        print("async not in data")
        data["async"] = False
        return data["async"]
    if not isinstance(data.get("async"), bool):
        raise ValueError("Async needs to be boolean")
    print(data.get("async"))
    return data.get("async")
