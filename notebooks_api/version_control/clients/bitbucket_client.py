import os
import shutil
import datetime
import json
import tempfile
import base64
from urllib.parse import urlparse, quote
import requests
from notebooks_api.utils.web_utils import auth_call
from flask import current_app as app
from mosaic_utils.ai.logger.utils import log_decorator
from notebooks_api.utils.exceptions import (
    RepoAuthentiactionException,
    BrachOperationFailureException,
    InvalidBranchORBaseDirException,
    InvalidRepoUrlException,
    ApiAuthorizationException,
    VCSException,
    RepoAccessException
)
from zipfile import ZipFile
from pathlib import Path
import shutil
from .base import GitClient
from notebooks_api.utils.file_utils import encode_to_base64, git_clone, git_push_file
import logging

# log = logging.getLogger("mosic_version_control.bitbucket_client")

class BitBucketClient(GitClient):

    provider = 'bitbucket'

    def __init__(self, *args, **kwargs):
        """Initial session with user/password, and setup repository owner
        Args:
            params:
        Returns:
        """
        self.configuration = None
        super().__init__(*args, **kwargs)

    def set_up(self, application):
        self.init_configuration_(application)

    def default_set_up(self, application):
        self.init_configuration_(application)

    def init_configuration_(self, application):
        """
        Method initiates the configuration object
        """
        self.configuration = application
        bitbucket_api_auth_user = app.config.get("GIT_BITBUCKET_API_AUTH_USER", "")
        bitbucket_api_auth_pass = app.config.get("GIT_BITBUCKET_API_AUTH_PASS", "")
        self.configuration["GIT_BITBUCKET_API_AUTH_USER"] \
            = bitbucket_api_auth_user if bitbucket_api_auth_user \
            else self.configuration["username"]
        self.configuration["GIT_BITBUCKET_API_AUTH_PASS"] \
            = bitbucket_api_auth_pass if bitbucket_api_auth_pass \
            else self.configuration["password"]

    def set_up_test(self, application):
        self.configuration = application

    @log_decorator
    def get_repo_name(self, repo_url):
        repo_name = urlparse(repo_url).path.replace(".git", "").split("/")[-1]
        return repo_name

    @log_decorator
    def create_repo(self, repo_name):
        git_url = urlparse(self.configuration["repo_url"])
        hostname = f"{git_url.scheme}://{git_url.netloc}"
        project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
        part = "/rest/api/1.0/projects/{}/repos".format(project_name)
        url = hostname + part
        rest_call_create_repo = requests.post(url, auth=(self.configuration["username"],
                                                         self.configuration["password"]),
                                              json={"name": repo_name, "scmId": "git", "forkable": True})
        response = rest_call_create_repo.json()
        return {"url": response["links"]["self"][0]["href"]}

    @log_decorator
    def list_files(self, repo_name, path, branch="master", limit=1000000):
        """
        Read the files from the repository.
        Args:
            repo_name (str): name of the repository
            path (str): path of the file to be read
            branch (str): branch name of the repository
            limit (int): The total no of files to be returned
        Returns:
            File list
        """
        # Parsing Repo URL to get Scheme and Netloc
        git_url = urlparse(self.configuration["repo_url"])
        hostname = f"{git_url.scheme}://{git_url.netloc}"

        # Parsing Project name from Repo URL
        project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]

        # Parsing Repo name from Repo URL
        repo = self.get_repo_name(self.configuration["repo_url"])

        # Check if path starts with "/"
        if path.startswith("/"):
            path = path.replace("/", "", 1)

        # Forming the URL
        part = "/rest/api/1.0/projects/{}/repos/{}/files/{}?at={}&limit={}".format(project_name, repo, path, branch, limit)
        url = hostname + part

        rest_call_repo_list = requests.get(url, auth=(self.configuration["username"],
                                                      self.configuration["password"]))

        if rest_call_repo_list.status_code == 200:
            files_list = rest_call_repo_list.json()["values"]
            list_of_files = self.list_repo_creation(files_list, path)
            return list_of_files
        elif rest_call_repo_list.status_code == 401:
            raise RepoAuthentiactionException
        elif rest_call_repo_list.status_code == 404:
            raise InvalidRepoUrlException
        elif rest_call_repo_list.status_code == 500:
            raise InvalidBranchORBaseDirException
        app.logger.error(rest_call_repo_list.json())
        raise VCSException

    @log_decorator
    def list_repo_creation(self, list_files, path):
        list_of_files = []
        if len(path)!=0:
            path = path + '/'
        for i in list_files:
            component = {}
            duplicate = False
            f = i.split('/')
            if len(f) > 1:
                ind = i.index("/")
                name = i[0:ind]
                for val in list_of_files:
                    if val['name'] == name:
                        duplicate = True
                if not duplicate:
                    component["name"] = name
                    component["type"] = 'tree'
                    component["path"] = path + name
                    list_of_files.append(component)
            else:
                component["name"] = i
                component["type"] = 'blob'
                component["path"] = path + i
                list_of_files.append(component)
        return list_of_files

    @log_decorator
    def rename_repo(self, project_name, new_project_name, project_id):
        pass

    @classmethod
    def _check_status_code(cls, response, repo_id=None):
        """Checks the response status code and raises the exceptions"""
        status_code = response.status_code
        if status_code == 401:
            raise RepoAuthentiactionException
        if status_code == 404 or status_code ==403:
            raise InvalidRepoUrlException
        elif status_code == 409 or status_code == 400:
            errors = response.json().get("errors", [])
            error_message = errors[0]["message"] if len(errors) > 0 \
                else "Something went wrong, please contact admin"
            error_message = error_message.replace("'" + repo_id + "'", "")
            raise BrachOperationFailureException(error_message)


    @log_decorator
    def create_branch(self, repo_name, branch_name, start_point='master'):
        try:
            git_url = urlparse(self.configuration["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
            repo_id = self.get_repo_name(self.configuration["repo_url"])
            part_get_branch = "/rest/api/1.0/projects/{}/repos/{}/branches?filterText={}".format(project_name, repo_id, start_point)
            url_get = hostname + part_get_branch
            response_get = requests.get(url_get, auth=(self.configuration["username"],
                                                       self.configuration["password"]))
            part_post_branch = "/rest/api/1.0/projects/{}/repos/{}/branches".format(project_name, repo_id)
            url = hostname + part_post_branch
            response_post = requests.post(url, auth=(self.configuration["username"],
                                                     self.configuration["password"]),
                                          json={"name": branch_name, "startPoint": response_get.json()['values'][0]['latestCommit']})
            self._check_status_code(response_post, repo_id=repo_id)
        except RepoAuthentiactionException as ex:
            raise ex
        except BrachOperationFailureException as ex:
            raise ex
        except Exception as ex:
            return ex.args[0], 500


    @log_decorator
    def delete_branch(self, repo_name, branch_name):
        pass

    @log_decorator
    def fetch_branches(self, repo_name, proxy_details=None):
        try:
            git_url = urlparse(self.configuration["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
            repo_name = self.get_repo_name(self.configuration["repo_url"])
            part_get_branch = "/rest/api/1.0/projects/{}/repos/{}/branches".format(project_name, repo_name)
            url_get = hostname + part_get_branch
            response_get = requests.get(url_get, auth=(self.configuration["username"],
                                                       self.configuration["password"]))
            self._check_status_code(response_get)
            branches = []
            for branch in response_get.json()['values']:
                branches.append({
                    'name': branch['displayId'],
                    'sha': branch['latestCommit'],
                })
            return branches
        except RepoAuthentiactionException as ex:
            app.logger.error(ex)
            raise ex
        except InvalidRepoUrlException as ex:
            app.logger.error(ex)
            raise ex
        except Exception as ex:
            app.logger.error(ex)
            raise VCSException

    @log_decorator
    def create_file(self, repo_name, file_path, file_content, branch_name='master', message='file created'):
        pass

    @log_decorator
    def read_file(self, repo_name, file_path, branch_name='master', raw_content=False, commit_type=False):
        try:
            git_url = urlparse(self.configuration["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
            repo_id = self.get_repo_name(self.configuration["repo_url"])

            part = "/projects/{}/repos/{}/browse/{}".format(
                project_name, repo_id, quote(file_path))
            url = hostname + part + "?&at={}&raw".format(branch_name)
            response = requests.get(url, auth=(self.configuration["username"],
                                               self.configuration["password"]))
            if response.status_code == 401:
                raise RepoAuthentiactionException

            if file_path.endswith(".ipynb"):
                file_content = json.dumps(response.json())
            elif file_path.lower().endswith(('.png', '.jpeg', '.jpg', '.bmp', '.gif',
                                             '.xlsx', '.docx')):
                file_content = str(base64.b64encode(response.content)).split("b'")[1].rstrip("'")
                return {
                    'url': '',
                    'sha': branch_name,
                    'content': file_content,
                    'encoding': None,
                }
            else:
                file_content = response.text

            if raw_content and not file_path.endswith(('.png', '.jpeg', '.jpg', '.bmp', '.gif',
                                                       '.xlsx', '.docx')):
                return {
                    'url': '',
                    'sha': branch_name,
                    'content': file_content,
                    'encoding': "base64",
                }

            content = str(encode_to_base64(file_content)).split("b'")[1]
            return {
                'url': '',
                'sha': branch_name,
                'content': content,
                'encoding': "base64",
            }
        except RepoAuthentiactionException as ex:
            raise ex
        except Exception as ex:
            return ex.args[0], 500

    @log_decorator
    def update_file(self, file_path, file_content, enabled_repo, message='file updated'):
        temp_file_dir = tempfile.mkdtemp()
        if "/" not in file_path:
            file_path = "/" + file_path
        filepath, filename = file_path.rsplit('/', 1)
        try:
            git_temp_dir = tempfile.mkdtemp()
            remote_url = enabled_repo['url']
            branch_name = enabled_repo.get("branch", "master")

            git_clone(git_temp_dir, remote_url, branch_name)
            tmp_file_path = os.path.join(temp_file_dir, filepath)
            if not os.path.exists(tmp_file_path):
                os.makedirs(tmp_file_path)
            with open('{}/{}'.format(tmp_file_path, filename), 'w') as file2write:
                if isinstance(file_content, str):
                    file2write.write(file_content)
                else:
                    json.dump(file_content, file2write)
            file2write.close()
            folder_list = os.listdir(os.path.join(temp_file_dir, filepath))
            for i in folder_list:
                if os.path.isdir(os.path.join(temp_file_dir, filepath, i)):
                    if os.path.exists(os.path.join(git_temp_dir, filepath, filename)):
                        os.unlink(os.path.join(git_temp_dir, filepath, filename))
                    else:
                        os.makedirs(os.path.join(git_temp_dir, filepath))
                    shutil.copy(os.path.join(temp_file_dir, filepath, filename), os.path.join(git_temp_dir, filepath, filename ))
                else:
                    if os.path.exists(os.path.join(git_temp_dir, filepath, i)):
                        os.unlink(os.path.join(git_temp_dir, filepath, i))
                    shutil.copy(os.path.join(temp_file_dir, filepath, filename),
                                os.path.join(git_temp_dir, filepath, i))

            response = git_push_file(git_temp_dir, branch_name, message)
            if response != '':
                self.when_response_is_blank(git_temp_dir, temp_file_dir)
            return {
            'sha': '',
            'url': '',
            }
        except Exception as ex:
            raise ex

    @log_decorator
    def delete_file(self, repo_name, file_path, branch_name='master', message='file deleted'):
        pass

    @log_decorator
    def list_files_with_content(self, repo_name, file_path):
        pass

    @log_decorator
    def get_latest_commit(self, project_id):
        """
                Get the latest commit id from the repo.

                Args:
                    project_id
                Return:
                    latest commit id
                """
        all_commits, project_found, message = self.get_commits(self.configuration["repo_url"], self.configuration["branch"])
        latest_commit = []
        if all_commits:
            sorted_commits = sorted(all_commits, key=lambda i: i['commit_date'], reverse=True)
            latest_commit = sorted_commits[0]
        return latest_commit, project_found, message

    @log_decorator
    def rename_all_repos(self):
        pass

    @log_decorator
    def fetch_start_page_number(self, page_no, per_page):
        if int(page_no) == 1:
            return 0
        return (int(page_no) - 1) * int(per_page) + 1

    @log_decorator
    def get_commits(self, repo_name, branch_name=None, page_no="1", per_page="20"):
        """
        Get the commit id's for given the project_id.

        Header X-Project-Id:
            project_id
        Return:
            list of  commit id's
        """
        try:
            if branch_name is None:
                branch_name = "master"
            git_url = urlparse(self.configuration["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
            repo_id = self.get_repo_name(self.configuration["repo_url"])

            if page_no != "all":
                page_no = 1 if page_no is None else page_no
                per_page = 20 if per_page is None else per_page
                start_page_no = self.fetch_start_page_number(page_no, per_page)
                part = "/rest/api/1.0/projects/{}/repos/{}/commits?until={}&start={}&limit={}".format(project_name, repo_id, branch_name, start_page_no, per_page)
            else:
                part = "/rest/api/1.0/projects/{}/repos/{}/commits?until={}".format(project_name, repo_id, branch_name)
            project_found = True
            url = hostname + part
            print(url)
            #url = self.configuration["GIT_URL"] + part
            commits_obj = requests.get(url, auth=(self.configuration["username"],
                                                  self.configuration["password"]))
            commits = []
            for commit in commits_obj.json()["values"]:
                commit_info = {
                    'commit_id': commit["id"],
                    'commit_date': datetime.datetime.utcfromtimestamp(commit["authorTimestamp"]/1000).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    'commit_message': commit["message"],
                    'is_merge_commit': len(commit["parents"]) > 1
                               }
                commits.append(commit_info)
            message = "Project Found"
            return commits, project_found, message
        except Exception as e:
            message = "Project Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def get_files(self, repo_url, commit_id):
        """
        Get the filenames that are changed for given the commit_id & project id.

        input:
            commit_id , project id
        Return:
            list of file name changed for given commit id
        """
        try:
            git_url = urlparse(self.configuration["repo_url"])
            hostname = f"{git_url.scheme}://{git_url.netloc}"
            project_name = urlparse(self.configuration["repo_url"]).path.replace(".git", "").split("/")[2]
            repo_id = self.get_repo_name(self.configuration["repo_url"])

            part = "/rest/api/1.0/projects/{}/repos/{}/commits/{}/changes".format(project_name, repo_id, commit_id)
            project_found = True

            url = hostname + part

            commits_obj = requests.get(url, auth=(self.configuration["username"],
                                                  self.configuration["password"]))

            # Get Diff for specified commit id
            diff_list = commits_obj.json()["values"]
            list_of_changed_files = []
            for diff in diff_list:
                list_of_changed_files.append(diff['path']['toString'])
            message = "Changed File Found"
            return list_of_changed_files, project_found, message
        except Exception as e:
            message = "Changed File Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def when_response_is_blank(self, git_temp_dir, temp_dir):
        """Method with operations to perform when response is blank"""
        if os.path.isdir(git_temp_dir):
            shutil.rmtree(git_temp_dir)
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir)

    @log_decorator
    def validate_group_access(self, project_name, repo_name, hostname, username):
        """
        Method checks if user is having an access to a group,
        which has access to given repo
        """
        part = f"/rest/api/1.0/projects/{project_name}/repos/{repo_name}/permissions/groups"
        group_response = requests.get(url=hostname + part,
                                      auth=(self.configuration["GIT_BITBUCKET_API_AUTH_USER"],
                                            self.configuration["GIT_BITBUCKET_API_AUTH_PASS"]))
        if group_response.status_code == 200 and group_response.json()["values"]:
            for group_value in group_response.json()["values"]:
                permission = group_value["permission"]
                if permission in ["REPO_WRITE", "REPO_ADMIN"]:
                    group_name = group_value["group"]["name"]
                    part = f"/rest/api/1.0/admin/groups/more-members?context={group_name}&filter={username}"
                    users_response = auth_call(hostname + part, username=self.configuration["username"],
                                               pwd=self.configuration["password"])
                    if users_response.status_code == 200 and users_response.json()["values"]:
                        return "Success"
        raise RepoAccessException

    @log_decorator
    def validate_repo_access(self):
        git_url = urlparse(self.configuration["repo_url"])
        hostname = f"{git_url.scheme}://{git_url.netloc}"
        project_name = urlparse(self.configuration["repo_url"]).path.replace(".git","").split("/")[2]
        repo_name = urlparse(self.configuration["repo_url"]).path.replace(".git","").split("/")[3]
        username = self.configuration["username"]

        #VALIDATE USER CREDS
        get_users_url = hostname + f"/rest/api/1.0/users?filter={username}"
        users_api_res = requests.get(get_users_url, auth=(username,self.configuration["password"]))
        if users_api_res.status_code == 401:
            app.logger.error(users_api_res.text)
            raise RepoAuthentiactionException

        part = f"/rest/api/1.0/projects/{project_name}/repos/{repo_name}/permissions/users?filter={username}"
        url = hostname + part
        permission_response = requests.get(url, auth=(self.configuration["GIT_BITBUCKET_API_AUTH_USER"],
                                                      self.configuration["GIT_BITBUCKET_API_AUTH_PASS"]))
        if permission_response.status_code == 200:
            if permission_response.json()["values"]:
                permission = permission_response.json()["values"][0]["permission"]
                if permission in ["REPO_WRITE", "REPO_ADMIN"]:
                    return "Success"
        elif permission_response.status_code == 401:
            if "AuthorisationException" in str(permission_response.json()):
                app.logger.error(permission_response.text)
                raise ApiAuthorizationException
            raise RepoAuthentiactionException
        elif permission_response.status_code == 404:
            raise InvalidRepoUrlException
        status = self.validate_group_access(project_name, repo_name, hostname, username)
        return status


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
            app.logger.error(ex)
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
            app.logger.error(ex)
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
            app.logger.error(ex)
            raise ex
