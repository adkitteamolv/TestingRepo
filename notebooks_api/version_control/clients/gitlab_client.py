# -*- coding: utf-8 -*-

"""GitClient implementation for GitLab."""
from uuid import UUID
import base64
import json
import os
from urllib.parse import urlparse, quote
import urllib
from gitlab import Gitlab
import gitlab
from mosaic_utils.ai.headers.constants import Headers
import requests
from .constants import GitlabConstants
from notebooks_api.utils.exceptions import (RepoAuthentiactionException,
                                InvalidBranchORBaseDirException,
                                VCSException, InvalidRepoUrlException,
                                ErrorCodes, RepoAccessException, MosaicException)
from mosaic_utils.ai.logger.utils import log_decorator
from .base import GitClient
from flask import g, current_app
from zipfile import ZipFile
from pathlib import Path
import shutil

# pylint: disable=invalid-name
# log = get_logger("mosic_version_control.github_client")


class GitLabClient(GitClient):
    """Gitclient implementation for gitlab."""

    provider = 'gitlab'

    def __init__(self, *args, **kwargs):
        """Initialize the gitlab client."""
        self.configuration = None
        self.client = None
        super().__init__(*args, **kwargs)

    @log_decorator
    def set_up(self, application):
            self.configuration = application
            git_url = urlparse(application["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            self.client = Gitlab(hostname, private_token=application["password"])

    @log_decorator
    def get_repo_name(self,repo_url):
        repo_name = urlparse(repo_url).path.replace(".git", "")[1:]
        return repo_name

    def get_repo(self, repo_name):
        """
        Return the required repo
        Args:
        repo_name: name of the repo (in path_with_namespace format)
        """
        try:
            repo_name_suffix = repo_name.rsplit('/', 1)[-1]
            repo = [project for project in
                    self.client.projects.list(membership=True, search=repo_name_suffix) if
                    project.path_with_namespace == repo_name][0]
            return repo
        except Exception as ex:
            current_app.logger.exception(ex)
            raise InvalidRepoUrlException

    @log_decorator
    def get_namespace(self, name):
        """
        Correct the repo name by prefixing namespace.

        Args:
            name: branch name or repo name to be namespaced
        """

        return urlparse(name).path.replace(".git","")[1:]

    @log_decorator
    def create_repo(self, repo_name, notebook_api=None):
        """
        Create a new repository.

        Args:
            repo_name (str): name of the repository
        Returns:
            dictionary
        """

        repo = self.client.projects.create({'name': repo_name})
        repo.files.create({
            'file_path': 'README.md',
            'branch': 'master',
            'content': '',
            'commit_message': 'initial commit',
        })
        return repo

    @log_decorator
    def rename_repo(self, project_name, new_project_name, project_id):
        """
        Rename repository.
        """
        flag = 0
        project_list = self.client.projects.list()

        for project in project_list:
            if project_name + "-" + project_id == project.name:
                print(project.name)
                projects = project
                projects.name = new_project_name + "-" + project_id
                projects.save()
                flag = 1
                return projects.name

        if flag == 0:
            print("No match found")
        return "No match found"

    @log_decorator
    def create_branch(self, repo_name, branch_name, start_point):
        """
        Create a new branch in the specified repository.

        Args:
            repo_name (str): name of the repository
            branch_name (str): name of the branch
            start_point (str): starting point for the new branch
        """
        repo_name = self.get_repo_name(repo_name)
        repo = self.get_repo(repo_name)
        if start_point is None:
            start_point = repo.default_branch
        repo.branches.create({'branch': branch_name, 'ref': start_point})
        branches = repo.branches.list()
   
    @log_decorator
    def delete_branch(self, repo_name, branch_name):
        """
        Delete the branch.

        Args:
            repo_name (str): name of the repo
            branch_name (str): name of the branch
        """
        repo_name = self.get_namespace(repo_name)
        repo = self.get_repo(repo_name)
        branch = repo.branches.get(branch_name)
        branch.delete()

    @log_decorator
    def fetch_branches(self, repo_name, proxy_details=None):
        """
        Fetch all the branches present in the repository.
        Args:
            repo_name (str): name of the repository
            proxy_details (dict): Dictionary containing proxy details required
            for connecting to git server via proxy, default is None
        Returns:
            List of dictionary
        """
        try:
            branches = []
            repo_name = self.get_repo_name(repo_name)
            repo = self.get_repo(repo_name)
            for branch in repo.branches.list(all=True):
                branches.append({
                    'name': branch.attributes['name'],
                    'sha': branch.attributes['commit']['id'],
                })
            return branches
        except gitlab.GitlabAuthenticationError as ex:
            current_app.logger.exception(ex)
            raise RepoAuthentiactionException
        except gitlab.exceptions.GitlabGetError as ex:
            current_app.logger.exception(ex)
            raise InvalidRepoUrlException
#TODO
        # Handle GitlabListError as well for guest user it is throwing 403
        except MosaicException as me:
            raise me
        except Exception as ex:
            current_app.logger.exception(ex)
            raise VCSException


    # pylint: disable=line-too-long,too-many-arguments
    @log_decorator
    def create_file(self, repo_name, file_path, file_content,
                    branch_name='master', message='file created'):
        """
        Add a new file to the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file
            file_content (str): file content
            message (str): commit message to be used
        """
        repo_name = self.get_namespace(repo_name)
        repo = self.get_repo(repo_name)
        repo.files.create({
            'file_path': file_path,
            'branch': branch_name,
            'content': file_content,
            'commit_message': message,
        })
        return {
            'sha': '',
            'url': '',
        }

    @log_decorator
    def read_file(self, repo_name, file_path, branch_name='master', raw_content=False, commit_type=False):
        """
        Read file from the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read
            branch_name (str): branch to be checked
            raw_content : Default False which returns html format contents else raw text format
        Returns:
            dictionary
        """
        # repo_name = self.get_namespace(repo_name)
        try:
            repo_name = self.get_repo_name(repo_name)
            repo = self.get_repo(repo_name)
            file_path = quote(file_path)
            file = repo.files.get(file_path=file_path, ref=branch_name)
            if raw_content:
                 _, file_extension = os.path.splitext(file_path)
                 if file_extension.lower() == '.ipynb':
                     content = json.loads(base64.b64decode(file.attributes['content']).decode('utf-8'))
                 else:
                     content = base64.b64decode(file.attributes['content']).decode('utf-8')
                 return {
                    'url': '',
                    'sha': file.attributes['commit_id'],
                    'content': content,
                    'encoding': file.attributes['encoding'],
                    }
            return {
                'url': '',
                'sha': file.attributes['commit_id'],
                'content': file.attributes['content'],
                'encoding': file.attributes['encoding'],
                }
        except gitlab.GitlabAuthenticationError as e:
            print("Git lab bad crendential error")
            raise RepoAuthentiactionException

    # pylint: disable=line-too-long,too-many-arguments
    @log_decorator
    def update_file(self, file_path, file_content, enabled_repo, message='file updated'):
        """
        Update file from the repository.

        Args:
            file_path (str): path of the file to be read
            file_content (str): content of the file
            enabled_repo (dict): enabled repo details
        """
        repo_name = enabled_repo["repo_url"]
        branch_name = enabled_repo.get("branch", "master")
        repo_name = self.get_namespace(repo_name)
        repo = self.get_repo(repo_name)

        if file_path.endswith(".ipynb"):
            repo.files.update(file_path, {'branch': branch_name,
                                          'content': json.dumps(file_content),
                                          'commit_message': message})
        else:
            repo.files.update(file_path, {'branch': branch_name,
                                          'content': file_content,
                                          'commit_message': message})

        return {
            'sha': '',
            'url': '',
        }

    #    @trace(logger=log)
    @log_decorator
    def delete_file(self, repo_name, file_path,
                    branch_name='master', message='file deleted'):
        """
        Delete file from the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read
            branch_name (str): branch to be checked
        """
        repo_name = self.get_namespace(repo_name)
        repo = self.get_repo(repo_name)
        file = repo.files.get(file_path=file_path, ref=branch_name)
        file.delete(branch=branch_name, commit_message=message)

    @log_decorator
    def list_files(self, repo_name, file_path, branch="master", limit=None):
        """
        Read file from the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read
            branch (str): branch name of the repository
            limit (int): The total no of files to be returned
        Returns:
            dictionary
        """
        if file_path in [None, ""]:
            file_path = '/'
        try:
            repo_name = self.get_repo_name(repo_name)
            repo = self.get_repo(repo_name)
            # tree = repo.repository_tree(file_path, all=True, ref=branch)  -> REF-104
            i = 1
            tree = []
            if limit:
                page = repo.repository_tree(file_path, per_page=limit, page=i, ref=branch)
                tree.extend(page)
            else:
                while True:
                    page = repo.repository_tree(file_path, per_page=100, page=i, ref=branch)
                    i = i + 1
                    if not page:
                        break
                    tree.extend(page)
                if not tree and file_path != "/":
                    raise InvalidBranchORBaseDirException
            return tree
        except gitlab.GitlabAuthenticationError as e:
            current_app.logger.exception(e)
            raise RepoAuthentiactionException
        except gitlab.exceptions.GitlabGetError as e:
            current_app.logger.exception(e)
            if (str(e.error_message).lower() == GitlabConstants.GIT_TREE_NOT_FOUND_EXCEPTION
                    or GitlabConstants.GIT_PATH_NOT_FOUND_EXCEPTION):
                raise InvalidBranchORBaseDirException
            raise InvalidRepoUrlException
        except InvalidBranchORBaseDirException as e:
            raise e
        except Exception as e:
            raise e

    @log_decorator
    def get_latest_commit(self, project_id):
        """
        Get the latest commit id from the repo.

        Args:
            project_id
        Return:
            latest commit id
        """
        # Get the repo for project_id given in input
        all_commits, project_found, message = self.get_commits(self.configuration["repo_url"], self.configuration["branch"])
        latest_commit = []
        if all_commits:
            sorted_commits = sorted(all_commits, key=lambda i: i['commit_date'], reverse=True)
            latest_commit = sorted_commits[0]
        return latest_commit, project_found, message

    @log_decorator
    def rename_all_repos(self):
        """
        Fetches a list of repos and rename those with project ID

        Args:
        """
        repos = []
        project_list = self.client.projects.list(all=True, owned=True)
        for project in project_list:
            repos.append({"id": project.id, "existing_name": project.name})
            try:
                UUID(project.name, version=4)
                repos[len(repos) - 1]["status"] = "skipped"
            except ValueError:
                start_index = str(project.name).find("-")
                if start_index > 0:
                    project_name = str(project.name)[start_index + 1:len(str(project.name))]
                    projects = project
                    projects.name = project_name
                    projects.save()
                    repos[len(repos) - 1]["status"] = "renamed"
                    repos[len(repos) - 1]["new_name"] = project_name
                else:
                    repos[len(repos) - 1]["status"] = "skipped"
        return repos

    @log_decorator
    def get_commits(self, repo_name, branch_name=None, page_no="1", per_page="20"):
        """
        Get the commit id's for given the project_id.

        Header X-Project-Id:
            project_id
        Return:
            list of  commit id's
        """
        # gl = Gitlab(self.configuration["GIT_URL"], private_token=self.configuration["GIT_TOKEN"])

        # Get the repo for project_id given in input
        # repo_name = '{}/{}'.format(self.configuration['GIT_NAMESPACE'], project_id)
        repo_name = self.get_repo_name(repo_name)
        try:
            if branch_name is None:
                branch_name = "master"
            repo_id = self.get_repo(repo_name)
            project_found = True
            if page_no == "all":
                commits_obj = repo_id.commits.list(all=True, ref_name=branch_name)
            else:
                page_no = 0 if page_no is None else page_no
                per_page = 20 if per_page is None else per_page
                commits_obj = repo_id.commits.list(page=page_no, per_page=per_page, ref_name=branch_name)
            commits = []
            for commit in commits_obj:
                commit_info = {
                    'commit_id': commit.get_id(),
                    'commit_date': commit.committed_date,
                    'commit_message': commit.message,
                    # a merge commit has more than 1 parent commit
                    'is_merge_commit': len(commit.attributes["parent_ids"]) > 1
                }
                commits.append(commit_info)
            message = "Project Found"
            return commits, project_found, message
        except gitlab.exceptions.GitlabGetError as e:
            message = "Project Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def get_files(self, repo_name, commit_id):
        """
        Get the filenames that are changed for given the commit_id & project id.

        input:
            commit_id , project id
        Return:
            list of file name changed for given commit id
        """
        # gl = Gitlab(self.configuration["GIT_URL"], private_token=self.configuration["GIT_TOKEN"])
        # Get the repo for project_id given in input
        # repo_name = '{}/{}'.format(self.configuration['GIT_NAMESPACE'], project_id)
        repo_name = self.get_repo_name(repo_name)
        try:
            repo_id = self.get_repo(repo_name)
            project_found = True
            message = "Changed File Found"
            # Get Diff for specified commit id
            commit_diff_obj = repo_id.commits.get(commit_id).diff()
            files_changed = set()
            for each_diff in commit_diff_obj:
                files_changed.add(each_diff.get('old_path'))
                files_changed.add(each_diff.get('new_path'))
            files = list(files_changed)
            return files, project_found, message
        except gitlab.exceptions.GitlabGetError as e:
            message = "Changed File Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def validate_repo_access(self):
        try:
            self.client.auth()
            # if self.client.user.username != self.configuration["username"]:
            #     raise RepoAuthentiactionException
            git_url = self.configuration["repo_url"]
            repo_name = self.get_repo_name(git_url)
            repo = self.get_repo(repo_name)
            if repo.attributes["permissions"]["project_access"]:
                level = repo.attributes["permissions"]["project_access"]["access_level"]
            elif repo.attributes["permissions"]["group_access"]:
                level = repo.attributes["permissions"]["group_access"]["access_level"]
            else:
                raise RepoAccessException
            if (level == 30 and self.configuration["branch"] != "master") \
                    or level >= 40:
                return "Success"
            # elif level >= 40:
            #     return "Success"
            else:
                raise RepoAccessException
        except gitlab.exceptions.GitlabGetError as e:
            current_app.logger.exception(e)
            raise InvalidRepoUrlException
        except gitlab.exceptions.GitlabAuthenticationError as e:
            current_app.logger.exception(e)
            raise RepoAuthentiactionException
        except Exception as e:
            current_app.logger.exception(e)
            raise e

    @log_decorator
    def download_file(self, repo_name, file_path, branch="master"):
        """
        downloads file
        :param file_path:
        :param branch
        :return: file
        """
        try:
            repo_name = self.configuration["repo_url"]
            read_json = self.read_file(repo_name, file_path, branch)
            content = read_json["content"]
            content_decoded = base64.decodebytes(content.encode())
            return content_decoded
        except Exception as ex:
            current_app.logger.exception(ex)
            raise ex

    @log_decorator
    def download_folder(self, repo_name, file_path, branch="master"):
        """
        downloads file
        :param file_path
        :param repo_name
        :param branch
        :return:
        """
        try:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            folder_name = file_path.split('/')[-1]
            folderpath = dir_path + '/FilesDownloadZip/' + folder_name
            Path(folderpath).mkdir(parents=True, exist_ok=True)
            repo_name = self.configuration["repo_url"]
            self.downloading_folder_contents(repo_name, file_path, folderpath, branch)
            # initializing empty file paths list
            file_paths = []
            zip_folder_dir = dir_path + '/FilesDownloadZip'
            os.chdir(zip_folder_dir)

            # crawling through directory and subdirectories
            for root, directories, files in os.walk(f'./{folder_name}'):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    file_paths.append(filepath)

            # writing files to a zipfile
            with ZipFile(folder_name + '.zip', 'w') as zip:
                # writing each file one by one
                for file in file_paths:
                    zip.write(file)

            resp = open(folder_name + '.zip', 'rb')
            os.remove(folder_name + '.zip')
            shutil.rmtree(folder_name)
            return resp , folder_name + '.zip', zip_folder_dir
        except Exception as ex:
            current_app.logger.exception(ex)
            raise ex

    @log_decorator
    def downloading_folder_contents(self, repo_name, file_path, folderpath, branch="master"):
        """
        downloads folder content with structure
        :param repo_name:
        :param file_path:
        :param folderpath:
        :param branch:
        :return:
        """
        try:
            get_file_list = self.list_files(repo_name, file_path, branch)
            path = folderpath
            for file in get_file_list:
                if file['type'] == 'blob':
                    read_json = self.read_file(repo_name, file['path'], branch)
                    content = read_json["content"]
                    content_decoded = base64.decodebytes(content.encode())
                    with open(path + "/" + file['name'], "wb") as binary_file:
                        # Write bytes to file
                        binary_file.write(content_decoded)
                    binary_file.close()

            for file in get_file_list:
                if file['type'] == 'tree':
                    path = folderpath
                    path = path + '/' + file['name']
                    Path(path).mkdir(parents=True, exist_ok=True)
                    self.downloading_folder_contents(repo_name, file['path'], path, branch)

        except Exception as ex:
            current_app.logger.exception(ex)
            raise ex

    @log_decorator
    def default_set_up(self, application):
        self.configuration = application
        self.client = Gitlab(self.configuration["GIT_URL"], private_token=self.configuration["GIT_TOKEN"])
