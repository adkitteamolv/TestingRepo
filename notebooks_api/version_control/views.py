# -*- coding: utf-8 -*-

"""Views module."""
import os
import json
import shutil
import tempfile
from distutils.dir_util import copy_tree
from urllib.parse import quote

from flask import g, current_app
from uuid import uuid4
from git import Repo

from mosaic_utils.ai.logger.utils import log_decorator
from mosaic_utils.ai.git_repo import utils as git_details

from .clients import get_client
from .clients.constants import GenericConstants
from .constants import ConfigKeyNames
from notebooks_api.utils.file_utils import git_push_file, git_clone, replace_special_chars_with_ascii, \
    checkout_new_branch, extract_tar, extract_zip, decode_base64_to_string
from notebooks_api.utils.exceptions import ErrorCodes, VCSException, NoRepoException, RepoAuthentiactionException, \
    MessageCodes, NoGitRepoEnabled, MosaicException, FileWithSameNameExists, FailedDuringGitPush, FailedInGitUpload


@log_decorator
def if_delete_nb(data, git_temp_dir, path, delete_nb):
    """Method with operations to perform when delete_nb is not none"""
    is_folder = data.get("isFolder")
    if is_folder:
        shutil.rmtree(os.path.join(git_temp_dir, path, delete_nb))
    else:
        os.unlink(os.path.join(git_temp_dir, path, delete_nb))


@log_decorator
def when_response_is_blank(git_temp_dir, temp_dir):
    """Method with operations to perform when response is blank"""
    if os.path.isdir(git_temp_dir):
        shutil.rmtree(git_temp_dir)
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)


@log_decorator
def if_not_delete_nb(ignore_duplicate, temp_dir, git_temp_dir, entity_type):
    """Method to perform operations when delete_nb parameter is not none"""
    if ignore_duplicate:
        folder_list = os.listdir(temp_dir)
        for i in folder_list:
            if os.path.isfile(os.path.join(git_temp_dir, entity_type, i)):
                os.unlink(os.path.join(git_temp_dir, entity_type, i))
            elif os.path.isdir(os.path.join(git_temp_dir, entity_type, i)):
                shutil.rmtree(os.path.join(git_temp_dir, entity_type, i))
        copy_tree(temp_dir, os.path.join(git_temp_dir, entity_type))
    else:
        copy_tree(temp_dir, os.path.join(git_temp_dir, entity_type))


@log_decorator
def check_duplicate_name(git_dir, folder_dir, upload_path="", base_folder=""):
    """
    Method to check the duplicate name
    :param git_dir:
    :param folder_dir:
    :param upload_path:
    :param base_folder
    :return:
    """
    folder_list = os.listdir(os.path.join(folder_dir, upload_path))
    for i in folder_list:
        if i == 'Zeppelin-Notebooks':
            pass
        elif os.path.isdir(os.path.join(git_dir, base_folder, upload_path, i)):
            shutil.rmtree(os.path.join(git_dir, base_folder, upload_path, i))
            copy_tree(git_dir, folder_dir)
            raise ValueError(
                "Folder with same name already exist"
            )
        elif os.path.isfile(os.path.join(git_dir, base_folder, upload_path, i)):
            os.remove(os.path.join(git_dir, base_folder, upload_path, i))
            copy_tree(git_dir, folder_dir)
            g.temp_dir = folder_dir
            raise FileWithSameNameExists


