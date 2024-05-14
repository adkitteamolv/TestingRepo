"""empty message

Revision ID: 59015e7f66a7
Revises: d386484e9c38
Create Date: 2021-06-08 20:15:36.712504

"""
from alembic import op
import sqlalchemy as sa
from notebooks_api.utils.defaults import default_id
from notebooks_api.notebook.models import GitRepoBranches
from notebooks_api.notebook.models import GitRepo
from notebooks_api.notebook.models import GitRepoActive
from sqlalchemy.orm.session import Session
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '59015e7f66a7'
down_revision = 'd386484e9c38'
branch_labels = None
depends_on = None


def upgrade():
    try:
        # Add Branch Name in 'nb_template_status' table
        add_branch_name_in_nb_status()
        # Create 'nb_repository_branches' Table
        create_branches_table()
        # Add branch id
        add_branch_id_column()
        # Make old branch column nullable
        make_old_branch_column_nullable()
    except Exception as e:
        print(e)
        print("ALEMBIC UPGRADE FAILED FOR VALIDATORS STORY !!")



def downgrade():
    remove_branch_name_in_nb_status()
    # 'branch_id' column deletion from 'ng_repository_active'
    remove_branch_id_column()
    #'nb_git_repository_branches' table drop
    #delete_branches_table()


"""
Method Migrates the branch data in 'nb_repository_braches' table.
"""
def migrate_data_using_conn():
    try:
        connection = op.get_bind()
        session = Session(bind=connection)
        results = connection.execute(
             "SELECT repo_id, branch, project_id, created_by, created_on, last_modified_by, last_modified_on branch FROM nb_git_repository")
        all_repos = results.fetchall()
        for repo in all_repos:
            not_exist = db.session.query(GitRepoBranches) \
                            .filter(GitRepoBranches.repo_id == repo[0]) \
                            .filter(GitRepoBranches.branch_name == repo[1]) \
                            .first() is None
            if not_exist:
                payload = {
                    "repo_id": repo[0],
                    "branch_name": repo[1],
                    "default_flag": True,
                    "freeze_flag": False,
                    "share_flag": False,
                    "created_by": repo[3] if repo[3] else 'System',
                    "created_on": repo[4] if repo[4] else datetime.now(),
                    "last_modified_by": repo[5] if repo[5] else 'System',
                    "last_modified_on": repo[6] if repo[6] else datetime.now(),
                }
                git_repo_branches = GitRepoBranches(**payload)
                session.add(git_repo_branches)
                session.flush()
                session.query(GitRepoActive) \
                    .filter(GitRepoActive.repo_id == repo.repo_id) \
                    .update(dict(branch_id=git_repo_branches.branch_id))
                session.commit()
    except Exception as e:
        print(e)
        print("DATA MIGRATION FAILED !!")

"""
Delete the foreign key constraint.
"""
def delete_foreignkey_constraint():
    try:
        with op.batch_alter_table("nb_git_repository_active") as batch_op:
            batch_op.drop_constraint(
                "fk_constraint_branch_id", type_="foreignkey")
    except Exception as e:
        print(e)
        print("UNABLE TO DELETE THE CONSTRAINT !!")


"""
Delete the 'branch_id' column from 'nb_repository_active' table.
"""
def remove_branch_id_column():
    try:
        op.drop_column("nb_git_repository_active", "branch_id")
    except Exception as e:
        print(e)
        print("UNABLE TO DELETE 'branch_id' COLUMN !!")


"""
Delete 'nb_repository_branches' table.
"""
def delete_branches_table():
    try:
        op.drop_table('nb_git_repository_branches')
    except Exception as e:
        print(e)
        print("UNABLE TO DROP 'nb_git_repository_branches' TABLE !!")


