#! -*- coding: utf:8 -*-
"""Module for pypi data"""
import logging

from .models import Package, PackageVersion, db
from .pypi_index import save_package_data


# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.pypi")


def load_data():
    """ master records for pypi packages """

    # define packages
    packages = (
        {
            "name": "XgBoost",
            "version": "0.71",

        },
        {
            "name": "PyMC3",
            "version": "3.4.1",

        },
        {
            "name": "category_encoders",
            "version": "1.2.6",

        },
        {
            "name": "vertica_python",
            "version": "0.7.3",

        },
        {
            "name": "sklearn",
            "version": "0.19.1",

        },
        {
            "name": "IPython",
            "version": "6.3.1",

        },
        {
            "name": "networkx",
            "version": "2.1",

        },
        {
            "name": "ggplot",
            "version": "0.11.5",

        },
        {
            "name": "keras",
            "version": "2.2.0",

        },
        {
            "name": "pyramid",
            "version": "1.9.2",

        },
        {
            "name": "pandas",
            "version": "0.23.1",

        },
        {
            "name": "requests",
            "version": "2.19.1",

        },
        {
            "name": "sqlalchemy-teradata",
            "version": "0.1.0",

        },
        {
            "name": "teradata",
            "version": "15.10.0.21",

        },
        {
            "name": "scipy",
            "version": "1.1.0",

        },
        {
            "name": "matplotlib",
            "version": "2.2.2",

        },
        {
            "name": "seaborn",
            "version": "0.7.1",

        },
        {
            "name": "h2o",
            "version": "3.20.0.8",

        },
        {
            "name": "bokeh",
            "version": "0.13.0",

        },
        {
            "name": "xlsxwriter",
            "version": "1.1.1",

        },
        {
            "name": "PyPDF2",
            "version": "1.26.0",

        },
        {
            "name": "fbprophet",
            "version": "0.3",

        }
    )


    # delete old records
    Package.query.delete()
    PackageVersion.query.delete()
    try:
        #Create new table
        db.session.commit()
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()

    for package in packages:
        save_package_data(package, "python")

    packages = (
        {
            "name": "dplyR",
            "version": "0.71",

        },
        {
            "name": "car",
            "version": "3.4.1",
        }
    )
    
    for package in packages:
        save_package_data(package, "r")
    


    packages = (
        {
            "name": "dplyR",
            "version": "0.71",

        },
        {
            "name": "car",
            "version": "3.4.1",

        }
    )

    for package in packages:
        save_package_data(package, "conda-r")

    packages = (
        {
            "name": "PyPDF2",
            "version": "1.26.0",

        },
        {
            "name": "fbprophet",
            "version": "0.3",
        }
    )

    for package in packages:
        save_package_data(package, "conda")
