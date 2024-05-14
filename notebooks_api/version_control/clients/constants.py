"""Constants Module"""
class GenericConstants:
    """Constants Class"""
    PROVIDER = 'provider'
    URL = 'url'
    TOKEN = 'token'
    REPO_NAME = 'repo_name'
    FILE_PATH = 'file_path'
    NAMESPACE = 'namespace'
    PROVIDER_LIST = ['github', 'gitlab', 'bitbucket', 'azuredevops']
    DEFAULT_BRANCH = 'master'
    README_FILE = 'Readme.md'
    DEFAULT_OBJECT_ID = "0000000000000000000000000000000000000000"


class AzureDevopsAPIUrls:
    """Class containing the REST API urls for Azuredevops client"""
    NEW_REPO = "/_apis/git/repositories?api-version=7.0"
    CREATE_BRANCH = "/{}/{}/_apis/git/repositories/{}/refs?api-version=7.0"
    LIST_FILES = "/{}/{}/_apis/git/repositories/{}/items?scopePath={}&versionDescriptor.version={}&recursionLevel=oneLevel"
    FILE_PREVIEW = "/{}/{}/_apis/git/repositories/{}/items?path={}&latestProcessedChange=true&includeContent=true&versionDescriptor.version={}&api-version=7.0"
    FILE_COMMIT_PREVIEW = "/{}/{}/_apis/git/repositories/{}/items?path={}&versionType=commit&version={}&includeContent=true&api-version=7.0"
    SEARCH_BRANCH = "/{}/{}/_apis/git/repositories/{}/refs?filter=heads/{}&api-version=7.0"
    LIST_BRANCH = "/{}/{}/_apis/git/repositories/{}/refs?filter={}&api-version=7.0"
    PROJECT_DETAILS = "{}/{}/_apis/projects/{}?api-version=7.0"
    ALL_COMMITS = "/{}/{}/_apis/git/repositories/{}/commits?searchCriteria.itemVersion.version={}&searchCriteria.itemVersion.versionType=branch&api-version=7.0"
    FEW_COMMITS = "/{}/{}/_apis/git/repositories/{}/commits?searchCriteria.itemVersion.version={}&searchCriteria.$skip={}&searchCriteria.$top={}&searchCriteria.itemVersion.versionType=branch&api-version=7.0"
    SHOW_COMMIT_CHANGE = "/{}/{}/_apis/git/repositories/{}/commits/{}/changes?api-version=7.0"


class AzureDevops:
    """
    This class stores the typeKey constants for identifying the type of
    exception coming in the response of ADO rest API
    """
    GIT_REPOSITORY_NOT_FOUND_EXCEPTION = "gitrepositorynotfoundexception"
    GIT_BRANCH_UNRESOLVABLE_EXCEPTION = "gitunresolvabletocommitexception"
    GIT_BASE_FOLDER_NOT_FOUND_EXCEPTION = "gititemnotfoundexception"

class GitlabConstants:
    GIT_TREE_NOT_FOUND_EXCEPTION = "404 tree not found"
    GIT_PATH_NOT_FOUND_EXCEPTION = "404 invalid revision or path Not Found"
