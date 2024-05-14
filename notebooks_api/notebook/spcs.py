#! -*- coding: utf-8 -*-
"""SCS related queries and connections"""
from snowflake.snowpark.session import Session


class SnowflakeConnection(object):
    """Snowflake connection manager."""

    def __init__(self, connection_params):
        """Initialize the session as None."""
        self.connection_params = connection_params
        self.session = None

    def __enter__(self):
        """Initialize the session when called using with statement."""
        self.session = Session.builder.configs(self.connection_params).create()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the session on exit."""
        self.session.close()


class SpcsQuery:
    """SCS snowsql queries"""
    create_service = """
CREATE SERVICE {service_name}
IN COMPUTE POOL {compute_pool}
FROM SPECIFICATION $$
{spec}
$$;
    """
    describe_service = "DESCRIBE SERVICE {service_name};"
    list_compute_pool = "SHOW COMPUTE POOLS;"
    list_database = "SHOW DATABASES;"
    list_schema = "SHOW SCHEMAS;"
    list_stage = "SHOW STAGES;"
    service_status = "SELECT SYSTEM$GET_SERVICE_STATUS('{service_name}');"
    stop_servie = "DROP SERVICE {service_name};"


class SpcsConstants:
    """SCS snowsql queries"""
    create_service = "create_service"
    cpu_family = ['STANDARD_1', 'STANDARD_2', 'STANDARD_5', 'HIGH_MEMORY_1', 'HIGH_MEMORY_2',
                  'HIGH_MEMORY_5', 'HIGH_MEMORY_7']
    list_database = "list_database"
    get_uri = "get_uri"
    gpu = "gpu"
    gpu_family = ['GPU_3', 'GPU_5', 'GPU_7', 'GPU_10']
    list_compute_pool = "list_compute_pool"
    list_schema = "list_schema"
    list_stage = "list_stage"
    mountable_stage = "INTERNAL NO CSE"
    provisioning = "Endpoints provisioning in progress"
    ready = "READY"
    service_stage_yaml = "service_with_stage.yaml"
    service_yaml = "service.yaml"
    snowflake = "SNOWFLAKE"
    stop_service = "stop_service"