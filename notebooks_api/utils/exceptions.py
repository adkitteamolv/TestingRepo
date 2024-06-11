#! -*- coding: utf-8 -*-
""" This module contains different exceptions used by the mosaic ai-logistics """
import configparser
import os

# pylint: disable=too-few-public-methods
class ErrorCodes:
    """ Exceptions used by mosaic ai-logistics """

    # MOSAIC customize response message
    MOSAIC_0001 = "Quota exceeded. Please stop your running notebooks and try again"
    # pylint: disable=line-too-long
    MOSAIC_0002 = "We are unable to launch a new notebook at this time due to high utilization of available resources."
    MOSAIC_0003 = "Unable to delete pod, Please try after sometime"
    MOSAIC_0004 = "Please login to continue"
    MOSAIC_0005 = "Permission denied"
    MOSAIC_0006 = "Invalid license... Permission denied"
    MOSAIC_0007 = "Template already Running."
    MOSAIC_0008 = "Template is still getting stopped. Please try after some time"
    MOSAIC_0009 = "Unable to trigger experiment recipes. Please try after some time"

    # Error message
    ERROR_0001 = "Requested resource does not exist"
    ERROR_0002 = "Oops! Something went wrong, Please try again later"
    ERROR_0003 = "Error while searching for available packages, Please try again later"
    ERROR_0004 = "Error while searching for compatiable versions, Please try again later"
    ERROR_0005 = "Unable to fetch snapshots. Kindly try again later !"
    ERROR_0006 = "You do not have a subscription. Please avail a subscription and try again"
    ERROR_0007 = "Your subscription has expired. Please renew the subscription and try again"
    ERROR_0008 = "Your subscription quota has been exceeded. Please renew the subscription and try again"
    ERROR_0009 = "Your user quota has been exceeded. Please increase your usage quota and try again"
    ERROR_0010 = "Your project quota has been exceeded. Please increase your usage quota and try again"
    ERROR_0011 = "Failed to fetch User role deatils. Kindly try again later !"
    ERROR_0012 = "Data is already there in db table, Please verify your data and try again."
    ERROR_0013 = "Unable to fetch data from SPCS due to : {error}"
    ERROR_0014 = "Unable to fetch data from connection manager due to :{error}"

    #VCS Error messages
    VCS_0001 = "Invalid Credentials, Please provide the correct information"
    VCS_0002 = "No repository is enabled, Kindly enable a git repo for this project"
    VCS_0003 = "Invalid URL, Please provide the correct information"
    VCS_0004 = "Invalid Branch/Base Folder, Please provide the correct information"
    VCS_0005 = "Please check access rights"
    VCS_0006 = "Something went wrong, please contact admin"
    VCS_0007 = "Authorisation failed, Please add Admin user in your repository" \
                  " or Ask infra team to set Admin credentials in configuration."
    VCS_0008 = "Organization or project not found"
    VCS_0009 = " A Git repository with the same name already exists."


class StatusCodes:
    """ Exceptions used by mosaic kubespawner """

    # MOSAIC customize response message
    MOSAIC_0001 = "Job has been successfully executed"
    MOSAIC_0002 = "Job submitted successfully"

    # Error message
    ERROR_0001 = "Scheduled Job failed"
    ERROR_0002 = "Oops ! An error occured while trying to execute the scheduled job. Please try again later."
    ERROR_0003 = "Unable to fetch pod metrics"
    ERROR_0004 = "Unable to fetch pod name"
    ERROR_0005 = "Unable to delete pod"
    ERROR_0006 = "Unable to create k8 resources for template"
    ERROR_0007 = "Unable to delete k8 resources for template"
    ERROR_0008 = "Unable to launch template"
    ERROR_0009 = "Template launched pod, but its in Pending state"
    ERROR_0010 = "Unable to create cron job"
    ERROR_0011 = "Unable to delete cron job"
    ERROR_0012 = "Unable to update cron job"


class MessageResponseKeys:
    exception_name = "exception_name"
    message_code = "message_code"
    message = "message"
    status = "status"


class MessageCodes:
    base_path = os.path.dirname(os.path.realpath(__file__))
    default = os.path.join(base_path, "../message_code.ini")
    message_code_file = os.getenv("NOTEBOOKS_API_ERROR_MESSAGES", default)
    messageCode = configparser.ConfigParser(allow_no_value=True)
    messageCode.read(message_code_file)


class MosaicException(Exception):
    """Mosaic ai common exception"""
    code = 500
    status = "Error"  # Same will be assigned to child class variables
    exception_name = "MosaicException"
    message_code = "MOSAIC_EXCEPTION_001"
    message = MessageCodes.messageCode.get("MosaicException", "MOSAIC_EXCEPTION_001")

    def __init__(self, msg_code=None):
        if msg_code is not None:
            self.message_code = msg_code
            self.message = MessageCodes.messageCode.get(self.__class__.__name__, self.message_code)

    def message_dict(self, exp_name="", exp_code="", error_message="", stats=""):
        """
         Generate API response dictionary
         Params:
         exp_name = Error exception defined in ini
         exp_code = Message Code defined in ini
         error_message = Message against the message code from ini
         stats = Success/Error
        """
        msg_dict = {
            MessageResponseKeys.exception_name: exp_name if exp_name else self.__class__.__name__,
            MessageResponseKeys.message_code: exp_code if exp_code else self.message_code,
            MessageResponseKeys.message: error_message if error_message else MessageCodes.messageCode.get(self.__class__.__name__, self.message_code),
            MessageResponseKeys.status: stats if stats else self.status
        }
        return msg_dict


