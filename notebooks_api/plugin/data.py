#! -*- coding: utf-8
"""Resource data module"""

import logging
from flask import current_app as app
from .models import CustomPlugins, PluginDockerImage, db
from .jsons import feature_drift, prediction_drift, preformance_drift, label_drift, data_quality, data_generation, \
    model_explanations, feature_store, model_prediction

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.plugin")


def load_data():
    """ master records for plugin """
    # define resources
    load_data_image()
    plugins = {
        "FEATURE_DRIFT": (
            "ML Observability", "FEATURE_DRIFT", "Node for Feature Drift", "PRE_BUILD", "FEATURE_DRIFT", "enabled",
            "FEATURE_DRIFT.svg", "48px", "48px", "#fff", "", "", "", "json", feature_drift.input_parameter_json,
            "", "python", "/custom_plugin/drift", "model", "python run.py", ["Drift Score"],'RefractMLMonitor','1.2.0',False),
        "PREDICTION_DRIFT": (
            "ML Observability", "PREDICTION_DRIFT", "Node for Prediction Drift", "PRE_BUILD", "PREDICTION_DRIFT",
            "enabled",
            "PREDICTION_DRIFT.svg", "48px", "48px", "#fff", "", "", "", "json", prediction_drift.input_parameter_json,
            "", "python", "/custom_plugin/drift", "model", "python run.py", ["Drift Score"],'RefractMLMonitor','1.2.0',False),
        "PERFORMANCE_DRIFT": (
            "ML Observability", "PERFORMANCE_DRIFT", "Node for Performance Drift", "PRE_BUILD", "PERFORMANCE_DRIFT",
            "enabled",
            "PERFORMANCE_DRIFT.svg", "48px", "48px", "#fff", "", "", "", "json", preformance_drift.input_parameter_json,
            "", "python", "/custom_plugin/drift", "model", "python run.py",
            ["Accuracy", "Precision", "Recall", "F1 Score"],'RefractMLMonitor','1.2.0',False),
        "LABEL_DRIFT": (
            "ML Observability", "LABEL_DRIFT", "Node for Label Drift", "PRE_BUILD", "LABEL_DRIFT", "enabled",
            "LABEL_DRIFT.svg", "48px", "48px", "#fff", "", "", "", "json", label_drift.input_parameter_json,
            "", "python", "/custom_plugin/drift", "model", "python run.py", ["Drift Score"],'RefractMLMonitor','1.2.0',False),
        "DATA_QUALITY": (
            "DATA TESTING", "DATA_QUALITY", "Node for data quality", "PRE_BUILD", "DATA_QUALITY", "enabled",
            "DATA_QUALITY.svg", "48px", "48px", "#fff", "", "", "", "json", data_quality.input_parameter_json,
            "", "python", "/custom_plugin/data_quality", "model", "python app.py", ["Completeness", "Consistency"],'RefractDQ','1.3.8',False),
        "DATA_GENERATION": (
            "DATA GENERATION", "DATA_GENERATION", "Node to generate more sample data", "PRE_BUILD", "DATA_GENERATION",
            "enabled", "DATA_GENERATION.svg", "48px", "48px", "#fff", "", "", "", "json",
            data_generation.input_parameter_json, "", "python", "/custom_plugin/data_generation", "data",
            "python run.py", ["Score"],'refract-data-gen','1.0.0',False),
        "MODEL_EXPLANATIONS": (
            "ML Observability", "MODEL_EXPLANATIONS", "Node for XAI", "PRE_BUILD", "MODEL_EXPLANATIONS", "enabled",
            "XAI.svg", "48px", "48px", "#fff", "", "", "", "json", model_explanations.input_parameter_json,
            "", "python", "/custom_plugin/xai", "model", "python app.py", [],'RefractXAI','1.3.8',True),
        "FEATURE_STORE": (
            "Feature Store", "FEATURE_STORE", "Plugin to materialize feature store", "PRE_BUILD", "FEATURE_STORE", "enabled",
            "DEFAULT.svg", "48px", "48px", "#fff", "", "", "", "json", feature_store.input_parameter_json,
            "", "feast", "/custom_plugin/feature_store", "notebook", "python app.py", [],'feature-store-refract','1.0.30',False),
        "BATCH_PREDICTION": (
            "Model Prediction", "BATCH_PREDICTION", "To calculate model Predictions", "PRE_BUILD", "BATCH_PREDICTION",
            "enabled", "DEFAULT.svg", "48px", "48px", "#fff", "", "", "", "json", model_prediction.input_parameter_json,
            "", "python", "/custom_plugin/refract_serving/batch_serving", "notebook", "python app.py", [], 'refract-serving',
            '0.0.12', True),
    }

    try:
        # create resource
        for name, plugin_data in plugins.items():
            record = (
                db.session.query(CustomPlugins).filter(
                    CustomPlugins.name == name).first())
            if record is None:
                plugin = CustomPlugins(category=plugin_data[0],
                                       name=plugin_data[1],
                                       description=plugin_data[2],
                                       plugin_type=plugin_data[3],
                                       type=plugin_data[4],
                                       status=plugin_data[5],
                                       icon=plugin_data[6],
                                       width=plugin_data[7],
                                       height=plugin_data[8],
                                       color=plugin_data[9],
                                       thumbnail=plugin_data[10],
                                       multiInputNode=plugin_data[11],
                                       nodeBackgroundColor=plugin_data[12],
                                       input_form_type=plugin_data[13],
                                       input_parameter_json=plugin_data[14],
                                       input_parameter_file_name=plugin_data[15],
                                       base_image_type=plugin_data[16],
                                       plugin_code_source=plugin_data[17],
                                       valid_sections=plugin_data[18],
                                       execution_command=plugin_data[19],
                                       alert_parameters=plugin_data[20],
                                       package_name=plugin_data[21],
                                       package_version=plugin_data[22],
                                       model_required=plugin_data[23],
                                       created_by="system",
                                       updated_by="system",
                                       )
                db.session.add(plugin)
                db.session.flush()
            elif record and not all([
                record.category==plugin_data[0],
                record.name==plugin_data[1],
                record.description==plugin_data[2],
                record.plugin_type==plugin_data[3],
                record.type==plugin_data[4],
                record.status==plugin_data[5],
                record.icon==plugin_data[6],
                record.width==plugin_data[7],
                record.height==plugin_data[8],
                record.color==plugin_data[9],
                record.thumbnail==plugin_data[10],
                record.multiInputNode==plugin_data[11],
                record.nodeBackgroundColor==plugin_data[12],
                record.input_form_type==plugin_data[13],
                record.input_parameter_json==plugin_data[14],
                record.input_parameter_file_name==plugin_data[15],
                record.base_image_type==plugin_data[16],
                record.plugin_code_source==plugin_data[17],
                record.valid_sections==plugin_data[18],
                record.execution_command==plugin_data[19],
                record.alert_parameters==plugin_data[20],
                record.package_name==plugin_data[21],
                record.package_version==plugin_data[22],
                record.model_required==plugin_data[23],
            ]):
                record.category=plugin_data[0]
                record.name=plugin_data[1]
                record.description=plugin_data[2]
                record.plugin_type=plugin_data[3]
                record.type=plugin_data[4]
                record.status=plugin_data[5]
                record.icon=plugin_data[6]
                record.width=plugin_data[7]
                record.height=plugin_data[8]
                record.color=plugin_data[9]
                record.thumbnail=plugin_data[10]
                record.multiInputNode=plugin_data[11]
                record.nodeBackgroundColor=plugin_data[12]
                record.input_form_type=plugin_data[13]
                record.input_parameter_json=plugin_data[14]
                record.input_parameter_file_name=plugin_data[15]
                record.base_image_type=plugin_data[16]
                record.plugin_code_source=plugin_data[17]
                record.valid_sections=plugin_data[18]
                record.execution_command=plugin_data[19]
                record.alert_parameters=plugin_data[20]
                record.package_name=plugin_data[21]
                record.package_version=plugin_data[22]
                record.model_required=plugin_data[23]
                log.info(f"Updated {record.name} DB configurations")

        # save to db
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()


def load_data_image():
    """ master records for plugin """
    # define resources
    docker_images = {
        "python": ("python", "{}{}/docker-builder-plugin:2024-05-20-06-57-45".format(app.config["GIT_REGISTRY"],
                                                        app.config["REGISTRY_DIR_PATH_PYTHON_PLUGIN_IMAGE"])),
        "feast": ("feast", "{}{}/plugin:feast_1.0.1".format(app.config["GIT_REGISTRY"],
                                                            app.config["REGISTRY_DIR_PATH_PYTHON_PLUGIN_IMAGE"]))
    }

    try:
        # create resource
        for name, image in docker_images.items():
            record = (
                db.session.query(PluginDockerImage).filter(
                    PluginDockerImage.base_image_type == name).first())
            if record is None:
                resource = PluginDockerImage(
                    base_image_type=name,
                    docker_url=image[1])
                db.session.add(resource)
                db.session.flush()
            elif not record.docker_url == image[1]:
                record.docker_url = image[1]

        # save to db
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
