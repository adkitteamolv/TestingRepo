from marshmallow import Schema, fields, validate, validates_schema, ValidationError

class BaseTemplateSchema(Schema):
    tags = fields.List(fields.Str(), required=True)
    kernel_type = fields.Str(required=True)
    docker_url = fields.Str(required=True)
    container_uid = fields.Str(required=True)

    @validates_schema
    def validate_tags(self, data, **kwargs):
        if 'tags' in data and not any(tag.startswith('type') for tag in data['tags']):
            raise ValidationError("Type key should be present in tags in the payload")

        if 'kernel_type' in data and data['kernel_type'] in ['rstudio', 'python', 'spark_distributed', 'spark']:
            if 'tags' in data and not any(tag.startswith('version') for tag in data['tags']):
                raise ValidationError("Version key should be present in tags in the payload")


def validate_create_base_template(payload):
    schema = BaseTemplateSchema()
    errors = schema.validate(payload)
    if errors:
        raise ValidationError(errors)


