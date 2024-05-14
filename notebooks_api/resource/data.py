#! -*- coding: utf-8
"""Resource data module"""

import logging

from .models import Resource, db
from .constants import ResourceStatus


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.resource")


def load_data():
    """ master records for resource """
    # define resources
    resources = {
        "Micro": ("100m", "256Mi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 10MB - 50MB"),
        "Small": ("1", "2Gi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 400MB - 500MB"),
        "Medium": ("2", "4Gi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 800MB - 1GB"),
        "Large": ("2", "8Gi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 1.8GB - 2GB"),
        "XLarge": ("4", "16Gi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 4GB - 5GB"),
        "2XLarge": ("8", "32Gi", "cpu", ResourceStatus.ENABLED, "recommended for data sizes 8GB - 10GB"),
        "GPU-NVIDIA-Small": ("1", "16Gi", "nvidia", ResourceStatus.ENABLED, ""),
        "GPU-NVIDIA-Medium": ("2", "16Gi", "nvidia", ResourceStatus.ENABLED, ""),
        "GPU-NVIDIA-Large": ("4", "32Gi", "nvidia", ResourceStatus.ENABLED, ""),
        "GPU-AMD-Small": ("1", "16Gi", "amd", ResourceStatus.ENABLED, ""),
        "GPU-AMD-Medium": ("2", "16Gi", "amd", ResourceStatus.ENABLED, ""),
        "GPU-AMD-Large": ("4", "32Gi", "amd", ResourceStatus.ENABLED, "")
    }

    try:
        # create resource
        for name, resource in resources.items():
            record = (
                db.session.query(Resource).filter(
                    Resource.name == name).first())
            if record is None:
                resource = Resource(
                    name=name,
                    cpu=resource[0],
                    mem=resource[1],
                    extra=resource[2],
                    description=resource[4],
                    created_by="system",
                    updated_by="system")
                db.session.add(resource)
                db.session.flush()
            else:
                # update data
                setattr(record, "name", name)
                setattr(record, "cpu", resource[0])
                setattr(record, "mem", resource[1])
                setattr(record, "extra", resource[2])
                setattr(record, "status", resource[3])
                setattr(record, "description", resource[4])
                db.session.add(record)
                db.session.flush()

        # save to db
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
