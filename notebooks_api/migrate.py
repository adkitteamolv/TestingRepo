""" Migrate module """
import os
import logging
import requests
from flask import Flask

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.migration.log")


# pylint: disable=too-few-public-methods
class Headers:
    """ Headers constants """
    authorization = "Authorization"
    x_auth_userid = "X-Auth-Userid"
    x_auth_username = "X-Auth-Username"
    x_auth_email = "X-Auth-Email"


# pylint: disable=invalid-name
app = Flask(__name__)

log.debug("Renaming GitLab projects")
# initialize settings
# pylint: disable=invalid-name
base_path = os.path.dirname(os.path.realpath(__file__)) + "/src/notebooks_api/"
default = os.path.join(base_path, "configs", "test.cfg")
config_file = os.getenv("NOTEBOOKS_API_SETTINGS", default)
app.config.from_pyfile(config_file)

git_server_url = app.config["VCS_BASE_URL"]

request_url = "{}/repo/rename/all".format(git_server_url)
# pylint: disable=logging-too-many-args
log.debug("Request URL - ", request_url)
headers = {
    Headers.x_auth_username: "TestUser",
    Headers.x_auth_email: "TestUser@lntinfotech.com",
    Headers.x_auth_userid: "0123456789",
}

response = requests.get(request_url, headers=headers)
response.raise_for_status()
log.debug("Response status- ", response.status_code)
log.debug("Response data- ", response.json())
print(response.json())
