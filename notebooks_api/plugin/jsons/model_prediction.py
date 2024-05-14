input_parameter_json = {
    "fields": [
        {
            "basic_details": [
                {
                    "field_id": "default_container_size",
                    "field_label": "Default container size",
                    "field_mandatory": "yes",
                    "field_name": "",
                    "field_options": "",
                    "field_placeholder": "container size",
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
            "input_dataset": [
                {
                    "field_id": "reference_data_path",
                    "field_info": "Select file from data section",
                    "field_label": "Input File",
                    "field_mandatory": "yes",
                    "field_name": "",
                    "field_options": "",
                    "field_placeholder": "Input file path here",
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
            "write_strategy": [
                {
                    "field_id": "write_strategy",
                    "field_label": "Write strategy",
                    "field_mandatory": "yes",
                    "field_value": "",
                    "field_options": [
                        "New table",
                        "New prediction table"
                    ],
                    "field_type": "select",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        },
        {
            "model_details": [
                {
                    "field_id": "model_id",
                    "field_label": "Model Name",
                    "field_mandatory": "yes",
                    "field_name": "Model Name",
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
                    "field_name": "Version NO",
                    "field_placeholder": "Version NO",
                    "field_type": "selectapi",
                    "field_value": "",
                    "field_docker_image_url": "",
                    "field_kernel_type": "",
                    "grid_value": 12,
                    "refract_source": ""
                }
            ]
        }
    ]
}
