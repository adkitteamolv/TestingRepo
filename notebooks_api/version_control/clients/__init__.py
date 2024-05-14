# -*- coding: utf-8 -*-
"""Different client implementation for different service providers."""

import logging
from requests.exceptions import MissingSchema
from flask import current_app
from mosaic_utils.ai.logger.utils import log_decorator
from gitlab.exceptions import GitlabHttpError
from .base import GitClient
from .github_client import GitHubClient
from .gitlab_client import GitLabClient
from .bitbucket_client import BitBucketClient
from .azdevops_client import AzureDevopsClient

# pylint: disable=invalid-name
# log = logging.getLogger("mosaic_version_control.clients")


# pylint: disable=inconsistent-return-statements
@log_decorator
def get_client(application):
    """ lookup all available clients and return the correct client """
    clients = GitClient.__subclasses__()
    git_provider = application.get("repo_type", None)
    default_git_provider = (application.get("GIT_PROVIDER", None))
    for client in clients:
        if git_provider and client.provider == git_provider.lower():
            try:
                client_obj = client()
                client_obj.set_up(application)
                return client_obj
            except MissingSchema as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None
            except GitlabHttpError as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None
            except Exception as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None

        if default_git_provider and client.provider == default_git_provider:
            try:
                client_obj = client()
                client_obj.default_set_up(application)
                return client_obj
            except MissingSchema as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None
            except GitlabHttpError as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None
            except Exception as ex:
                current_app.logger.error("Configurations are not valid - " + str(ex))
                return None
