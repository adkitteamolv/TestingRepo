import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ! -*- coding: utf-8 -*-
bind = "0.0.0.0:5000"
reload = True
capture_output = True
loglevel = "info"
timeout = 1000
# errorlog = "/logs/gunicorn-error.log"
# accesslog = "/logs/gunicorn-access.log"
workers = 5
threads = 5
keepalive = 5


def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

    resource = Resource.create(attributes={"service.name": "Notebooks-api", "custom.parent_pid": os.getppid()})

    trace.set_tracer_provider(TracerProvider(resource=resource))
    span_processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://jaeger-collector.decision-designer.svc.cluster.local:4317", insecure=True)
    )
    trace.get_tracer_provider().add_span_processor(span_processor)
