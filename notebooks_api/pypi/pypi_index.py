#! -*- coding: utf-8 -*-
"""Pypi index module"""
import datetime
import logging
from flask import current_app as app
from .manager import get_packages
from .models import db, Package, PackageVersion

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api")


#pylint: disable=R0912
def create_index(refresh=False, language='python'):
    """ Create ES index """
    if language == 'r':
        alias_name = app.config["CRAN_ALIAS_NAME"]
        packages = get_packages(language)
    elif language == 'conda':
        alias_name = app.config["CONDA_PYTHON_ALIAS_NAME"]
        packages = get_packages(language)
    elif language == 'conda-r':
        alias_name = app.config["CONDA_R_ALIAS_NAME"]
        packages = get_packages(language)
    else:
        alias_name = app.config["PYPI_ALIAS_NAME"]
        packages = get_packages()
    index_name = ('index_' + datetime.datetime.now().strftime("%Y%M%d%H%M%S"))

    package_list = []

    # pylint: disable=unexpected-keyword-arg
    for package in packages:
        if "href=" not in package:
            save_package_data(package, language)
            package_list.append(package['name'])

    if len(package_list) > 0:
        delete_missing_packages(package_list, language)


def save_package_data(package, language):
    """
    Save plugin user data
    """
    # save data
    try:
        #db.create_all()


        result = 0
        result = db.session.query(Package) \
            .filter(Package.package_name == package['name']) \
            .filter(Package.language_version == package.get('python_version', None)) \
            .filter(Package.language == language).count()


        if result == 0:
            package_data = Package(
                package_name=package['name'],
                package_version=package.get('version', None),
                language=language,
                language_version=package.get('python_version', None)
            )
            
            db.session.add(package_data)

        if package.get('version') is not None:                 
            package_data = db.session.query(Package) \
                .filter(Package.package_name == package['name']) \
                .filter(Package.language_version == package.get('python_version', None)) \
                .filter(Package.language == language).all()
            add_package_version(package_data[0].id, package)
            
        #print(package_data)
        db.session.commit()
        return ""
    # pylint: disable=broad-except
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return ""

def add_package_version(id, package):

    version_result = 0
    version_result = db.session.query(PackageVersion) \
        .filter(PackageVersion.package_id == id) \
        .filter(PackageVersion.version == package.get('version', None)).count()

    if version_result == 0:
        package_version_data = PackageVersion(
            version=package.get('version', None),
            package_id=id
        )
        db.session.add(package_version_data)                    


def search_package(package_name, language='python'):
    try:    
        result = db.session.query(Package) \
            .filter(Package.package_name.ilike(package_name+"%")) \
            .filter(Package.language == language).limit(100).all()
    
        matching_packages = []

        for row in result:
            matching_packages.append(row.package_name)
        
        db.session.commit()

        return matching_packages
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return []

def search_package_version(package_name, py_version, language='python'):
    try:    
        result = 0
        result = db.session.query(Package) \
            .filter(Package.package_name == package_name) \
            .filter(Package.language == language).limit(1).all()
        
        if py_version is None:
            result = db.session.query(Package) \
                .filter(Package.package_name == package_name) \
                .filter(Package.language == language).limit(1).all()
            
        else:
            result = db.session.query(Package) \
                .filter(Package.package_name == package_name) \
                .filter(Package.language_version == py_version) \
                .filter(Package.language == language).limit(1).all()
            
            
        version_list = []

        if result != 0:
            versions = db.session.query(PackageVersion) \
                .filter(PackageVersion.package_id == result[0].id).all()

            for row in versions:
                version_list.append(row.version)
        
        db.session.commit()

        return version_list
    except Exception as e:
        log.exception(e)
        db.session.rollback()
        return []

def delete_missing_packages(package_list, language):
    try:            
        # Get the list of package names for the given language
        result = db.session.query(Package.package_name) \
            .filter(Package.language == language).all()
        package_names = [row.package_name for row in result]

        # Find the missing packages
        missing_packages = set(package_names) - set(package_list)

        # Delete the missing packages
        for missing_package in missing_packages:
            num_deleted = db.session.query(Package) \
                .filter(Package.package_name == missing_package, Package.language == language) \
                .delete()
            if num_deleted != 1:
                log.warning(f"Expected to delete 1 row for package {missing_package} in language {language}, but deleted {num_deleted} rows")

        db.session.commit()

    except Exception as e:
        log.exception(e)
        db.session.rollback()

    
#alter table nb_pypi_package add column package_name varchar;
#alter table nb_pypi_package add column package_version varchar;
#alter table nb_pypi_package add column language varchar;
#alter table nb_pypi_package add column language_version varchar;
#alter table nb_pypi_package drop column name;

#CREATE TABLE  nb_pypi_package (   id varchar(60),
#    package_name varchar, 
#    package_version varchar, 
#    language varchar, 
#    language_version varchar)
