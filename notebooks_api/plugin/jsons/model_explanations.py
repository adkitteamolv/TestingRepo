input_parameter_json = {
    "fields": [
        {
                "basic_details": [
                    {
                        "field_id": "drift_type",
                        "field_label": "Drift type",
                        "field_mandatory": "yes",
                        "field_type": "hidden",
                        "field_value": "MODEL_EXPLANATIONS",
                        "refract_source": ""
                    },
                    {
                        "field_id": "data_type",
                        "field_label": "Data Type",
                        "field_mandatory": "yes",
                        "field_value": "Tabular",
                        "field_options": [
                            "Tabular"
                        ],
                        "field_type": "select",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "problem_type",
                        "field_label": "Problem type",
                        "field_mandatory": "yes",
                        "field_value": "Binary Classification",
                        "field_options": [
                            "Binary Classification",
                            "Multiclass Classification",
                            "Regression"
                        ],
                        "field_type": "select",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "default_container_size",
                        "field_label": "Default container size",
                        "field_mandatory": "yes",
                        "field_name": "Select container size",
                        "field_options": "",
                        "field_placeholder": "Select container size",
                        "field_type": "selectapi",
                        "field_value": "",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "data_source",
                        "field_label": "Data source",
                        "field_mandatory": "yes",
                        "field_value": "Local data files",
                        "field_options": [
                            "Local data files"
                        ],
                        "field_type": "select",
                        "grid_value": 12,
                        "refract_source": ""
                    }
                    
                ]
                ,
                "model_details" : [
                    {
                        "field_id": "model_id",
                        "field_label": "Model Name",
                        "field_mandatory": "yes",
                        "field_name": "",
                        "field_placeholder": "Model Name",
                        "field_type": "selectapi",
                        "field_value": "",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "version_id",
                        "field_label": "Version NO",
                        "field_mandatory": "yes",
                        "field_name": "",
                        "field_placeholder": "Version NO",
                        "field_type": "selectapi",
                        "field_value": "",
                        "field_docker_image_url":"",
                        "field_kernel_type" :"",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "model_flavour",
                        "field_label": "Model Flavour",
                        "field_mandatory": "yes",
                        "field_value": "sklearn",
                        "field_options": [
                            "keras",
                            "sklearn",
                            "pytorch",
                            "tensorflow",
                            "pyspark",
                            "spacy",
                            "r",
                            "pmml",
                            "ensemble",
                            "sas",
                            "xgboost"
                        ],
                        "field_type": "select",
                        "grid_value": 12,
                        "refract_source": ""
                    }
                ]
            },
            {
                "current_test_dataset": [
                    {
                        "field_id": "current_data_path",
                        "field_info": "Provide only test dataset with target label ",
                        "field_label": "Test Data",
                        "field_mandatory": "yes",
                        "field_name": "",
                        "field_options": "",
                        "field_placeholder": "Test data path...",
                        "field_type": "selectapi",
                        "field_value": "",
                        "grid_value": 12,
                        "refract_source": "",
                        "secured": "false"
                    },
                    {
                        "field_id": "target_column",
                        "field_label": "Target Column",
                        "field_mandatory": "yes",
                        "field_placeholder": "Target column",
                        "field_info": "Provide the name of Target column inside test dataset provided",
                        "field_value": "",
                        "field_options": "",
                        "field_type": "text",
                        "grid_value": 12,
                        "refract_source": ""
                    },
                    {
                        "field_id": "target_class_names",
                        "field_label": "Target names",
                        "field_mandatory": "no",
                        "field_placeholder": "For classification problems only : class names",
                        "field_info": "This field used only for classification problems and provide class names in the order of 0,1,2 etc ..",
                        "field_value": "",
                        "field_options": "",
                        "field_type": "text",
                        "grid_value": 12,
                        "refract_source": ""
                    }
                ]
            }
        ]
}