"""
create 'nb_repository_branches' table.
"""
def create_branches_table():
    try:
        table_name = "nb_git_repository_branches"
        conn = op.get_bind()
        inspector = Inspector.from_engine(conn)
        tables = inspector.get_table_names()
        if table_name not in tables:
            op.create_table(
                table_name,
                sa.Column('branch_id', sa.String(length=60), nullable=False),
                sa.Column('repo_id', sa.String(length=60), nullable=False),
                sa.Column('branch_name', sa.String(length=60), nullable=False),
                sa.Column('default_flag', sa.Boolean, nullable=False),
                sa.Column('freeze_flag', sa.Boolean, nullable=False),
                sa.Column('share_flag', sa.Boolean, nullable=False),
                sa.Column('created_by', sa.String(length=60), nullable=True),
                sa.Column('created_on', sa.DateTime(), nullable=True),
                sa.Column('last_modified_by', sa.String(length=60), nullable=True),
                sa.Column('last_modified_on', sa.DateTime(), nullable=True),
                sa.ForeignKeyConstraint(["repo_id"], ["nb_git_repository.repo_id"], ondelete='CASCADE'),
                sa.PrimaryKeyConstraint('branch_id')
            )
    except Exception as e:
        print(e)
        print("UNABLE TO CREATE 'nb_git_repository_branches' TABLE !!")


"""
Add 'branch_id' column to 'nb_repository_active' table
"""
def add_branch_id_column():
    try:
        op.add_column("nb_git_repository_active", sa.Column("branch_id", sa.String(length=60)))
    except Exception as e:
        print(e)
        print("UNABLE TO ADD 'branch_id' Column to 'nb_branch_repository' TABLE !!")


"""
Add the foreign key constraint.
"""
def add_foreignkey_constraint():
    try:
        op.create_foreign_key(
            "fk_constraint_branch_id", "nb_git_repository_active",
            "nb_git_repository_branches", ["branch_id"], ["branch_id"])
    except Exception as e:
        print(e)
        print("UNABLE TO ADD THE CONSTRAINT !!")


"""
Create backup of tables
"""
def create_backup_table():
    try:
        connection = op.get_bind()
        session = Session(bind=op.get_bind())
        count = session.query(func.count(GitRepo.repo_id)).scalar()
        print("The count is : "+str(count))
        if count>0:
            table_name = "nb_git_repository_bkBeforeValidatorStory" + str(datetime.utcnow().strftime('%Y%m%d%H%M%S'))
            query = f"CREATE TABLE {table_name} AS SELECT * FROM nb_git_repository"
            op.execute(query)
        session.flush()
        session.commit()
        return True
    except Exception as e:
        print(e)
        print("UNABLE TO CREATE BACKUP TABLE !!")
        return False

"""
Delete the 'branch' column from 'nb_repository' table.
"""
def remove_branch_column_from_nbrepository():
    try:
        op.drop_column("nb_git_repository", "branch")
    except Exception as e:
        print(e)
        print("UNABLE TO REMOVE branch COLUMN FROM nb_git_repository TABLE !!")


"""
Add and Populate the 'branch' column from 'nb_repository' table.
"""
def populate_branch_column_from_nbrepository():
    try:
        op.add_column("nb_git_repository", sa.Column("branch", sa.String(length=60)))
        connection = op.get_bind()
        session = Session(bind=connection)
        branch_list = session.query(GitRepoBranches).filter(GitRepoBranches.default_flag == True).all()
        for branch in branch_list:
            query = text("UPDATE nb_git_repository SET branch=:branch_name WHERE repo_id=:repo_id").bindparams(
                branch_name=branch.branch_name,
                repo_id=branch.repo_id
            )
            op.execute(query)
        session.flush()
        session.commit()
    except Exception as e:
        print(e)
        print("UNABLE TO POPULATE branch COLUMN FROM nb_git_repository TABLE !!")


"""
Add Branch Name in nb_status
"""
def add_branch_name_in_nb_status():
    try:
        op.add_column("nb_template_status", sa.Column('branch_name', sa.String(length=60)))
    except Exception as e:
        print(e)
        print("Unable to add 'branch_name' in 'nb_template_status' table !!")


"""
Remove Branch Name from nb_template_status
"""
def remove_branch_name_in_nb_status():
    try:
        op.drop_column("nb_template_status", "branch_name")
    except Exception as e:
        print(e)
        print("Unable to remove 'branch_name' from 'nb_template_status' table !!")

"""
Make old branch column nullable
"""
def make_old_branch_column_nullable():
    try:
        op.alter_column('nb_git_repository', 'branch',
                        existing_type=sa.VARCHAR(60),
                        nullable=True)
    except Exception as e:
        print(e)
        print("Error while making 'branch' column nullable")