# -*- coding: utf-8 -*-
"""pytest module"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from notebooks_api import create_app


@pytest.fixture(scope="session")
def client():
    """Method to create client"""
    app = create_app()
    # pylint: disable=redefined-outer-name
    client = app.test_client()
    yield client


def create_db_engine():
    """Method to create db engine"""
    return create_engine("sqlite:////tmp/sqlite.db")


def create_db_session(db_engine):
    """create db session method"""
    session_maker = sessionmaker(bind=db_engine)
    return session_maker()


@pytest.fixture()
def session():
    """create db session"""
    db_engine = create_db_engine()
    yield create_db_session(db_engine)


def append_url_prefix(url):
    """Method to append url prefix"""
    app = create_app()
    return "{}/{}".format(app.config["URL_PREFIX"], url)

def console_backend_url():
    """Method to append url prefix"""
    app = create_app()
    return app.config["CONSOLE_BACKEND_URL"]

@pytest.fixture()
def headers():
    headers = {"X-Project-ID": "1"}
    return headers