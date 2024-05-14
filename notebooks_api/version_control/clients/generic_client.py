import gitlab

from flask import Flask
from mosaic_utils.ai.logger.utils import log_decorator
from . import get_client
from .github_client import GitHubClient
from .gitlab_client import GitLabClient


class GenericClient:

    def __init__(self, provider, url, token, namespace, repo_name, file_path):
        config = {"repo_type": provider, "repo_url": url, "password": token}
        self.git_client = get_client(config)
        if file_path is None:
            self.file_path = '/'
        else:
            self.file_path = file_path
        self.repo_name = repo_name
        self.files = None

    @log_decorator
    def generic_list_files(self):
        if self.git_client is None:
            return []
        self.files = self.git_client.list_files(self.repo_name, self.file_path)
        return self.files
