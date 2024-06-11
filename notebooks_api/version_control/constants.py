#! -*- coding: utf-8 -*-
""" GitProvider Constants"""

class GitProvider:
    """ GitProvider Constants"""
    gitlab = "gitlab"
    github = "github"
    bitbucket = "bitbucket"
    azuredevops = "azuredevops"

class MessageConstants:
    """ Message Constants"""
    VALIDATED_SUCCESSFULLY = "Validated successfully"

class ConfigKeyNames:
    """ Class for storing config key names"""
    PROXY_ENABLED_GIT_PROVIDER = "PROXY_ENABLED_GIT_PROVIDER"
    PROXY_DETAILS = "PROXY_DETAILS"

class RepoType:
    PRIVATE_REPO = "PRIVATE"