class View:

    def __init__(self, repo_details=None, repo_id=None, project_id=False):
        from notebooks_api.notebook.manager import get_git_repo, list_git_repo, add_git_repo
        if repo_details or repo_id or project_id:
            if repo_details:
                g.repo_details = repo_details
            if not hasattr(g, 'repo_details') and repo_id:
                g.repo_details = get_git_repo(repo_id)
            if not hasattr(g, 'repo_details') and project_id:
                g.repo_details = list_git_repo(project_id=project_id, repo_status="Enabled")
            g.CLIENT = get_client(g.repo_details)

    def create_branch(self, payload):
        """
        Create a new branch of the repo
        """
        try:
            git_temp_dir = None
            default_branch_flag = str(payload.get("default_branch_flag", "false")).lower() == "true"
            if default_branch_flag:
                enabled_repo = g.repo_details
                git_temp_dir = tempfile.mkdtemp()
                url_parts = enabled_repo["repo_url"].split("//")
                url_splits = str(url_parts[1]).split("@")
                url_right_part_without_user = url_splits[1] \
                    if len(url_splits) == 2 else url_splits[0]
                password = quote(enabled_repo["password"], safe='')
                remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], enabled_repo["username"],
                                                       password, url_right_part_without_user)
                proxy_details = enabled_repo.get('proxy_details', None)
                if proxy_details:
                    proxy_ip = proxy_details.get("IPaddress", None)
                    verify_ssl = proxy_details.get('SSLVerify', True)
                    proxy_type = proxy_details.get("Protocol", 'http')
                    proxy_type = "http"  # Currently kept it to http for SCB use case
                    # When proxy type was set to https the git clone did not work
                    proxy_username = proxy_details.get('UsernameOrProxy', None)
                    proxy_password = proxy_details.get('PasswordOrProxy', None)
                    if proxy_username and proxy_password:
                        if verify_ssl:
                            Repo.clone_from(remote_url, git_temp_dir,
                                            config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}",
                                            allow_unsafe_options=True)
                        else:
                            Repo.clone_from(remote_url, git_temp_dir,
                                            config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}",
                                            allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'})
                    else:
                        if verify_ssl:
                            Repo.clone_from(remote_url, git_temp_dir,
                                            config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True)
                        else:
                            Repo.clone_from(remote_url, git_temp_dir,
                                            config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True,
                                            env={'GIT_SSL_NO_VERIFY': '1'})
                else:
                    Repo.clone_from(remote_url, git_temp_dir)
                repo = Repo(git_temp_dir)
                filename = os.path.join(git_temp_dir, GenericConstants.README_FILE)
                open(filename, 'wb').close()
                repo.index.add([filename])
                repo.index.commit("initial commit")
                branch = payload.get("branch", GenericConstants.DEFAULT_BRANCH)
                branch = GenericConstants.DEFAULT_BRANCH if branch.strip() == "" else branch
                if branch != GenericConstants.DEFAULT_BRANCH:
                    repo.git.checkout('-b', branch)
                repo.git.push("origin", "-u", branch)
                shutil.rmtree(git_temp_dir)
            else:
                g.CLIENT.create_branch(g.repo_details["repo_url"],
                                       payload["branch"], payload["parent_branch"])
            return "", 201
        except Exception as ex:
            if git_temp_dir and os.path.isdir(git_temp_dir):
                shutil.rmtree(git_temp_dir)
            current_app.logger.error("Exception - " + str(ex))
            return ex.args[0], 500

    def list_branches(self, proxy_details, repo=None):
        try:
            # proxy_details = request.args.get("proxy_details")
            current_app.logger.error("Exception - " + str(proxy_details))
            if proxy_details:
                proxy_details = json.loads(proxy_details)
                proxy_details_json = json.loads(proxy_details)

                branches = g.CLIENT.fetch_branches(g.repo_details["repo_url"], proxy_details_json)
            else:
                branches = g.CLIENT.fetch_branches(g.repo_details["repo_url"])
            return json.dumps(branches), 200
        except MosaicException as ex:
            current_app.logger.error("Exception - " + str(ex.message))
            raise ex
        except Exception as ex:
            current_app.logger.error("Exception - " + str(ex))
            raise VCSException

    def validate_git(self, payload):
        try:
            # VALIDATE CREDENTIALS AND ACCESS
            if payload.get('repo_type', '') in current_app.config.get(ConfigKeyNames.PROXY_ENABLED_GIT_PROVIDER, []):
                payload['proxy_details'] = current_app.config.get(ConfigKeyNames.PROXY_DETAILS, {})
            g.CLIENT = get_client(payload)
            g.CLIENT.validate_repo_access()
            g.CLIENT.list_files(payload["repo_url"], payload["base_folder"],
                                payload.get("branch", ""), limit=1)
            return MessageCodes.messageCode.get("Repo_Validation_Success", "REPO_VALIDATION_SUCCESS_001"), 200
        except MosaicException as ex:
            current_app.logger.exception(ex)
            return ex.message_dict(), ex.code
        except Exception as ex:
            current_app.logger.exception(ex)
            return MessageCodes.messageCode.get("Repo_Validation_Error", "REPO_VALIDATION_ERROR_001"), 500

    def get_latest_commit_id(self, project_id):
        """ Method to fetch the recent commit id """
        current_app.logger.debug(f"Fetching latest commit ID")
        latest_commit_id, project_found, message = g.CLIENT.get_latest_commit(project_id)
        code = 204
        if project_found:
            code = 200
        return latest_commit_id, message, code

    @log_decorator
    def rename_repo(self, project_name, new_project_name, project_id):
        repo = g.CLIENT.rename_repo(project_name, new_project_name, project_id)
        return json.dumps(repo)

    @log_decorator
    def read_file(self, repo, file_path, raw_content, commit_type, branch=None, commit=None):
        try:
            if raw_content:
                branch = commit
                file_path = decode_base64_to_string(file_path)
            response = g.CLIENT.read_file(g.repo_details["repo_url"], file_path, branch, raw_content, commit_type)
            return response, 200
        except RepoAuthentiactionException as e:
            current_app.logger.exception(e)
            return e.message, 500
        except Exception as ex:
            return ex.args[0], 500

    @log_decorator
    def list_repo(self, repo, file_path):
        try:
            if not g.repo_details:
                raise NoRepoException
            repo_files = dict()
            if file_path is None:
                file_path = g.repo_details["base_folder"]

            response = g.CLIENT.list_files(g.repo_details["repo_url"], file_path,
                                           g.repo_details.get("branch", ""))
            # filtered response will ignore hidden files starting
            filtered_response = []
            for dic in response:
                for key, val in dic.items():
                    if key == "name" and not val.startswith("."):
                        filtered_response.append(dic)
            repo_details = {'repo_name': g.repo_details.get('repo_name'),
                            'branch': g.repo_details.get('branch'),
                            'repo_status': 'Enabled',
                            'repo_type': g.repo_details.get('repo_type'),
                            'repo_url': g.repo_details.get('repo_url'),
                            'username': g.repo_details.get('username'),
                            'freeze_flag': g.repo_details.get('freeze_flag'),
                            'repo_id': g.repo_details.get('repo_id')}
            repo_files['repo_details'] = repo_details
            repo_files['files'] = filtered_response
            return repo_files, 200
        except NoRepoException as e:
            current_app.logger.exception(e)
            return e.message, e.code
        except VCSException as e:
            current_app.logger.exception(e)
            return e.message, 500
        except Exception as e:
            current_app.logger.exception(e)
            return ErrorCodes.VCS_0006, 500

    @log_decorator
    def _git_upload(self, repo, temp_dir, commit_message, ignore_duplicate=False, delete_nb=None, path=None, upload_path="", data={}):
        """
        :param repo:
        :param temp_dir:
        :param ignore_duplicate:
        :param delete_nb:
        :param path:
        :param commit_message:
        :return:
        """
        try:
            git_temp_dir = tempfile.mkdtemp()
            # pylint: disable=too-many-function-args
            enabled_repo = git_details.get_repo(
                repo,
                g.user["email_address"],
                g.user["mosaicId"],
                g.user["first_name"]
            )
            if enabled_repo is None:
                raise NoGitRepoEnabled
            remote_url = enabled_repo['url']
            git_branch = enabled_repo['branch']
            proxy_details = enabled_repo.get("proxy_details", {})
            if proxy_details:
                proxy_details = json.loads(proxy_details)
                git_clone(git_temp_dir, remote_url, git_branch, proxy_details)
            else:
                git_clone(git_temp_dir, remote_url, git_branch)
            if not ignore_duplicate:
                check_duplicate_name(git_temp_dir, temp_dir, upload_path, enabled_repo['base_folder'])
            if not delete_nb:
                if_not_delete_nb(ignore_duplicate, temp_dir, git_temp_dir, enabled_repo['base_folder'])
            else:
                if_delete_nb(data, git_temp_dir, path, delete_nb)
            if proxy_details:
                response = git_push_file(git_temp_dir, git_branch, commit_message, proxy_details)
            else:
                response = git_push_file(git_temp_dir, git_branch, commit_message)
            if response != '':
                when_response_is_blank(git_temp_dir, temp_dir)
            return response, temp_dir
        except MosaicException as me:
            current_app.logger.exception(me)
            raise me
        except ValueError as ex:
            current_app.logger.exception(ex)
            raise FailedDuringGitPush
        except Exception as ex2:
            current_app.logger.exception(ex2)
            raise FailedInGitUpload
        finally:
            when_response_is_blank(git_temp_dir, temp_dir)

    @log_decorator
    def create_repo(self, repo=None):
        """
        Create git repo
        Args:
            repo (str): name of the git repository
        Returns:
            JSON of the git repo
        """
        repo = repo if repo else uuid4()
        proxy_details = g.repo_details.get("proxy_details", None)
        provider = g.CLIENT.provider
        repo1 = g.CLIENT.create_repo(repo)
        if proxy_details:
            self.initial_commit(repo, branch=g.repo_details["branch"], proxy_details=proxy_details,
                                git_provider=provider)
        else:
            self.initial_commit(repo, branch=g.repo_details["branch"], git_provider=provider)
        return g.repo_details['repo_url']

    @log_decorator
    def upload_folder(self, repo, file, upload_path, notebook_id, commit_message, override_flag=None):
        temp_file_dir = tempfile.mkdtemp()
        if len(upload_path) > 0:
            os.makedirs(os.path.join(temp_file_dir, upload_path))
        file.save(os.path.join(temp_file_dir, upload_path, file.filename))
        tmp_file_path = os.path.join(temp_file_dir, upload_path, file.filename)
        if file.filename.endswith(".tar.gz"):
            extract_tar(tmp_file_path, os.path.join(temp_file_dir, upload_path))
            os.unlink(tmp_file_path)
            response, temp_dir = self._git_upload(repo, temp_file_dir, commit_message=commit_message,
                                                  upload_path=upload_path, ignore_duplicate=override_flag)
        elif file.filename.endswith(".zip"):
            extract_zip(tmp_file_path, os.path.join(temp_file_dir, upload_path))
            os.unlink(tmp_file_path)
            response, temp_dir = self._git_upload(repo, temp_file_dir, commit_message=commit_message,
                                                  upload_path=upload_path, ignore_duplicate=override_flag)
        elif file.filename.endswith("note.json"):
            if notebook_id:
                tmpfile = tempfile.mkdtemp()
                os.makedirs(os.path.join(tmpfile, "Zeppelin-Notebooks", notebook_id))
                dir_tmp = os.path.join(tmpfile, "Zeppelin-Notebooks", notebook_id)
                copy_tree(os.path.join(temp_file_dir, upload_path), dir_tmp)
                response, temp_dir = self._git_upload(repo, tmpfile, commit_message=commit_message,
                                                      upload_path=upload_path, ignore_duplicate=override_flag)
                when_response_is_blank(tmpfile, None)
            else:
                response, temp_dir = self._git_upload(repo, temp_file_dir, commit_message=commit_message,
                                                      upload_path=upload_path, ignore_duplicate=override_flag)
        else:
            response, temp_dir = self._git_upload(repo, temp_file_dir, commit_message=commit_message,
                                                  upload_path=upload_path, ignore_duplicate=override_flag)
        when_response_is_blank(temp_file_dir, None)
        return response, temp_dir

    @log_decorator
    @log_decorator
    def initial_commit(self, repo, branch="master", proxy_details={}, git_provider=""):
        """
        :param repo: Repo Name
        :param branch: Repo Branch
        :param proxy_details: Dictionary containing proxy server information
        :param git_provider: string default is '' and it will take value from git.CLIENT.provider
        :return:
        """
        username = current_app.config["GIT_NAMESPACE"]
        password = replace_special_chars_with_ascii(str(current_app.config["GIT_PASSWORD"]))
        git_temp_dir = tempfile.mkdtemp()
        if git_provider == "azuredevops":
            url = "{0}/_git/{1}".format(current_app.config["REMOTE_URL"], repo)
        else:
            url = "{0}/{1}.git".format(current_app.config["REMOTE_URL"], repo)
        url_parts = url.split("//")
        remote_url = "{0}//{1}:{2}@{3}".format(url_parts[0], username, password, url_parts[1])
        if proxy_details:
            git_clone(git_temp_dir, remote_url, branch="", proxy_details=proxy_details)
        else:
            git_clone(git_temp_dir, remote_url, branch="")
        if branch != GenericConstants.DEFAULT_BRANCH:
            checkout_new_branch(git_temp_dir, branch)
        os.makedirs(os.path.join(git_temp_dir, "notebooks"))
        os.makedirs(os.path.join(git_temp_dir, "flows"))
        os.makedirs(os.path.join(git_temp_dir, "workflows"))
        os.makedirs(os.path.join(git_temp_dir, "preposthooks"))
        file_content = ".ipynb_checkpoints/ \n .placeholder \n ~* \n"
        temp = open(os.path.join(git_temp_dir, ".gitignore"), 'w')
        temp.write(file_content)
        temp.close()
        file_content = "#!/bin/sh\necho 'EXECUTION_TYPE='$EXECUTION_TYPE\necho 'EXECUTION_DIR='$EXECUTION_DIR\necho 'JAR_NAME='$JAR_NAME\nif [ ${EXECUTION_TYPE} = 'workflow' ]\nthen\ncd ./workflows/${EXECUTION_DIR}/\nmvn -o clean package -DskipTests\njava -jar target/${JAR_NAME}\nelif [ ${EXECUTION_TYPE} = 'preposthook' ]\nthen\nsh /preposthooks/${EXECUTION_DIR}/entrypoint.sh\nfi"
        temp = open(os.path.join(git_temp_dir, "entrypoint.sh"), 'w')
        temp.write(file_content)
        temp.close()
        temp = open(os.path.join(git_temp_dir, "notebooks", ".placeholder"), 'w')
        temp.write("")
        temp.close()
        temp = open(os.path.join(git_temp_dir, "flows", ".placeholder"), 'w')
        temp.write("")
        temp.close()
        temp = open(os.path.join(git_temp_dir, "workflows", ".placeholder"), 'w')
        temp.write("")
        temp.close()
        temp = open(os.path.join(git_temp_dir, "preposthooks", ".placeholder"), 'w')
        temp.write("")
        temp.close()
        if proxy_details:
            response = git_push_file(git_temp_dir, git_branch=branch, proxy_details=proxy_details)
        else:
            response = git_push_file(git_temp_dir, git_branch=branch)
        if response != '':
            if os.path.isdir(git_temp_dir):
                shutil.rmtree(git_temp_dir)
