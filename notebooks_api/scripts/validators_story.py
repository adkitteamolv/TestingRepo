#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from notebooks_api.utils.defaults import default_id
from sqlalchemy import and_, or_
from sqlalchemy import func

application = Flask(__name__)

def get_config():
    """ get config method """
    #base_path = "../configs/local.cfg"
    base_path = "../configs/test.cfg"
    application.config.from_pyfile(base_path)
    return application.config

def create_db_config(application):
    """creates database configuration"""
    configuration = get_config()
    application.config['SQLALCHEMY_DATABASE_URI'] = configuration['SQLALCHEMY_DATABASE_URI']
    application.config['SQLALCHEMY_ECHO'] = False
    application.config['SQLALCHEMY_POOL_SIZE'] = None
    application.config['SQLALCHEMY_POOL_TIMEOUT'] = None
    application.config['SQLALCHEMY_POOL_RECYCLE'] = 60
    application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    application.config['SQLALCHEMY_MAX_OVERFLOW'] = configuration['SQLALCHEMY_MAX_OVERFLOW']
    return application

application = create_db_config(application)

# pylint: disable=invalid-name
db = SQLAlchemy(application)

class RepoAccessCategory:
    """
    Access Type constants used for git repo
    """
    name = "access_category"
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"

# pylint: disable=too-few-public-methods
class GitRepo(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository"
    created_by = db.Column(db.String(100), default="System")
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified_by = db.Column(db.String(100), default="System")
    last_modified_on = db.Column(db.DateTime, default=datetime.utcnow)
    repo_id = db.Column(db.String(60), primary_key=True, default=default_id)
    project_id = db.Column(db.String(60))
    repo_url = db.Column(db.String(255))
    username = db.Column(db.String(60), nullable=True)
    password = db.Column('password', db.Text)
    branch = db.Column(db.String(60))
    access_category = db.Column(db.Enum(RepoAccessCategory.PRIVATE, RepoAccessCategory.PUBLIC))

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class GitRepoBranches(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository_branches"
    branch_id = db.Column(db.String(60), primary_key=True, default=default_id)
    repo_id = db.Column(
        db.String(60), db.ForeignKey(
            GitRepo.repo_id, ondelete="CASCADE"), nullable=False)
    branch_name = db.Column(db.String(60), nullable=False)
    default_flag = db.Column(db.Boolean, default=False)
    freeze_flag = db.Column(db.Boolean, default=False)
    share_flag = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(100), default="System")
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified_by = db.Column(db.String(100), default=lambda: "System")
    last_modified_on = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        """ Dict representation """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class GitRepoActive(db.Model):
    """
    Model for user Git Details
    """
    __tablename__ = "nb_git_repository_active"
    id = db.Column(db.String(60), primary_key=True, default=default_id)
    repo_id = db.Column(
        db.String(60), db.ForeignKey(
            GitRepo.repo_id, ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    branch_id = db.Column(db.String(60), nullable=True)


def execute(operation):
    """ This function performs data migrations for validators story"""
    print("\n## Inside Execute : "+str(operation))
    if operation:
        if operation.upper()=='UPGRADE':
            run_upgrade_script()
        elif operation.upper()=='DOWNGRADE':
            run_downgrade_script()
        else:
            print("Invalid Operation, please specify correct operation (upgrade/downgrade)!")
    else:
        print("Operation seems to be empty!")


def run_upgrade_script():
    """Upgrade Script"""
    print("RUNNING UPGRADE SCRIPT")
    migrate_data()
    print("DONE !!")

def run_downgrade_script():
    """Downgrade Script"""
    raise Exception("Data Migration not needed for downgrade!")


def migrate_data():
    """Migrate Data"""
    try:
        repos = db.session.query(GitRepo).filter(and_(GitRepo.branch.isnot(None), func.trim(GitRepo.branch) != "")).all()
        print("Total Rows : "+str(len(repos)))
        for repo in repos:
            try:
                repo_dict = repo.as_dict()
                not_exist = db.session.query(GitRepoBranches) \
                                .filter(and_(GitRepoBranches.repo_id == repo_dict["repo_id"], GitRepoBranches.default_flag == True)) \
                                .first() is None
                if not_exist:
                    record_update_cnt = db.session.query(GitRepoBranches) \
                        .filter(GitRepoBranches.repo_id == repo_dict["repo_id"]) \
                        .filter(GitRepoBranches.branch_name == repo_dict["branch"]) \
                        .update(dict(default_flag=True))
                    if record_update_cnt == 0:
                        payload = {
                            "repo_id": repo_dict["repo_id"],
                            "branch_name": repo_dict["branch"],
                            "default_flag": True,
                            "freeze_flag": False,
                            "share_flag": False,
                            "created_by": repo_dict["created_by"] if repo_dict["created_by"] else 'System',
                            "created_on": repo_dict["created_on"] if repo_dict["created_on"] else datetime.now(),
                            "last_modified_by": repo_dict["last_modified_by"] if repo_dict[
                                "last_modified_by"] else 'System',
                            "last_modified_on": repo_dict["last_modified_on"] if repo_dict[
                                "last_modified_on"] else datetime.now(),
                        }
                        git_repo_branches = GitRepoBranches(**payload)
                        db.session.add(git_repo_branches)
                        db.session.flush()
                        update_active_repo(repo.repo_id, git_repo_branches.branch_id)
                    elif record_update_cnt > 0:
                        updated_record = db.session.query(GitRepoBranches) \
                            .filter(GitRepoBranches.repo_id == repo_dict["repo_id"]) \
                            .filter(GitRepoBranches.branch_name == repo_dict["branch"]).first()
                        if updated_record:
                            update_active_repo(updated_record.repo_id, updated_record.branch_id)
                    db.session.flush()
                    db.session.commit()
            except Exception as e:
                print(e)
                pass
    except Exception as e:
        print(e)
        print("DATA MIGRATION FAILED !!")

def update_active_repo(repo_id, branch_id):
    db.session.query(GitRepoActive) \
        .filter(and_(GitRepoActive.repo_id == repo_id,
                     or_(GitRepoActive.branch_id.is_(None), func.trim(GitRepoActive.branch_id) == ""))) \
        .update(dict(branch_id=branch_id), synchronize_session=False)

if __name__ == "__main__":
    try:
        operation = sys.argv[1]
        execute(operation)
    except IndexError as ex:
        print("Please specify operation(upgrade/downgrade) as an argument!")
    except Exception as ex:
        print(ex)
        print(ex.args[0])

