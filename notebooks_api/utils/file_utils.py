# -*- coding: utf-8 -*-
import os
import tarfile
import logging as log
from zipfile import ZipFile
import urllib.parse
import base64
from git import *
import json


def extract_tar(tar_file, output_dir):
    tar = tarfile.open(tar_file)
    tar.extractall(path=output_dir)
    tar.close()


def extract_zip(zip_file, output_dir):
    with ZipFile(zip_file, 'r') as f:
        f.extractall(path=output_dir)


def git_clone(dir_name, remote_url, branch="master", proxy_details = {}):
    try:
        if proxy_details:
            if type(proxy_details) == str:
                proxy_details = json.load(proxy_details)
            
            proxy_ip = proxy_details.get("IPaddress", None)
            verify_ssl = proxy_details.get('SSLVerify', True)
            proxy_type = proxy_details.get("Protocol", 'http')
            proxy_type = "http" # Currently kept it to http for SCB use case
            # When proxy type was set to https the git clone did not work 
            proxy_username = proxy_details.get('UsernameOrProxy', None)
            proxy_password = proxy_details.get('PasswordOrProxy', None)
            if proxy_username and proxy_password:
                if verify_ssl:
                    Repo.clone_from(remote_url, dir_name, branch=branch, 
                        config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}", allow_unsafe_options=True) \
                        if branch else Repo.clone_from(remote_url, dir_name, 
                            config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}", allow_unsafe_options=True)
                else:
                    Repo.clone_from(remote_url, dir_name, branch=branch, 
                        config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}", allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'}) \
                        if branch else Repo.clone_from(remote_url, dir_name, 
                            config=f"http.proxy={proxy_type}://{proxy_username}:{proxy_password}@{proxy_ip}", allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'})
            else:
                if verify_ssl:
                    Repo.clone_from(remote_url, dir_name, branch=branch, config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True) \
                    if branch else Repo.clone_from(remote_url, dir_name, config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True)
                else:
                    Repo.clone_from(remote_url, dir_name, branch=branch, config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'}) \
                    if branch else Repo.clone_from(remote_url, dir_name, config=f"http.proxy={proxy_type}://{proxy_ip}", allow_unsafe_options=True, env={'GIT_SSL_NO_VERIFY': '1'})
        else:
            Repo.clone_from(remote_url, dir_name, branch=branch) \
                if branch else Repo.clone_from(remote_url, dir_name)
    except Exception as ex:
        log.exception(ex)
        raise ValueError("Failed during git clone")


def is_push_rejected(text) -> (bool, str):
    """
    Checks for invalid commit message in text
    :param text:
    :return: boolean status, and error message
    """
    errors = ["One of your commit messages is missing a valid issue key", "No Jira Issue found in commit message","commit messages that are missing valid issue keys",
              "Check your branch permissions configuration with the project administrator", "You are not allowed to push code to protected branches on this project.",
              "Protected branch update failed"]
    additional_errors = os.getenv("PUSH_REJECTED_ERRORS")
    if additional_errors:
        errors.extend(additional_errors.split(","))

    for error in errors:
        if error in text:
            print("Invalid Commit ::: %s", error)
            return True, error
    return False, ""


def git_push_file(dir_name, git_branch='master', commit_message="Folder/File upload", proxy_details={}):
    try:
        from flask import g
        repo = Repo(dir_name)
        if proxy_details:
            sslverify = proxy_details.get("SSLVerify", True)
            repo.config_writer().set_value("http", "sslVerify", sslverify).release()    
        repo.config_writer().set_value("user", "name", g.user["first_name"]).release()
        repo.config_writer().set_value("user", "email", g.user["email_address"]).release()
        repo.config_writer().set_value("push", "default", "simple").release()
        repo.git.add('--all')
        commit_result = repo.index.commit(commit_message)
        repo.git.push('origin', git_branch)
        repo.git.add(update=True)
        return str(commit_result)
    except Exception as ex:
        log.exception(ex)
        err = "Failed during git push"
        invalid_commit, msg = is_push_rejected(str(ex))
        if invalid_commit:
            # equivalent to git reset --soft HEAD~1
            repo.head.reset('HEAD~1', index=False, working_tree=False)
            raise ValueError(f"{err}, {msg}")

        raise ValueError(err)


def replace_special_chars_with_ascii(password):
    # Function checks if the password
    # contains any special character
    # if found, it will encode it
    return urllib.parse.quote(password)


def git_chekout_commit(dir_name, commit_id):
    try:
        repo = Repo(dir_name)
        repo.config_writer().set_value("user", "name", "admin").release()
        repo.config_writer().set_value("user", "email", "admin").release()
        repo.config_writer().set_value("push", "default", "simple").release()
        repo.git.checkout(commit_id)
    except Exception as ex:
        log.exception(ex)
        raise ValueError("Failed to checkout commit id.")


def decode_base64_to_string(base64_value):
    return base64.b64decode(base64_value).decode('utf-8')


def encode_to_base64(string_value):
    return base64.b64encode(string_value.encode('utf-8'))

def checkout_new_branch(base_dir, branch_to_checkout):
    repo = Repo(base_dir)
    repo.git.checkout('-b', branch_to_checkout)



