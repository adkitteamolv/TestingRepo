input_parameter_json = {
    "fields": [
        {
            "basic_details": [
                {
                    "field_id": "drift_type",
                    "field_label": "Drift type",
                    "field_mandatory": "yes",
                    "field_type": "hidden",
                    "field_value": "feature_drift",
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
            "advanced_settings": {
                "categorical_features": [{
                    "field_id": "categorical_columns",
                    "field_label": "Feature list",
                    "field_mandatory": "no",
                    "field_info": "Enter auto as default categorical_columns",
                    "field_placeholder": "Feature List",
                    "field_type": "multipleselect",
                    "field_value": "",
                    "grid_value": 4,
                    "secured": "false"
                },
                    {
                        "field_id": "categorical_features_stattest",
                        "field_label": "Test",
                        "field_mandatory": "yes",
                        "field_options": [
                            "auto",
                            "chisquare",
                            "fisher_exact",
                            "g_test",
                            "hellinger",
                            "jensenshannon",
                            "kl_div",
                            "psi",
                            "TVD"
                        ],
                        "field_type": "select",
                        "field_value": "auto",
                        "grid_value": 4
                    },
                    {
                        "field_id": "categorical_features_threshold",
                        "field_label": "Threshold",
                        "field_mandatory": "yes",
                        "field_placeholder": "Threshold",
                        "field_type": "text",
                        "field_value": "auto",
                        "grid_value": 4,
                        "secured": "false"
                    }
                ],
                "numerical_features": [{
                    "field_id": "numeric_columns",
                    "field_label": "Feature list",
                    "field_mandatory": "no",
                    "field_placeholder": "List",
                    "field_info": "Enter auto as default numeric_columns",
                    "field_type": "multipleselect",
                    "field_value": "",
                    "grid_value": 4,
                    "secured": "false"
                },
                    {
                        "field_id": "numerical_features_stattest",
                        "field_label": "Test",
                        "field_mandatory": "yes",
                        "field_options": [
                            "auto",
                            "anderson",
                            "cramer_von_mises",
                            "ed",
                            "es",
                            "hellinger",
                            "jensenshannon",
                            "kl_div",
                            "ks",
                            "mannw",
                            "psi",
                            "t_test",
                            "wasserstein",
                            "z"
                        ],
                        "field_type": "select",
                        "field_value": "auto",
                        "grid_value": 4
                    },
                    {
                        "field_id": "numerical_features_threshold",
                        "field_label": "Threshold",
                        "field_mandatory": "yes",
                        "field_placeholder": "Threshold",
                        "field_type": "text",
                        "field_value": "auto",
                        "grid_value": 4,
                        "secured": "false"
                    }
                ]
            }
        }
    ]
}
