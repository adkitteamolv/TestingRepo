# -*- coding: utf-8 -*-

"""GitClient implementation for GitHub."""
import os
import sys
from .base import GitClient
from flask import current_app
from urllib.parse import urlparse
import urllib

import json
import base64
from notebooks_api.utils.file_utils import decode_base64_to_string, encode_to_base64
from notebooks_api.utils.exceptions import (RepoAuthentiactionException,
                                VCSException, InvalidRepoUrlException,
                                RepoAccessException, InvalidBranchORBaseDirException)
from uuid import UUID
from mosaic_utils.ai.logger.utils import log_decorator
import logging
from .base import GitClient
import requests
import json
from zipfile import ZipFile
from pathlib import Path
import shutil

# pylint: disable=invalid-name
# log = logging.getLogger("mosic_version_control.github_client")

class GitHubClient(GitClient):
    """Git client implementation for github."""

    provider = 'github'

    def __init__(self, *args, **kwargs):
        """
        Initialize the github client
        """
        self.configuration = None
        self.github_api_url = None
        super().__init__(*args, **kwargs)

    @log_decorator
    def set_up(self, application):
        if "github.com" in urlparse(application["repo_url"]).netloc.lower():
            self.github_api_url = 'https://api.github.com'
            self.configuration = application
        else:
            git_url = urlparse(application["repo_url"])
            hostname = urllib.parse.urljoin(f"{git_url.scheme}://", git_url.netloc)
            self.configuration = application

    @log_decorator
    def get_repo_name(self, repo_url):
        if 'git' in repo_url:
            repo_name = urlparse(repo_url).path.replace(".git", "")[1:]
        else:
            repo_name = repo_url
        return repo_name

    @log_decorator
    def get_namespace(self, name):
        """
        Correct the repo name by prefixing namespace.

        Args:
            name: branch name or repo name to be namespaced
        """

        return urlparse(name).path.replace(".git", "")[1:]

    @staticmethod
    def get_reference(branch_name):
        """
        Prepare reference.

        Args:
            branch_name (str): Name of the branch
        """
        return 'refs/heads/{}'.format(branch_name)

    @log_decorator
    def get_github_headers(self):
        """
        :return: Header
        """
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': 'token ' + self.configuration["password"]
        }
        return headers

    @log_decorator
    def create_repo(self, repo_name):
        """
        Create a new repository.

        Args:
            repo_name (str): name of the repository
        Returns:
            dictionary
        """
        try:
            headers = self.get_github_headers()
            create_repo_resp = requests.post(self.github_api_url + '/user/repos', headers=headers,
                                             data=json.dumps({"name": repo_name}))
            create_repo_resp_json = create_repo_resp.json()
            self.check_statuscode(create_repo_resp)
            self.create_file(repo_name, '/README.md', 'Read me', message='initial commit')
            return {'url': create_repo_resp_json['clone_url']}
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    @log_decorator
    def rename_repo(self, project_name, new_project_name, project_id):
        """
        Rename repository.
        """
        # url_rename = self.github_api_url+"/repos/{0}/{1}".format(
        #     self.configuration["username"], project_name)
        # print(url_rename)
        # rename_data = {"name": new_project_name}
        # resp = requests.patch(url_rename, headers=self.headers(), data=json.dumps(rename_data))
        # print(resp)
        pass

    @log_decorator
    def create_branch(self, repo_name, branch_name, start_point='master'):
        """
        Create a new branch in the specified repository.

        Args:
            repo_name (str): name of the repository
            branch_name (str): name of the branch
            start_point (str): starting point for the new branch
        """
        try:
            repo_url = self.get_repo_name(self.configuration["repo_url"])
            headers = self.get_github_headers()
            get_branch_url = self.github_api_url + "/repos/{repo_url}/git/refs/heads".format(repo_url=repo_url)
            branches_resp = requests.get(get_branch_url, headers=headers)
            branches = branches_resp.json()
            self.check_statuscode(branches_resp)
            ref = self.get_reference(branch_name)
            sha = branches[-1]['object']['sha']
            create_branch_url = self.github_api_url + "/repos/{repo_url}/git/refs".format(repo_url=repo_url)
            res = requests.post(create_branch_url,
                                json={"ref": ref, "sha": sha},
                                headers=headers)
            self.check_statuscode(res)
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    def check_statuscode(self, response):
        """
        Checks if the response is successful or not
        :param response: request response object
        :return: exception, if the response is not successful
        """
        if not str(response.status_code).startswith('2'):
            message = response.json()['message']
            current_app.logger.error(message)
            if response.status_code == 401:
                raise RepoAuthentiactionException
            elif response.status_code == 404:
                if "not a user" in message:
                    raise RepoAuthentiactionException
                raise InvalidRepoUrlException
            else:
                current_app.logger.error(message)
                raise Exception(message)

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
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            branches = []
            if not self.github_api_url:
                raise InvalidRepoUrlException
            get_branch_url = self.github_api_url + '/repos/{repo}/branches'.format(repo=repo_name)
            headers = self.get_github_headers()
            branches_resp = requests.get(get_branch_url, headers=headers)
            branches_resp_json = branches_resp.json()
            self.check_statuscode(branches_resp)
            for branch in branches_resp_json:
                branches.append({
                    'name': branch['name'],
                    'sha': branch['commit']['sha'],
                })
            return branches
        except InvalidRepoUrlException as ex:
            current_app.logger.error(ex)
            raise ex
        except RepoAuthentiactionException as ex:
            current_app.logger.error(ex)
            raise ex
        except Exception as ex:
            current_app.logger.error(ex)
            raise VCSException

    @log_decorator
    def delete_branch(self, repo_name, branch_name):
        """
        Delete the branch.

        Args:
            repo_name (str): name of the repo
            branch_name (str): name of the branch
        """
        try:
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            # repo = self.create_repo(repo_name)
            reference = self.get_reference(branch_name)
            delete_api = self.github_api_url + '/repos/{repo_name}/git/refs/heads/{branch_name}'.format(
                repo_name=repo_name, branch_name=branch_name
            )
            headers = self.get_github_headers()
            delete_api_resp = requests.delete(delete_api, headers=headers)
            self.check_statuscode(delete_api_resp)
        except Exception as ex:
            current_app.logger.error(ex)
            raise ex

    # pylint: disable=line-too-long,too-many-arguments
    @log_decorator
    def create_file(self, repo_name, file_path, file_content,
                    branch_name='master', message='created file'):
        """
        Add a new file to the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file
            file_content (str): file content
            message (str): commit message to be used
            branch_name(str): branch name
        """
        try:
            headers = self.get_github_headers()
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            file_name = file_path.split('/')[-1]
            create_file_url = self.github_api_url + "/repos/{repo_name}/contents/{path}".format(
                repo_name=repo_name, path=file_name)
            file_content_base64_bytes = encode_to_base64(file_content)
            file_content_base64_string = file_content_base64_bytes.decode('utf-8')
            file_resp = requests.put(create_file_url, headers=headers,
                                     data=json.dumps({"message": message,
                                                      "content": file_content_base64_string,
                                                      "branch": branch_name}))
            file = file_resp.json()
            self.check_statuscode(file_resp)
            return {
                'sha': file['commit']['sha'],
                'url': file['content']['download_url']
            }
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    @log_decorator
    def read_file(self, repo_name, file_path, branch_name='master', raw_content=False, commit_type=False):
        """
        Read file from the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read
            branch_name (str): branch to be checked
            raw_content (bool)
        Returns:
            dictionary
        """
        try:
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            file_path = '/{}'.format(file_path)
            file = self.get_file_content(repo_name, file_path, branch_name)
            _, file_extension = os.path.splitext(file_path)
            content = file['content']
            if raw_content:
                if file_extension.lower() == '.ipynb':
                    content = json.loads(decode_base64_to_string(content))
                else:
                    content = decode_base64_to_string(content)

            return {
                'url': file['download_url'],
                'sha': file['sha'],
                'content': content,
                'encoding': file['encoding'],
            }
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    @log_decorator
    def get_file_content(self, repo_name, file_path, branch_name='master'):
        """
        to get content from the filepath
        :param repo_name:
        :param file_path:
        :param branch_name:
        :return: filecontent
        """
        try:
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            headers = self.get_github_headers()
            file_path_url = urllib.parse.quote(file_path)
            file_content_api_url = self.github_api_url + '/repos/{repo_name}/contents/{path}?ref={branchname}'.format(
                repo_name=repo_name, path=file_path_url, branchname=branch_name)
            file_status = requests.get(file_content_api_url, headers=headers)

            if file_status.status_code != 403:
                self.check_statuscode(file_status)
                file_content = file_status.json()
                return file_content
            else:
                file_name = file_path.rsplit('/')[-1]
                folder_path = file_path.rsplit('/', 1)[0]
                folder_path = folder_path.lstrip('/')
                folder_path = urlparse(folder_path).path
                url = self.github_api_url + '/repos/{repo_name}/git/trees/{branch}:{path}'.format(
                    repo_name=repo_name, branch=branch_name, path=folder_path
                )
                get_blob_resp = requests.get(url, headers=headers)
                self.check_statuscode(get_blob_resp)
                tree = get_blob_resp.json()['tree']
                for content_file in tree:
                    if content_file['path'] == file_name:
                        content_url = content_file['url']
                        file_content_status = requests.get(content_url, headers=headers)
                        file_content = file_content_status.json()
                        file_content['download_url'] = None
                        self.check_statuscode(file_content_status)
                        return file_content
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    # pylint: disable=line-too-long,too-many-arguments
    @log_decorator
    def update_file(self, file_path, file_content, enabled_repo, message='file updated'):
        """
        Update file from the repository.

        Args:
            file_path (str): path of the file to be read
            file_content (str): content of the file
            enabled_repo (dict): enabled repo details
            message(str): commit message
        """
        try:
            repo_name = enabled_repo["repo_url"]
            branch_name = enabled_repo.get("branch", "master")
            namespace = self.get_namespace(repo_name)
            file_path = '{}'.format(file_path)
            file_object = self.get_file_content(namespace, file_path, branch_name=branch_name)
            content = file_content
            if isinstance(file_content, dict):
                content = json.dumps(file_content)

            api_url = self.github_api_url + '/repos/{repo}/contents/{file_path}'.format(
                repo=namespace, file_path=file_path)
            headers = self.get_github_headers()
            content_encoded_bytes = encode_to_base64(content)
            content_encoded_string = content_encoded_bytes.decode('utf-8')
            file_obj_resp = requests.put(api_url, headers=headers,
                                         data=json.dumps({
                                             "message": message, "content": content_encoded_string,
                                             "sha": file_object['sha'], "branch": branch_name,
                                             "path": file_path}))
            file = file_obj_resp.json()
            self.check_statuscode(file_obj_resp)
            return {
                'sha': file['commit']['sha'],
                'url': file['content']['download_url'],
            }
        except Exception as ex:
            current_app.logger.error(ex)
            raise Exception(ex.args[0])

    @log_decorator
    def delete_file(self, repo_name, file_path,
                    branch_name='master', message='removed file'):
        """
        Delete file from the repository.

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read
            branch_name (str): branch to be checked
            message(str): commit message
        """
        try:
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            file_object = self.get_file_content(repo_name, file_path, branch_name=branch_name)
            # file_path = '{}'.format(file_path)
            headers = self.get_github_headers()
            if isinstance(file_object, list):
                for elem in file_object:
                    delete_api_url = self.github_api_url + '/repos/{repo}/contents/{file_path}'.format(
                        repo=repo_name, file_path=elem['path'])
                    status = requests.delete(delete_api_url, headers=headers,
                                             data=json.dumps({"message": message, "sha": elem['sha'],
                                                              "branch": branch_name}))
            else:
                delete_api_url = self.github_api_url + '/repos/{repo}/contents/{file_path}'.format(
                    repo=repo_name, file_path=file_object['path'])
                status = requests.delete(delete_api_url, headers=headers,
                                         data=json.dumps({"message": message, "sha": file_object['sha'],
                                                          "branch": branch_name}))
            self.check_statuscode(status)
        except RepoAuthentiactionException as re:
            current_app.logger.error("Git hub bad credential error: %s", re)
            raise re
        except Exception as ex:
            current_app.logger.error(ex)
            raise ex

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
            List of dictionary
        """
        if file_path in [None, ""]:
            file_path = ''
        files = []
        try:
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            headers = self.get_github_headers()
            fetch_tree_api = self.github_api_url + "/repos/{repo_name}/commits?sha={branch_name}".format(
                repo_name=repo_name, branch_name=branch)
            current_app.logger.info(fetch_tree_api)
            latest_commit_resp = requests.get(fetch_tree_api, headers=headers,
                                              data=json.dumps({"sha": branch}))
            self.check_statuscode(latest_commit_resp)
            latest_commit = latest_commit_resp.json()
            latest_commit_sha = latest_commit[0]['sha']
            current_app.logger.info(file_path)
            file_list_url = self.github_api_url + "/repos/{repo_name}/contents/{path}?ref={latest_commit_sha}".format(
                repo_name=repo_name, path=file_path, latest_commit_sha=latest_commit_sha)
            current_app.logger.info(file_list_url)
            file_list_resp = requests.get(file_list_url, headers=headers)
            self.check_statuscode(file_list_resp)
            file_list = file_list_resp.json()
            current_app.logger.info(file_list)
            for content_file in file_list:
                type_of_file = 'tree'
                name = content_file['path'].split('/')[-1]
                if '.' in name or content_file['type']=='file':
                    type_of_file = 'blob'
                files.append({
                    'id': None,
                    'mode': None,
                    'name': name,
                    'path': content_file['path'],
                    'type': type_of_file
                })
            return files
        except InvalidRepoUrlException as e:
            current_app.logger.error(e)
            repo_url = self.github_api_url+"/repos/{repo_name}".format(repo_name=repo_name)
            repo_res = requests.get(repo_url, headers=headers)
            if repo_res.status_code==404:
                raise InvalidRepoUrlException
            raise InvalidBranchORBaseDirException
        except Exception as e:
            current_app.logger.error(e)
            raise e

    @log_decorator
    def list_files_with_content(self, repo_name, file_path):
        """
        Read files from the repository. Lists down only the files in a repo with their content

        Args:
            repo_name (str): name of the repository
            file_path (str): path of the file to be read

        Returns:
            List of dictionary
        """
        repo_name = self.get_repo_name(self.configuration["repo_url"])
        if file_path is None:
            file_path = ''
        branch_name = self.configuration['branch']
        repo_url = self.github_api_url + '/repos/{repo}/contents{path}?ref={branch_name}'.format(repo=repo_name,
                                                                                                 path=file_path,
                                                                                                 branch_name=branch_name)
        headers = self.get_github_headers()
        repo_api_resp = requests.get(repo_url, headers=headers)
        tree = repo_api_resp.json()
        files = []
        try:
            for content_file in tree:
                name = content_file['path'].split('/')[-1]
                if '.' in name:
                    file_content_url = content_file['url']
                    file_content_status = requests.get(file_content_url, headers=headers)
                    file_content = file_content_status.json()
                    self.check_statuscode(file_content_status)
                    files.append({
                        'id': None,
                        'mode': None,
                        'name': name,
                        'path': content_file['path'],
                        'type': content_file['type'],
                        'content': file_content['content']
                    })
        except Exception as e:
            current_app.logger.error(e)
        return files

    @log_decorator
    def get_latest_commit(self, project_id):
        """
        Get the latest commit id from the repo.

        Args:
            project_id
        Return:
            latest commit id
        """
        all_commits, project_found, message = self.get_commits(self.configuration["repo_url"],
                                                               self.configuration["branch"])
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
        pass

    @log_decorator
    def get_commits(self, repo_name, branch_name=None, page_no="1", per_page="20"):
        """
        Get the commit id's for given the project_id.

        Header X-Project-Id:
            project_id
        Return:
            list of  commit id's
        """
        # gh = Github(self.configuration["GIT_TOKEN"])

        repo_name = self.get_repo_name(self.configuration['repo_url'])
        try:
            project_found = True
            if branch_name is None:
                branch_name = "master"
            headers = self.get_github_headers()
            commits_url = self.github_api_url + '/repos/{repo_name}/commits?sha={branchname}'.format(
                repo_name=repo_name, branchname=branch_name)
            print(commits_url)
            if page_no != "all":
                page_no = 0 if page_no is None else page_no
                per_page = 20 if per_page is None else per_page
                self.configuration.update({"per_page": int(per_page)})
                self.set_up(self.configuration)
                commits_resp_status = requests.get(commits_url, headers=headers,
                                                   data=json.dumps({"sha": branch_name, "per_page": per_page}))
            else:
                commits_resp_status = requests.get(commits_url, headers=self.get_headers(),
                                                   data=json.dumps({"sha": branch_name}))
            self.check_statuscode(commits_resp_status)
            commits_json = commits_resp_status.json()
            commits = []
            for commit in commits_json:
                commit_info = {
                    'commit_id': commit['sha'],
                    'commit_date': commit['commit']['author']['date'],
                    'commit_message': commit['commit']['message'],
                    # a merge commit has more than 1 parent commit
                    'is_merge_commit': len(commit["parents"]) > 1
                }
                commits.append(commit_info)
            message = "Project Found"
            return commits, project_found, message
        except RepoAuthentiactionException as re:
            current_app.logger.error("Git hub bad credential error - %s", re)
            message = "Project Not Found"
            project_found = False
            return [], project_found, message
        except Exception as ex:
            current_app.logger.error(ex)
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
        try:
            repo_name = self.get_repo_name(self.configuration['repo_url'])
            project_found = True
            message = "Changed File Found"
            # Get Diff for specified commit id
            commit_url = self.github_api_url + '/repos/{repo}/commits/{commit_id}'.format(repo=repo_name,
                                                                                          commit_id=commit_id)
            headers = self.get_github_headers()
            commit_resp_status = requests.get(commit_url, headers=headers)
            self.check_statuscode(commit_resp_status)
            commit_json = commit_resp_status.json()
            files_changed = set()
            for file in commit_json['files']:
                files_changed.add(file['filename'])
            files = list(files_changed)
            return files, project_found, message
        except Exception as ex:
            current_app.logger.error(ex)
            message = "Changed File Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def validate_repo_access(self):
        try:
            repo_name = self.get_repo_name(self.configuration['repo_url'])
            validate_url = self.github_api_url + '/repos/{repo_name}/collaborators/{username}/permission'.format(
                repo_name=repo_name, username=self.configuration['username']
            )
            headers = self.get_github_headers()
            permission_status = requests.get(validate_url, headers=headers)
            permission_json = permission_status.json()
            self.check_statuscode(permission_status)
            if permission_json['permission'] == 'admin' or permission_json['permission'] == 'write':
                return "Success"
            raise RepoAccessException
        except RepoAuthentiactionException as re:
            current_app.logger.error("Git hub bad credential error - %s", re)
            raise RepoAuthentiactionException
        except Exception as ex:
            current_app.logger.error(ex)
            raise ex

    @log_decorator
    def delete_repo(self, repo_name):
        """
        deletes the repo (for create_repo test case to delete repo if already exists)
        :param repo_name:
        :return:
        """
        try:
            headers = self.get_github_headers()
            repo_name = self.get_repo_name(self.configuration['repo_url'])
            delete_repo_url = self.github_api_url + '/repos/{name}'.format(name=repo_name)
            delete_repo_resp = requests.delete(delete_repo_url, headers=headers)
            return delete_repo_resp.status_code
        except Exception as ex:
            current_app.logger.error(ex)
            raise ex

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
            current_app.logger.error(ex)
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
            return resp, folder_name + '.zip', zip_folder_dir
        except Exception as ex:
            current_app.logger.error(ex)
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
            current_app.logger.error(ex)
            raise ex

    @log_decorator
    def default_set_up(self, application):
        self.configuration = application
        # self.client = Github(base_url=self.configuration["GIT_URL"], login_or_token=self.configuration["GIT_TOKEN"])
