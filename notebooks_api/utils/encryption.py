#! -*- coding: utf-8 -*-
""" This module contains Encryption Classes  """
import ast
import json
import os

import logging
from uuid import uuid4
import requests
import six
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from ..constants import PasswordStore

LOGGER = logging.getLogger("notebooks_api")


class DBFernetEncrypter:
    """
    Class implementing DB Encryption Operations
    """

    def __init__(self, table_name=None):
        self.table_name = table_name
        fernet_key = self.__secret_key(os.environ["ENC_PASSWORD"])
        self.fernet = Fernet(fernet_key)

    @staticmethod
    def __secret_key(key):
        """

        :param key:
        :return:
        """
        if isinstance(key, six.string_types):
            key = key.encode()
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(key)
        engine_key = digest.finalize()
        fernet_engine = FernetEngine()
        fernet_engine._initialize_engine(engine_key)  # pylint: disable=protected-access
        return fernet_engine.secret_key

    def store(self, password):
        """
        :param password:
        :return:
        """
        return self.encrypt(password)

    def retrieve(self, _id, coerce_dtype=False):
        """
        :param _id:
        :param coerce_dtype:
        :return:
        """
        return self.decrypt(_id, coerce_dtype)

    def encrypt(self, message):
        """
        :param message: message To be encrypted
        :return:
        """
        if message is None:
            msg = None
        else:
            if not isinstance(message, str):
                message = json.dumps(message)
            msg = self.fernet.encrypt(bytes(message, "utf-8")).decode("utf-8")
        return msg

    def decrypt(self, enctypted_message, coerce_dtype=False):
        """
        Message to be decrypted
        :param coerce_dtype: Try to convert str to dict
        :param enctypted_message:
        :return:
        """
        if enctypted_message is None:
            return None

        res = self.fernet.decrypt(bytes(enctypted_message, "utf-8")).decode("utf-8")
        if coerce_dtype and isinstance(res, str):
            # convert string to python object
            try:
                res = json.loads(res)
            except json.decoder.JSONDecodeError:
                res = ast.literal_eval(res)

        return res


class VaultEncrypter:
    """
    Class implementing Vault Backend APIs
    """

    def __init__(self, prefix_path):
        """
        :param prefix_path: Prefix path of kv store
        :param base_url: vault url
        :param token:
        """
        self._prefix_path = prefix_path
        self._vault_url = os.environ["VAULT_URL"]
        self._headers = {"X-Vault-Token": os.environ["VAULT_TOKEN"]}

    @property
    def url(self) -> str:
        """
        :return: URL
        """
        return f"{self._vault_url}{self._prefix_path}"

    def retrieve(self, key, coerce_dtype=False):
        """
        :param coerce_dtype:
        :param key_error: raise or ignore
        :param key:
        :return:
        """
        if key is None:
            return None

        LOGGER.debug("Entering retrieve, key %s %s", key, coerce_dtype)
        url = f"{self.url}/{key}"
        LOGGER.debug("url... %s", url)

        resp = requests.get(url=url, headers=self._headers)
        try:
            resp.raise_for_status()
            resp = resp.json()
            value = resp["data"]["value"]

        except requests.exceptions.HTTPError as ex:
            if resp.status_code != 404:
                LOGGER.exception(ex)
                raise KeyError("Key Not Present in Vault")
            LOGGER.debug("Key Not Present. Return None")
            value = None
        LOGGER.debug("Exiting retrieve")
        return value

    def store(self, value=None, key=None):
        """
        :param key:
        :param value:
        :return:
        """
        if value is None:
            return None
        if key is None:
            key = str(uuid4())
        LOGGER.debug("Entering store, key %s, value %s", key, value)
        url = f"{self.url}/{key}"
        payload = {"value": value}
        LOGGER.debug("url... %s", url)
        LOGGER.debug("payload... %s", payload)
        result = requests.post(url=url, json=payload, headers=self._headers)
        result.raise_for_status()
        LOGGER.debug("Exiting store")
        return key

    def delete(self, key):
        """
        :param key:
        :param value:
        :return:
        """
        if key is None:
            return
        LOGGER.debug("Entering Delete, key %s", key)
        url = f"{self.url}/{key}"
        LOGGER.debug("url... %s", url)
        result = requests.delete(url=url, headers=self._headers)
        try:
            result.raise_for_status()
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception(ex)
        LOGGER.debug("Exiting delete")


class PasswordStoreFactory:
    """
    Factory Class to Invoke Vault Encrypter or DBFernet Enctypter
    """
    def __init__(self, password_store, table_name):
        """
        :param password_store: VAULT or DB
        :param table_name: Table name used to store in Vault
        """
        _clients_map = {
            PasswordStore.VAULT: VaultEncrypter,
            PasswordStore.DB: DBFernetEncrypter
        }
        try:
            self.client = _clients_map[password_store](table_name)
        except KeyError as ex:
            logging.exception("key error in Password store factory %s", ex)
            raise NotImplementedError("PASSWORD_STORE {} has not been implemented.".
                                      format(password_store))

    def store(self, value):
        """
        Store value and return key or encrypted value
        :param value: value to be stored/encrypted
        :return: key or encrypted value
        """
        return self.client.store(value)

    def retrieve(self, _id, coerce_dtype=False):
        """
        Return decrypted value from key or encrypted value
        :param _id: key or encrypted value
        :param coerce_dtype: Should convert to python dtype or not
        :return: decrypted value
        """
        return self.client.retrieve(_id, coerce_dtype)
