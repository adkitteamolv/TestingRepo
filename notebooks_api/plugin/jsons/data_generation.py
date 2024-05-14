input_parameter_json = {
    "fields": [
        {
            "Configurations": [
                {
                    "field_id": "data_source",
                    "field_label": "Data Source",
                    "field_mandatory": "yes",
                    "field_value": "Local Data Files",
                    "field_options": [
                        "Local Data Files",
                        "Refract Datasets"
                    ],
                    "field_type": "select",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "reference_data_path",
                    "field_info": "Select input data",
                    "field_label": "Input dataset or local data file path",
                    "field_mandatory": "yes",
                    "field_name": "",
                    "field_options": "",
                    "field_placeholder": "Input dataset or local data file path",
                    "field_type": "selectapi",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": "",
                    "secured": "false"
                },
                {
                    "field_id": "sample_size",
                    "field_label": "Input sample size",
                    "field_mandatory": "yes",
                    "field_value": "200",
                    "field_options": "",
                    "field_type": "text",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "filter_condition",
                    "field_label": "Filter Condition",
                    "field_mandatory": "no",
                    "field_placeholder": "for ex: where col_1='some_value' order by col_2",
                    "field_info": "Applicable for RDBMS datasets, write syntactically correct where condition to be used in select query",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "text",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "numeric_columns",
                    "field_label": "Enter Numerical Column Names",
                    "field_mandatory": "no",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "multipleselect",
                    "grid_value": 12,
                    "refract_source": "",
                    "field_info": "Numeric Columns"
                },
                {
                    "field_id": "categorical_columns",
                    "field_label": "Enter Categorical Column Names",
                    "field_mandatory": "no",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "multipleselect",
                    "grid_value": 12,
                    "refract_source": "",
                    "field_info": "Categorical Columns"
                },
                {
                    "field_id": "set_conditional",
                    "field_label": "Generate Data Using Conditional Columns",
                    "field_mandatory": "no",
                    "field_value": "False",
                    "field_options": [
                        "True",
                        "False"
                    ],
                    "field_type": "select",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "conditional_columns",
                    "field_label": "Select the Conditional column names",
                    "field_mandatory": "no",
                    "field_value": "",
                    "field_options": "",
                    "field_type": "multipleselect",
                    "grid_value": 12,
                    "refract_source": "",
                    "field_info": "Conditional Columns"
                },
                {
                    "field_id": "epoch",
                    "field_label": "Epoch",
                    "field_mandatory": "yes",
                    "field_options": "",
                    "field_type": "text",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "learning_rate",
                    "field_label": "Learning Rate",
                    "field_mandatory": "yes",
                    "field_options": "",
                    "field_type": "text",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": ""
                },
                {
                    "field_id": "default_container_size",
                    "field_label": "Default Container Size",
                    "field_mandatory": "yes",
                    "field_options": "",
                    "field_type": "selectapi",
                    "field_value": "",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        }
    ]
}
