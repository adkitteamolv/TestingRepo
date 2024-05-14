# -*- coding: utf-8 -*-
import json
import requests, re

# from notebooks_api import get_application
from flask import request, g, current_app
from ..constants import KernelType
from ..manager import get_env_value
from mosaic_utils.ai.git_repo import utils as git
from mosaic_utils.ai.k8.pod_metrics_summary import attach_default_volume, volume_custom_mount, volume_custom,attach_default_volume_mount, volume_count, volume_mount_count, attach_snapshot_volume_mount


# pylint: disable=too-many-instance-attributes, too-many-locals, too-few-public-methods
class SparkLoader:
    """Executes spark batch jobs using spark on k8s operator"""

    def __init__(
            self,
            job_name,
            git_repo,
            file_path,
            env_variables,
            jwt,
            package_list,
            cpu,
            memory,
            resource_quota,
            snapshots
    ):
        """
        Init function

        Args:
            job_name (string): name for the spark batch job
            git_repo (string): name of the git repo
            file_path (string): full path for the file to be executed
            env_variables (list): list of environment variables
            jwt (string): bearer token
            package_list (string): list of packages as string
            cpu (int): CPU cores to be assigned for spark worker
            memory (string): Memory to be assigned for spark worker
        """
        current_app.logger.debug("init function sparkloader")
        self.execution_command = None
        self.cpu = None
        self.memory = None
        self.package_install_command = None
        self.file_path = file_path
        self.job_name = job_name
        self.git_repo = git_repo
        self.env_variables = env_variables
        self.jwt = jwt
        self.package_list = package_list
        self.resource_quota = resource_quota
        self.snapshots = snapshots
        self.validate_cpu(cpu)
        self.validate_memory(memory)

    def submit_spark_app(self):
        """
        Function to submit spark application using spark on k8s operator

        Returns:
            [response]: response json from spark post call
        """
        current_app.logger.debug("start submit spark app")
        self.env_variables.pop()
        self.create_execution_command()

        # creating the necessary payload
        payload = self.create_spark_on_k8s_payload()
        current_app.logger.debug(f"current_app.config['SPARK_ON_K8S_OPERATOR_URL']:"
                                 f" {current_app.config['SPARK_ON_K8S_OPERATOR_URL']}\n"
                                 f"payload: {payload}\nAuthorization: {current_app.config['SPARK_K8S_BEARER']}")
        # post request to spark on k8s
        response = requests.post(current_app.config["SPARK_ON_K8S_OPERATOR_URL"], json=payload, headers={
            "Authorization": current_app.config["SPARK_K8S_BEARER"]},
                                 verify=False)
        current_app.logger.debug("end submit spark app")
        return response

    def create_execution_command(self):
        """
        Creates the execution command set
        """
        # creating the execution command
        current_app.logger.debug("start execution command")
        git_execution_command = self.create_git_init_command()

        notebook_convert_command = "chmod -R 777 /notebooks;" \
                                   "jupyter nbconvert --to=python {};" \
                                   "echo Done with nbconvert;".format(self.file_path)

        package_install_command = self.create_install_command()

        self.execution_command = git_execution_command + notebook_convert_command + package_install_command
        current_app.logger.debug(f"end execution command: {self.execution_command}")

    def create_git_init_command(self):
        """
        Creates the Git init command

        Returns:
            string: git clone command
        """
        current_app.logger.debug("start git init command")
        current_app.logger.debug("git repo %s", self.git_repo)
        current_app.logger.debug("email_address %s", g.user["email_address"])
        current_app.logger.debug("mosaicId %s", g.user["mosaicId"])
        current_app.logger.debug("first_name %s", g.user["first_name"])
        enabled_repo = git.get_repo(
            self.git_repo,
            g.user["email_address"],
            g.user["mosaicId"],
            g.user["first_name"]
        )
        print(enabled_repo)
        remote_url = enabled_repo['url']
        if enabled_repo['base_folder'] not in [None, ""]:
            base_folder = f"/{enabled_repo['base_folder']}/"
            base_copy_folder = f"/{enabled_repo['base_folder']}/"
        else:
            base_folder = "/"
            base_copy_folder = "/*"
        remote_branch = enabled_repo['branch']

        git_execution_command = "echo cloning into {0} for branch {1} for base folder {2} for base copy folder {3};" \
                                "git clone -b {1} {0} /git;" \
                                "echo done with clone;" \
                                "cd /git;" \
                                "echo cd into git;" \
                                "cp -r /git{3} /notebooks{2};" \
                                "echo cp /git{3} into /notebooks{2};" \
                                "cd /notebooks{2};" \
                                "echo cd /notebooks{2}".format(
            remote_url, remote_branch, base_folder, base_copy_folder
        )
        current_app.logger.debug("end git init command")
        return git_execution_command

    def create_install_command(self):
        """
        Creates pip install command

        Returns:
            string: pip install command
        """
        current_app.logger.debug("start create install command")
        if self.package_list is None:
            packages = ""
        else:
            packages = self.package_list.split()
        index_url = current_app.config["INDEX_URL"]
        init = "pip3 install -i " + index_url + " "
        target = " --target=/notebooks/pip_packages "
        package_install_command = " "
        for package in packages:
            if package.startswith("-e"):
                pass
            else:
                package_install_command += init + target + package + ";"
        current_app.logger.debug("end create install command")
        return package_install_command

    def validate_cpu(self, cpu):
        """
        Validation function for CPU cores

        Args:
            cpu (int): CPU cores
        """
        current_app.logger.debug("start validate cpu")
        # verify if CPU is 1 core or above for spark
        try:
            if isinstance(int(cpu), int):
                self.cpu = int(cpu)
        except ValueError as e:
            self.cpu = 1
        current_app.logger.debug("end validate cpu")

    def validate_memory(self, memory):
        """
        Validation function for Memory units

        Args:
            memory (string): Memory Units
        """
        current_app.logger.debug("start validate memory")
        # verify if Memory is converted correctly
        if isinstance(memory, str) and memory[-2:] == "Gi":
            self.memory = memory[:-2] + "000m"
        else:
            self.memory = "1000m"
        current_app.logger.debug("end validate memory")

    @staticmethod
    def get_memory(memory):
        try:
            temp = re.compile("([0-9\.]+)([a-zA-Z]+)")
            res = temp.match(memory).groups()
            if 'M' in res[1]:
                if float(res[0]) >= 500:
                    return str(res[0]) + "m"
                else:
                    return "500m"
            elif 'G' in res[1]:
                return str(res[0]) + "g"
        except Exception as ex:
            print(f"Memory issue: {ex}")
            return None

    def create_spark_on_k8s_payload(self):
        """
        Function to create spark on k8s payload

        Returns:
            dict: payload for spark on k8s operator
        """
        try:
            current_app.logger.debug("start create sparkk8s payload")
            # load the static json file into payload
            spark_payload_file = open("/refract/mosaic-notebooks-manager/app/notebooks_api/spawner/sparkbatch/spark_k8s_payload.json", )
            payload = json.load(spark_payload_file)

            # adding parameters to payload
            # name of spark job
            payload["metadata"]["name"] = self.job_name
            payload["metadata"]["labels"]["job-name"] = self.job_name + "-driver"
            payload["metadata"]["namespace"] = current_app.config["OPERATOR_NAMESPACE"]

            # images and spark versions
            payload["spec"]["image"] = current_app.config["PYSPARK_BATCH_IMAGE"]
            payload["spec"]["driver"]["initContainers"][0]["image"] = current_app.config["PYSPARK_INIT_IMAGE"]
            payload["spec"]["executor"]["initContainers"][0]["image"] = current_app.config["PYSPARK_INIT_IMAGE"]
            payload["spec"]["imagePullSecrets"] = [current_app.config["IMAGE_PULL_SECRETS"]]
            payload["spec"]["sparkVersion"] = current_app.config["SPARK_OPERATOR_VERSION"]
            payload["spec"]["driver"]["labels"]["version"] = current_app.config["SPARK_OPERATOR_VERSION"]
            payload["spec"]["executor"]["labels"]["version"] = current_app.config["SPARK_OPERATOR_VERSION"]
            payload["spec"]["mainApplicationFile"] = "local://" + "".join((self.file_path.strip("ipynb"), "py"))
            payload["spec"]["driver"]["serviceAccount"] = current_app.config["SPARK_OPERATOR_SA"]
            if get_env_value(self.env_variables, "custom_spark_jars_path"):
                payload["spec"]["sparkConf"]["spark.driver.extraClassPath"] = get_env_value(self.env_variables,
                                                                                            "custom_spark_jars_path")
                payload["spec"]["sparkConf"]["spark.executor.extraClassPath"] = get_env_value(self.env_variables,
                                                                                              "custom_spark_jars_path")

            # post start hook and init container commmands
            payload["spec"]["driver"]["lifecycle"]["postStart"]["exec"]["command"] = [
                "/bin/bash",
                "-c",
                "echo {} > /root/.mosaic.ai || true;".format(self.jwt)
            ]
            payload["spec"]["driver"]["initContainers"][0]["command"] = [
                "/bin/sh",
                "-c",
                self.execution_command
            ]
            payload["spec"]["executor"]["initContainers"][0]["command"] = [
                "/bin/sh",
                "-c",
                "echo INSTALLING_CUSTOM_PACKAGE;" + self.create_install_command()
            ]

            # env variables and resources
            self.env_variables.extend([
                {
                    "name": "PYTHONPATH",
                    "value": "/notebooks/pip_packages"
                },
                {
                    "name": "SPARK_MODEL_PVC",
                    "value": "/spark-model-dir"
                },
                {
                    "name": "is_job_run",
                    "value": "true"
                }
            ])

            # dropping null dictionary from env as it's not working with json payload
            self.env_variables = [i for i in self.env_variables if i['value'] not in ["", None, "None", "null"]]

            payload["spec"]["driver"]["env"] = self.env_variables
            payload["spec"]["executor"]["env"] = self.env_variables
            payload["spec"]["driver"]["cores"] = self.cpu
            payload["spec"]["driver"]["memory"] = self.memory
            payload["spec"]["executor"]["instances"] = int(get_env_value(self.env_variables, "number_of_executors")) if get_env_value(self.env_variables, "number_of_executors") else 2
            payload["spec"]["executor"]["cores"] = int(get_env_value(self.env_variables, "executor_resource_cpu")) if get_env_value(self.env_variables, "executor_resource_cpu") else 1
            payload["spec"]["executor"]["memory"] = SparkLoader.get_memory(get_env_value(self.env_variables, "executor_resource_mem")) if get_env_value(self.env_variables, "executor_resource_mem") else "2g"

            # default volume mount attachment
            current_app.logger.debug("attach default volume")
            default_volume_details = volume_custom(g.user["project_id"], current_app.config["SPARK_OPERATOR_SHARED_PVC"])[0]

            payload["spec"]["volumes"].append(default_volume_details)
            payload["spec"]["driver"]["volumeMounts"].append(volume_custom_mount(g.user["project_id"], current_app.config["MINIO_DATA_BUCKET"])[0])
            payload["spec"]["executor"]["volumeMounts"].append(volume_custom_mount(g.user["project_id"], current_app.config["MINIO_DATA_BUCKET"])[0])

            if self.snapshots["input"] != KernelType.default:
                payload["spec"]["driver"]["volumeMounts"].append(attach_snapshot_volume_mount(project_id=g.user["project_id"], snapshot_type="input", snapshot_id=self.snapshots["input"], minio_bucket=current_app.config["MINIO_DATA_BUCKET"], resource_quota_full=self.resource_quota))
                payload["spec"]["executor"]["volumeMounts"].append(attach_snapshot_volume_mount(project_id=g.user["project_id"], snapshot_type="input", snapshot_id=self.snapshots["input"], minio_bucket=current_app.config["MINIO_DATA_BUCKET"], resource_quota_full=self.resource_quota))

            if self.snapshots["output"] != KernelType.default:
                payload["spec"]["driver"]["volumeMounts"].append(attach_snapshot_volume_mount(project_id=g.user["project_id"], snapshot_type="output", snapshot_id=self.snapshots["output"], minio_bucket=current_app.config["MINIO_DATA_BUCKET"], resource_quota_full=self.resource_quota))
                payload["spec"]["executor"]["volumeMounts"].append(attach_snapshot_volume_mount(project_id=g.user["project_id"], snapshot_type="output", snapshot_id=self.snapshots["output"], minio_bucket=current_app.config["MINIO_DATA_BUCKET"], resource_quota_full=self.resource_quota))

            current_app.logger.debug("end create sparkk8s payload")
            return payload
        except Exception as ex:
            current_app.logger.info(f"Exception ex : {ex}")
