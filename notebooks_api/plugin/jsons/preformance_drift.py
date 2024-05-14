input_parameter_json = {
    "fields": [
        {
            "basic_details": [
                {
                    "field_id": "drift_type",
                    "field_label": "Drift Type",
                    "field_mandatory": "yes",
                    "field_type": "hidden",
                    "field_value": "model_performance_drift",
                    "refract_source": ""
                },
                {
                    "field_id": "data_type",
                    "field_label": "Data Type",
                    "field_mandatory": "yes",
                    "field_options": [
                        "Tabular"
                    ],
                    "field_type": "select",
                    "field_value": "Tabular",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "problem_type",
                    "field_label": "Problem type",
                    "field_mandatory": "yes",
                    "field_options": [
                        "Binary Classification",
                        "Multiclass Classification",
                        "Regression"
                    ],
                    "field_type": "select",
                    "field_value": "Binary Classification",
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
                        "Local data files",
                        "Refract datasets"
                    ],
                    "field_type": "select",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        },
        {
            "reference_dataset": [
                {
                    "field_id": "reference_data_path",
                    "field_info": "Select file from data section",
                    "field_label": "Reference data path",
                    "field_mandatory": "yes",
                    "field_name": "",
                    "field_options": "",
                    "field_placeholder": "reference path...",
                    "field_type": "selectapi",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": "",
                    "secured": "false"
                },
                {
                    "field_id": "reference_filter_condition",
                    "field_label": "Filter Condition",
                    "field_mandatory": "no",
                    "field_placeholder": "for ex: where col_1='some_value' order by col_2",
                    "field_info": "Applicable for RDBMS datasets, write syntactically correct where condition to be used in select query",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "text",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        },
        {
            "current_dataset": [
                {
                    "field_id": "current_data_path",
                    "field_info": "Select file from data section",
                    "field_label": "Current data path",
                    "field_mandatory": "yes",
                    "field_name": "",
                    "field_options": "",
                    "field_placeholder": "current path...",
                    "field_type": "selectapi",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": "",
                    "secured": "false"
                },
                {
                    "field_id": "current_filter_condition",
                    "field_label": "Filter Condition",
                    "field_mandatory": "no",
                    "field_placeholder": "for ex: where col_1='some_value' order by col_2",
                    "field_info": "Applicable for RDBMS datasets, write syntactically correct where condition to be used in select query",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "text",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        },
        {
            "data_configuration": [
                {
                    "field_id": "prediction_col_name",
                    "field_label": "Prediction column",
                    "field_mandatory": "no",
                    "field_placeholder": "Prediction column",
                    "field_type": "multipleselect",
                    "field_value": "",
                    "grid_value": 6,
                    "secured": "false"
                },
                {
                    "field_id": "target_col_name",
                    "field_label": "Target column",
                    "field_mandatory": "no",
                    "field_placeholder": "Target column",
                    "field_type": "multipleselect",
                    "field_value": "",
                    "grid_value": 6,
                    "secured": "false"
                }
            ]
        }
    ]
}
