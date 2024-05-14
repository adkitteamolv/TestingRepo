# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
from git import *
import json
from .file_utils import git_clone, git_push_file


def when_response_is_blank(git_temp_dir, temp_dir):
    """Method with operations to perform when response is blank"""
    if os.path.isdir(git_temp_dir):
        shutil.rmtree(git_temp_dir)
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)

def update_file_content(file_path, file_content, enabled_repo, message='file updated'):
    """
    Update file from the repository.
    Args:
        file_path (str): path of the file to be read
        file_content (str): content of the file
        enabled_repo (dict): enabled repo details
        message(str): commit message
    """
    temp_file_dir = tempfile.mkdtemp()
    if "/" not in file_path:
        file_path = "/" + file_path
    filepath, filename = file_path.rsplit('/', 1)
    try:
        git_temp_dir = tempfile.mkdtemp()

        remote_url = enabled_repo['url']
        branch_name = enabled_repo.get("branch", "master")
        proxy_details = enabled_repo.get("proxy_details", {})
        if proxy_details:
            if type(proxy_details) == str:
                proxy_details = json.loads(proxy_details)
            git_clone(git_temp_dir, remote_url, branch_name, proxy_details)
        else:
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
                    os.unlink(os.path.join(
                        git_temp_dir, filepath, filename))
                else:
                    os.makedirs(os.path.join(git_temp_dir, filepath))
                shutil.copy(os.path.join(temp_file_dir, filepath, filename),
                            os.path.join(git_temp_dir, filepath, filename))
            else:
                if os.path.exists(os.path.join(git_temp_dir, filepath, i)):
                    os.unlink(os.path.join(git_temp_dir, filepath, i))
                shutil.copy(os.path.join(temp_file_dir, filepath, filename),
                            os.path.join(git_temp_dir, filepath, i))

        if proxy_details:
            response = git_push_file(git_temp_dir, branch_name, message, proxy_details)
        else:
            response = git_push_file(git_temp_dir, branch_name, message)
        if response != '':
            when_response_is_blank(git_temp_dir, temp_file_dir)
        return {
            'sha': '',
            'url': '',
        }
    except Exception as ex:
        raise ex
