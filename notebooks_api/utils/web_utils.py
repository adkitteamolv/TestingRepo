import requests
def auth_call(url="", username="", pwd=""):
    response = requests.get(url=url,
                            auth=(username,pwd))
    return response


def get_call(url = "", headers= None):
    response = requests.get(url=url, headers=headers)
    return response


def put_call(url = "", headers= None, data = None):
    response = requests.put(
        url,
        json=data,
        headers=headers,
    )
    return response


def delete_call(url = "", headers= None, data = None):
    response = requests.delete(url, headers=headers,
                             data=data)
    return response