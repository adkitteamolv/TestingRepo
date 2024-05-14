import os
import shutil
import json
import tempfile
import base64
import logging

from urllib.parse import urlparse
from zipfile import ZipFile
from pathlib import Path
import requests
from flask import g, current_app as app
from mosaic_utils.ai.logger.utils import log_decorator
from .constants import AzureDevopsAPIUrls, GenericConstants, AzureDevops
from notebooks_api.utils.exceptions import (
    RepoAuthentiactionException,
    BrachOperationFailureException,
    InvalidBranchORBaseDirException,
    InvalidRepoUrlException,
    ApiAuthorizationException,
    VCSException,
    RepoAccessException,
    AzureDevopsOrgProjectException,
    AzureDevopsRepositoryExists
)

from .base import GitClient
from notebooks_api.utils.file_utils import encode_to_base64, git_clone, git_push_file
from notebooks_api.utils.git_operations import update_file_content

# log = logging.getLogger("mosic_version_control.azdevops_client")


class AzureDevopsClient(GitClient):
    """
    Class for Azure devops client associating different git methods
    which are subclassed from GitClient
    """
    provider = 'azuredevops'

    def __init__(self, *args, **kwargs):
        """Initial session with user/password, and setup repository owner
        Args:
            params:
        Returns:
        """
        self.configuration = None
        self.headers = {}
        self.organization = None
        super().__init__(*args, **kwargs)

    def generate_headers(self, usertoken):
        """
        This method encodes the personal access token to base64 format and
        sets it to the headers
        """
        encodedpat = base64.b64encode(usertoken.encode('utf-8')).decode('utf-8')
        self.headers['Authorization'] = 'Basic ' + encodedpat

    def set_up(self, application):
        """
        Initial method to set up the Azure devops client
        """
        self.init_configuration_(application)


    def add_proxy(self, proxy_details):
        """
        This method takes proxy details dictionary and extracts different
        keys and saves it in object
        """
        self.proxy_ip = proxy_details.get("IPaddress", None)
        self.verify_ssl = proxy_details.get('SSLVerify', True)
        self.proxy_type = proxy_details.get("Protocol", 'http')
        self.proxy_username = proxy_details.get('UsernameOrProxy', None)
        self.proxy_password = proxy_details.get('PasswordOrProxy', None)


    def default_set_up(self, application):
        """
        Method for default case set up
        """
        self.configuration = application
        userpat = ":" + app.config.get("GIT_TOKEN", "")
        self.generate_headers(userpat)
        self.project_name = app.config.get("PROJECT_KEY", "")
        self.configuration["repo_url"] = app.config.get("GIT_URL", "")
        self.organization = urlparse(
                self.configuration["repo_url"]).path.split("/")[1]
        self.default_object_id = GenericConstants.DEFAULT_OBJECT_ID
        self.git_url = urlparse(self.configuration["repo_url"])
        self.repo_name = self.git_url.path.split("/")[-1]
        proxy_details = self.configuration.get('proxy_details', {})
        if proxy_details:
            proxy_details = json.loads(proxy_details)
            proxy_details = proxy_details if type(proxy_details) == dict else json.loads(proxy_details)
            self.add_proxy(proxy_details)
        else:
            self.proxy_ip = None
            self.proxy_username = None
            self.proxy_password = None


    def init_configuration_(self, application):
        """
        Method initiates the configuration object
        """
        self.configuration = application
        userpat = ":" + self.configuration["password"]
        self.generate_headers(userpat)
        try:
            self.project_name = urlparse(
            self.configuration["repo_url"]).path.split("/")[2]
            organization = urlparse(
                application["repo_url"]).path.split("/")[1]
            self.organization = organization if organization \
                else urlparse(app.config.get("GIT_URL", "")).path.split("/")[1]
            self.git_url = urlparse(self.configuration["repo_url"])
            self.repo_name = self.git_url.path.split("/")[-1]
            proxy_details = self.configuration.get('proxy_details', {})
            if proxy_details:
                proxy_details = json.loads(proxy_details)
                proxy_details = proxy_details if type(proxy_details) == dict else json.loads(proxy_details)
                self.add_proxy(proxy_details)
            else:
                self.proxy_ip = None
                self.proxy_username = None
                self.proxy_password = None

        except IndexError:
            app.logger.error(f"Organization or project not found in repo_url {application['repo_url']}")
            raise AzureDevopsOrgProjectException
        except Exception as err:
            app.logger.error(err)
            raise VCSException


    @log_decorator
    def get_api_request_call(self, url):
        """
        This method takes url as an input and makes a http GET API request to 
        the URL based on the proxy details available in the object.
        If proxy details are available then it is added to the python requests.
        The method returns the response object
        """
        try:
            if self.proxy_ip and self.proxy_username and self.proxy_password:
                get_response = requests.get(url=url, 
                    headers=self.headers, 
                    auth=(self.proxy_username, self.proxy_password),
                    proxies = {self.proxy_type: self.proxy_ip},
                    verify = self.verify_ssl)    
            elif self.proxy_ip:
                get_response = requests.get(url=url, 
                    headers=self.headers, 
                    proxies = {self.proxy_type: self.proxy_ip},
                    verify = self.verify_ssl)
            else:
                get_response = requests.get(url=url, 
                                    headers=self.headers)
            app.logger.info(get_response)
            return get_response
        except Exception as err:
            app.logger.error(err)

    @log_decorator
    def post_api_request_call(self, url, request_data):
        """
        This method takes url as an input and makes a http POST API request to 
        the URL based on the proxy details available in the object.
        If proxy details are available then it is added to the python requests.
        The method returns the response object
        """
        try:
            if self.proxy_ip and self.proxy_username and self.proxy_password:
                response = requests.post(url, headers=self.headers,
                                        auth = (self.proxy_username, self.proxy_password),
                                        data=json.dumps(request_data),
                                        proxies = {self.proxy_type: self.proxy_ip},
                                        verify = self.verify_ssl)
            elif self.proxy_ip:
                response = requests.post(url, headers=self.headers,
                                        data=json.dumps(request_data),
                                        proxies = {self.proxy_type: self.proxy_ip},
                                        verify = self.verify_ssl)
            else:
                response = requests.post(url, headers=self.headers,
                                                data=json.dumps(request_data))
            app.logger.info(response)
            return response
        except Exception as err:
            app.logger.error(err)


    @log_decorator
    def fetch_project_details(self, hostname):
        """
        Fetches the Azure devops project id from project name
        Args: 
          hostname (str) : Url of the project
          project_name (str) : Name of the project
        """
        try:
            project_detail_url = AzureDevopsAPIUrls.PROJECT_DETAILS.format(
                hostname, self.organization, self.project_name)
            rest_call_get_project_details = self.get_api_request_call(project_detail_url)
            return rest_call_get_project_details.json()["id"]
        except Exception as projecterror:
            app.logger.error(projecterror)
            return None

    @log_decorator
    def create_repo(self, repo_name):
        """
        Creates new repository using the name passed in the request
        Args:
        repo_name (str): name of the repository
        """
        try:
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"
            az_project_id = self.fetch_project_details(hostname)
            part = AzureDevopsAPIUrls.NEW_REPO
            url = f"{hostname}/{self.organization}{part}"
            self.headers["Content-Type"] = "application/json"
            request_data = {
                "name": repo_name,
                "project": {
                    "id": az_project_id
                }
            }
            
            rest_call_create_repo = self.post_api_request_call(url, request_data)
            if rest_call_create_repo.status_code == 201:
                response = rest_call_create_repo.json()
                return {"url": response["remoteUrl"]}
            elif rest_call_create_repo.status_code == 409:
                app.logger.error(rest_call_create_repo.text)
                app.logger.error(rest_call_create_repo.status_code)
                raise AzureDevopsRepositoryExists
        except Exception as err:
            app.logger.error(err)
            raise err

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
        try:
            # Parsing Repo URL to get Scheme and Netloc
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"

            # Check if path starts with "/"
            if path.startswith("/"):
                path = path.replace("/", "", 1)

            # Forming the URL
            part = AzureDevopsAPIUrls.LIST_FILES.format(
                self.organization, self.project_name, self.repo_name, path, branch)
            url = f"{hostname}{part}"
            app.logger.info(url)
            rest_call_repo_list = self.get_api_request_call(url)
            if rest_call_repo_list.status_code == 200:
                files_list = rest_call_repo_list.json()["value"]
                list_of_files = self.list_repo_objects(files_list, path)
                return list_of_files
            elif rest_call_repo_list.status_code in [401, 203]:
                raise RepoAuthentiactionException
            elif rest_call_repo_list.status_code == 404:
                type_of_exception = rest_call_repo_list.json()["typeKey"].lower()
                if type_of_exception == AzureDevops.GIT_REPOSITORY_NOT_FOUND_EXCEPTION:
                    raise InvalidRepoUrlException
                elif (type_of_exception == AzureDevops.GIT_BRANCH_UNRESOLVABLE_EXCEPTION
                      or AzureDevops.GIT_BASE_FOLDER_NOT_FOUND_EXCEPTION):
                    raise InvalidBranchORBaseDirException
                raise VCSException
        except Exception as err:
            app.logger.error(err)
            raise err

    @log_decorator
    def list_repo_objects(self, list_files, path):
        """
        Method for parsing the file path and creating the list of dictionary
        of files as per general format
        """
        if path:
            path = "/" + path
            finalpath = path + '/'
        else:
            path = "/"
            finalpath = ""

        list_of_files = []
        for file_details in list_files:
            component = {}
            if file_details["path"] != path:
                if len(path) > 1:
                    name = file_details["path"].split(path + '/')[1]
                else:
                    name = file_details["path"].split(path)[1]
                component["name"] = name
                component["path"] = finalpath + name
                component["type"] = file_details["gitObjectType"]
                list_of_files.append(component)
        return list_of_files

    @log_decorator
    def read_file(self, repo_name, file_path, branch_name='master', raw_content=False, commit_type = False):
        """
        Function to Read the contents of the file and return file content
        in base64 encoded format
        repo_name (str) name of the repository
        file_path (str) file path
        branch_name (str) name of branch
        raw_content (str) either true or false
        """
        app.logger.info("Inside read file")
        try:
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"

            part = AzureDevopsAPIUrls.FILE_PREVIEW.format(
                self.organization, self.project_name, self.repo_name, file_path, branch_name)
            if raw_content or commit_type:
                part = AzureDevopsAPIUrls.FILE_COMMIT_PREVIEW.format(
                    self.organization, self.project_name, self.repo_name, file_path, branch_name)

            url = f"{hostname}{part}"
            response = self.get_api_request_call(url)
            if response.status_code == 401 or response.status_code == 203:
                raise RepoAuthentiactionException
            if file_path.endswith(".ipynb"):
                file_content = json.dumps(response.json())
            elif file_path.lower().endswith(('.png', '.jpeg', '.jpg', '.bmp', '.gif',
                                             '.xlsx', '.docx')):
                file_content = str(base64.b64encode(
                    response.content)).split("b'")[1].rstrip("'")
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

    @classmethod
    def _check_status_code(cls, response, repo_id=None):
        """Checks the response status code and raises the exceptions"""
        status_code = response.status_code
        if status_code == 401:
            raise RepoAuthentiactionException
        if status_code == 404:
            raise InvalidRepoUrlException    

    @log_decorator
    def fetch_branches(self, repo_name, proxy_details=None):
        """
        Fetches the list of branches in a repository
        Args:
        repo_name (str) : name of the repsoitory
        proxy_details (dict): Dictionary containing proxy details required
            for connecting to git server via proxy, default is None
        returns: list of branches
        """
        try:
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"
            part_get_branch = AzureDevopsAPIUrls.LIST_BRANCH.format(
                self.organization, self.project_name, self.repo_name, "heads/")
            url_get = f"{hostname}{part_get_branch}"
            app.logger.info(url_get)
            if proxy_details:
                self.add_proxy(proxy_details)
            response_get = self.get_api_request_call(url_get)
            self._check_status_code(response_get, self.repo_name)
            branches = []
            for branch in response_get.json()['value']:
                branches.append({
                    'name': branch['name'].replace("refs/heads/", ''),
                    'sha': branch['objectId'],
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
    def create_branch(self, repo_name, branch_name, start_point='master'):
        """
        Creates a new branch from an existing branch or default master branch
        Args:
        repo_name (str): name of the repository
        branch_name (str): name of the branch to be created
        start_point (str): existing branch name from which new branch is to be 
                        created, if not specified default will be the master
                        branch
        returns: None
        """
        app.logger.info("Inside create branch function")
        try:
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"
            part_get_branch = AzureDevopsAPIUrls.SEARCH_BRANCH.format(
                self.organization, self.project_name, self.repo_name, start_point)
            url_get = f"{hostname}{part_get_branch}"
            response_get = self.get_api_request_call(url_get)
            response_data = response_get.json()['value']
            if response_data:
                old_object_id = response_data[0]['objectId']
                part_post_branch = AzureDevopsAPIUrls.CREATE_BRANCH.format(
                    self.organization, self.project_name, self.repo_name)
                url = f"{hostname}{part_post_branch}"
                default_object_id = GenericConstants.DEFAULT_OBJECT_ID
                request_body = [{
                    "name": f"refs/heads/{branch_name}",
                    "newObjectId": old_object_id,
                    "oldObjectId": default_object_id
                }
                ]
                self.headers['Content-Type'] = "application/json"

                response_post = self.post_api_request_call(url, request_body)
                self._check_status_code(response_post, repo_id=self.repo_name)
                error_status = response_post.json().get("value", [])
                if error_status:
                    if not error_status[0]['success']:
                        error_message = f"Branch '{branch_name}' exists in repository '{self.repo_name}'"
                        raise BrachOperationFailureException(error_message)
                return response_post
            else:
                app.logger.error("Branch does not exists")
                raise BrachOperationFailureException(f"Source branch '{branch_name}' does not exists in respository '{self.repo_name}'")
        except RepoAuthentiactionException as ex:
            raise ex
        except BrachOperationFailureException as ex:
            raise ex
        except Exception as ex:
            return ex.args[0], 500

    @log_decorator
    def fetch_start_page_number(self, page_no, per_page):
        """
        Returns the page number which is used for displaying the commits 
        """
        if int(page_no) == 1:
            return 0
        return (int(page_no) - 1) * int(per_page)

    @log_decorator
    def get_commits(self, repo_name, branch_name=None, page_no="1", per_page="20", latest=False):
        """
        Get the commit id's for given the project_id.

        Header X-Project-Id:
            project_id
        Args: 
        repo_name (str): name of the repository
        branch_name (str): name of branch default is None
        page_no (str): page number default is 1
        per_page (str): number of commits per page 20
        latest (bool): This variable is used to get latest commit when true
                       otherwise it will return all the commits
        Return:
            list of  commit id's
        """
        try:
            if branch_name is None:
                branch_name = "master"
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"
            if page_no != "all":
                page_no = 1 if page_no is None else page_no
                per_page = 20 if per_page is None else per_page
                start_page_no = self.fetch_start_page_number(page_no, per_page)
                part = AzureDevopsAPIUrls.FEW_COMMITS.format(
                    self.organization, self.project_name, self.repo_name,
                    branch_name, start_page_no, per_page)
            else:
                part = AzureDevopsAPIUrls.ALL_COMMITS.format(
                    self.organization, self.project_name, self.repo_name, branch_name)
            project_found = True
            url = f"{hostname}{part}"
            commits_obj = self.get_api_request_call(url)
            commits = []
            for commit in commits_obj.json()["value"]:
                commit_info = {
                    'commit_id': commit["commitId"],
                    'commit_date': commit['committer']['date'],
                    'commit_message': commit["comment"],
                    'is_merge_commit': False
                }
                commits.append(commit_info)
                if latest:
                    break
            message = "Project Found"
            return commits, project_found, message
        except Exception as e:
            app.logger.error(e)
            message = "Project Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def get_latest_commit(self, project_id):
        """
                Get the latest commit id from the repo.

                Args:
                    project_id
                Return:
                    latest commit id
                """
        all_commits, project_found, message = self.get_commits(
            self.configuration["repo_url"], self.configuration["branch"], latest= True)
        if all_commits:
            all_commits = all_commits[0]
        return all_commits, project_found, message

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
            hostname = f"{self.git_url.scheme}://{self.git_url.netloc}"

            part = AzureDevopsAPIUrls.SHOW_COMMIT_CHANGE.format(
                self.organization, self.project_name, self.repo_name, commit_id)
            project_found = True
            url = f"{hostname}{part}"
            commits_obj = self.get_api_request_call(url)
            # Get Diff for specified commit id
            diff_list = commits_obj.json()['changes']
            list_of_changed_files = []
            for diff in diff_list:
                if diff.get("item", "").get("isFolder", False) == False:
                    list_of_changed_files.append(diff['item']['path'][1:])
            message = "Changed File Found"
            return list_of_changed_files, project_found, message
        except Exception as e:
            message = "Changed File Not Found"
            project_found = False
            return [], project_found, message

    @log_decorator
    def download_file(self, repo_name, file_path, branch="master"):
        """
        downloads file
        :param file_path:
        :param branch
        :return: file
        """
        try:
            read_json = self.read_file(self.repo_name, file_path, branch)
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
            self.downloading_folder_contents(
                self.repo_name, file_path, folderpath, branch)
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
                    self.downloading_folder_contents(
                        repo_name, file['path'], path, branch)

        except Exception as ex:
            app.logger.error(ex)
            raise ex

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
        return update_file_content(file_path, file_content, enabled_repo, message)

    @log_decorator
    def rename_repo(self, project_name, new_project_name, project_id):
        pass

    @log_decorator
    def delete_branch(self, repo_name, branch_name):
        pass

    @log_decorator
    def create_file(self, repo_name, file_path, file_content,
                    branch_name='master', message='file created'):
        pass

    @log_decorator
    def delete_file(self, repo_name, file_path, branch_name='master', message='file deleted'):
        pass

    @log_decorator
    def list_files_with_content(self, repo_name, file_path):
        pass

    @log_decorator
    def rename_all_repos(self):
        pass

    @log_decorator
    def validate_repo_access(self):
        """
        This method will validate the user by cloning the git project and with
        this it will check the user access for that repository as we do not 
        have direct api for checking the user repository permissions
        """
        pass 
        # Cuurently as there is no direct api to check user access thus 
        # proceeding check repo access with known limitation
