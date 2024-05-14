# -*- coding: utf-8 -*-

""" Abstract class for GitClient """


# pylint: disable=invalid-name
# log = get_logger("mosaic_version_control.clients")


class GitClient:
    """Abstract class for implementing a git client."""

    provider = 'unknown'

    def create_repo(self, repo_name):
        """Create a new repository."""
        raise NotImplementedError

    def rename_repo(self, project_name, new_project_name, project_id):
        """Rename repository."""
        raise NotImplementedError

    def create_branch(self, repo_name, branch_name, start_point='master'):
        """Create a new branch."""
        raise NotImplementedError

    def delete_branch(self, repo_name, branch_name):
        """Delete the existing branch."""
        raise NotImplementedError

    def fetch_branches(self, repo_name):
        """Fetch all the branches of the given repository."""
        raise NotImplementedError

    # pylint: disable=line-too-long,too-many-arguments
    def create_file(self, repo_name, file_path, file_content,
                    branch_name='master', message='file created'):
        """Add a new file to the repository."""
        raise NotImplementedError

    def read_file(self, repo_name, file_path, branch_name='master'):
        """Read a file from the repository."""
        raise NotImplementedError

    # pylint: disable=line-too-long,too-many-arguments
    def update_file(self, file_path, file_content, enabled_repo,
                    message='file updated'):
        """Update the contents of a file in the repository."""
        raise NotImplementedError

    def delete_file(self, repo_name, file_path,
                    branch_name='master', message='file deleted'):
        """Delete the file from the repository."""
        raise NotImplementedError

    def list_files(self, repo_name, file_path, branch="master", limit=None):
        """Read a file from the repository."""
        raise NotImplementedError

    def list_files_with_content(self, repo_name, file_path):
        """ Read a file from the repository """
        raise NotImplementedError

    def get_latest_commit(self, repo_url, access_token):
        """Get the latest commit id from the git repository."""
        raise NotImplementedError

    def rename_all_repos(self):
        """Read a list of repositories."""
        raise NotImplementedError

    def get_commits(self, project_id):
        """Returns a list of commits for specified project id."""
        raise NotImplementedError

    def get_files(self, project_id, commit_id):
        """Returns a list of file changed for  specified commit id."""
        raise NotImplementedError

    def validate_repo_access(self):
        """Returns valid if user have valid repository access"""
        raise NotImplementedError

    def download_file(self, repo_name, file_path, branch="master"):
        """Returns file to be downloaded if user have valid repository access"""
        raise NotImplementedError

    def download_folder(self, repo_name, file_path, branch="master"):
        """Returns zipped folder to be downloaded if user have valid repository access"""
        raise NotImplementedError