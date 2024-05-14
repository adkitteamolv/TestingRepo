"""
DML - Encryption/Decryption of Password in nb_git_repository
Revision ID: 82435a37de09
Revises: 3ab985242bea
Create Date: 2021-03-22 16:04:23.078028

"""
from alembic import op
import os
import sqlalchemy as sa
from sqlalchemy.orm.session import Session
from cryptography.fernet import Fernet
from typing import List
import six
from cryptography.hazmat.backends import default_backend
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine
from cryptography.hazmat.primitives import hashes
from notebooks_api.notebook.models import db, GitRepo

# revision identifiers, used by Alembic.
revision = '82435a37de09'
down_revision = '3ab985242bea'
branch_labels = None
depends_on = None


# def secret_key(key):
#     if isinstance(key, six.string_types):
#         key = key.encode()
#     digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
#     digest.update(key)
#     engine_key = digest.finalize()
#     f = FernetEngine()
#     f._initialize_engine(engine_key)
#
#     return f.secret_key
#
#
# password = os.environ["ENC_PASSWORD"]
# fernet_key = secret_key(password)
# f = Fernet(fernet_key)
#
#
# class GitRepoNonEncrypted(GitRepo):
#     """
#     Overide password parameter
#     """
#     __tablename__ = "nb_git_repository"
#     __table_args__ = {'extend_existing': True}
#     password = db.Column(sa.Text, nullable=False)
#
#
# def encrypt(message):
#     """
#     :param message: message To be encrypted
#     :return:
#     """
#     return f.encrypt(bytes(message, "utf-8")).decode("utf-8")
#
#
# def decrypt(enctypted_message):
#     """
#     Message to be decrypted
#     :param enctypted_message:
#     :return:
#     """
#     return f.decrypt(bytes(enctypted_message, "utf-8")).decode("utf-8")


def upgrade():
    pass
    # pass
    # session = Session(bind=op.get_bind())
    # repo_lists: List[GitRepoNonEncrypted] = session.query(GitRepoNonEncrypted).all()
    # for repo in repo_lists:
    #     repo.password = encrypt(repo.password)
    #
    # session.commit()


def downgrade():
    pass
    # session = Session(bind=op.get_bind())
    # repo_lists: List[GitRepoNonEncrypted] = session.query(GitRepoNonEncrypted).all()
    #
    # for repo in repo_lists:
    #     repo.password = decrypt(repo.password)
    #
    # session.commit()