class VCSException(MosaicException):
    """ Common exceptions used by mosaic version control """
    code = 500
    message_code = "VCS_ERROR_001"


class PluginException(MosaicException):
    """ Plugin related exceptions """
    code = 500
    message_code = "PLUGIN_ERROR_0001"

class UploadFileException(MosaicException):
    """ Plugin related exceptions """
    code = 500
    message_code = "UPLOAD_FILE_ERROR_0001"


class PreviewFileException(MosaicException):
    """ Plugin related exceptions """
    code = 500
    message_code = "Preview_FILE_ERROR_0001"

class NoGitRepoEnabled(MosaicException):
    """ Plugin related exceptions """
    code = 400
    message_code = "NO_GIT_REPO_ENABLED_ERROR_001"


class SpawningError(MosaicException):
    """ Spawning error used by mosaic ai-logistics """
    code = 400
    message_code = "SPAWNING_ERROR_001"


class NoSubscriptionException(MosaicException):
    """No Subscription Exception"""
    code = 500
    message_code = "NO_SUBS_ERROR_001"


class SubscriptionExpiredException(MosaicException):
    """Subscription Expiry Exception"""
    code = 500
    message_code = "SUBS_EXPIRED_ERROR_001"


class SubscriptionExceededException(MosaicException):
    """Subscription Exceeded Exception"""
    code = 500
    message_code = "SUBS_EXCEED_ERROR_001"


class UserQuotaExceededException(MosaicException):
    """User Quota Exceeded Exception"""
    code = 500
    message_code = "USER_QUOTA_EXCEED_ERROR_001"


class ProjectQuotaExceededException(MosaicException):
    """Project Quota Exceeded Exception"""
    code = 500
    message_code = "PROJECT_QUOTA_EXCEED_ERROR_001"


class QuotaExceedException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 429
    message_code =  "QUOTA_EXCEED_ERROR_001"


class RepoAuthentiactionException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 500
    message_code =  "REPO_AUTH_001"


class BrachOperationFailureException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 500
    message = "Unable to perform branch operation!"


class InvalidBranchORBaseDirException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 404
    message_code = "INVALID_BRANCH_001"


class InvalidRepoUrlException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 404
    message_code = "INVALID_REPO_URL_001"


class ApiAuthorizationException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 500
    message_code = "API_AUTH_001"


class RepoAccessException(MosaicException):
    """ Spawning error used by mosaic version control """
    code = 403
    message_code = "REPO_ACCESS_001"


class NoRepoException(MosaicException):
    """ no repo exception used by mosaic version control """
    code = 400
    message_code = "REPO_UNAVAILABLE_001"


class AzureDevopsOrgProjectException(MosaicException):
    """ Error while extracting the organization and project name
        from Git repo url """
    code = 422
    message_code = "AZURE_ORG_001"


class AzureDevopsRepositoryExists(MosaicException):
    """ When a repository with same name already exists """
    code = 409
    message_code = "AZURE_REPO_EXIST_001"


class UserRoleException(MosaicException):
    code=500
    message_code = "UR_ERROR_001"


class ExperimentWithSameNameException(MosaicException):
    """Experiment with same name Exception"""
    code = 400
    message_code = "EXPERIMENT_SAME_NAME_ERROR_0001"


class FileWithSameNameExists(MosaicException):
    """When a file with the same name already exists """
    code = 400
    message_code = "FILE_SAME_NAME_EXIST_001"

class FailedDuringGitPush(MosaicException):
    """When a file with the same name already exists """
    code = 400
    message_code = "FAILED_DURING_GIT_PUSH"

class FailedInGitUpload(MosaicException):
    code = 400
    message_code = "FAILED_IN_GIT_UPLOAD"


class FetchProjectDetailException(MosaicException):
    """Exception in fetching Project details """
    code = 500
    message_code = "FETCH_PROJECT_DETAIL_ERROR_001"


class CreateK8ResourceBYOCException(MosaicException):
    """Exception in creating K8 resource """
    code = 500
    message_code = "CREATE_K8_RESOURCE_BYOC_ERROR_001"


class ServiceConnectionError(MosaicException):
    """Authorization error method"""
    code = 503
    message_code = "SERVICE_CONNECTION_ERROR_001"


class FetchProjectResourceQuotaError(MosaicException):
    """Exception in fetching Project resource quota """
    code = 500
    message_code = "FETCH_PROJECT_RESOURCE_QUOTA_ERROR_001"