import logging
import os
import pandas as pd
import shutil
from notebooks_api.notebook.models import db, DataSnapshot, DockerImageTag, TemplateStatus, DockerImage, Resource
from datetime import timedelta, datetime
import requests

# pylint: disable=invalid-name
log = logging.getLogger("notebooks_api.clear_snapshot")
from flask import current_app as app
from mosaic_utils.ai.headers.constants import Headers


def get_snapshot_newer_than_days(days):
    '''
    :param days: say 2 days is value we pass
    :return:
    Today is 31st Oct 2021 , it will return containers created on date 29th Oct,30 Oct and 31st Oct
    '''
    days = timedelta(hours=24 * days)
    days_ago = datetime.now() - days
    snapshot_to_keep = (db.session.query(DataSnapshot).filter(DataSnapshot.updated_on > days_ago))
    snapshots_to_keep = snapshot_to_keep.with_entities('snapshot_path', 'snapshot_input_path').all()
    snapshots_to_keep = [item for t in snapshots_to_keep for item in t]
    # convert to set as there are snapshots which are duplicate as we can use output snapshot as input
    snapshots_to_keep = set(snapshots_to_keep)
    if None in snapshots_to_keep:
        snapshots_to_keep.remove(None)
    return snapshots_to_keep


def get_all_snapshot():
    '''
    :return all snapshot list which is union of input + output
    '''
    all_snapshot = db.session.query(DataSnapshot.snapshot_path, DataSnapshot.snapshot_input_path)
    all_snapshot = [item for t in all_snapshot for item in t]
    # convert to set as there are snapshots which are duplicate as we can use output snapshot as input
    all_snapshot = set(all_snapshot)
    if None in all_snapshot:
        all_snapshot.remove(None)
    return all_snapshot


def get_elegible_snapshot():
    '''
    :return all snapshot which is elegible to delete
    '''
    try:
        log.info(f'Scheduled snapshot deletion started at {datetime.now()}')
        log.info('fetching data from db')
        df = pd.DataFrame(db.session.query(DataSnapshot.snapshot_name, DataSnapshot.project_id,
                                           DataSnapshot.created_on, DataSnapshot.snapshot_life))
        log.info(f"Total records of snapshots : {len(df)}")
        df['delta'] = (datetime.now() - df['created_on']).dt.days
        df = df[(df['snapshot_life'] <= df['delta'])]
        df = df.drop(['created_on', 'snapshot_life', 'delta'], axis=1)
        log.info(f"Total eligible snapshots for deletion: {len(df)}")
        return df.to_dict(orient='records')
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return []


def snapshot_delete_minio(snapshot):
    try:
        log.info(f"deleting snapshot {snapshot['snapshot_name']} from file")
        file = os.path.join(app.config['NOTEBOOK_MOUNT_PATH'], app.config['MINIO_BUCKET'], snapshot['project_id'],
                            f"{snapshot['project_id']}-Snapshot", snapshot['snapshot_name'])
        if os.path.exists(file):
            shutil.rmtree(file)
            log.info("file found and deleted")
        return True
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        return False


def snapshot_delete_db(snap_list):
    '''
    :delete the snapshot from db
    '''
    try:
        log.info(f"deleting {len(snap_list)} snapshots from db: {snap_list}")
        res = db.session.query(DataSnapshot).filter(DataSnapshot.snapshot_name.in_(snap_list)). \
            delete(synchronize_session=False)
        db.session.commit()
        log.info('deleted successfully')
    # pylint: disable=broad-except
    except Exception as ex:
        log.debug(ex)
        db.session.rollback()


def nas_package_log_delete():
    '''
    :delete the package log files from nas
    '''
    try:
        log.info('Started deletion of package files stored at nas')
        log.info('Getting the list of active templates present in environment')
        query_set = db.session \
            .query(DockerImageTag, TemplateStatus, DockerImage, Resource) \
            .join(DockerImage, DockerImage.id == DockerImageTag.docker_image_id) \
            .join(TemplateStatus, TemplateStatus.template_id == DockerImage.id) \
            .join(Resource, Resource.id == DockerImage.resource_id) \
            .filter(TemplateStatus.status.in_(["STARTING", "RUNNING"]))

        result_set = query_set.all()
        active_project = []

        log.info('Fetching list of project ids where templates are active')
        for _, template_status, docker_image, resource in result_set:
            project_id = template_status.project_id
            active_project.append(project_id)

        log_dir = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/" + "log"

        log.info('List of project ids present inside log directory')
        project_id_present = list(os.listdir(log_dir))

        for project_id in active_project:
            if project_id in project_id_present:
                project_id_path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/" + "log/" + project_id
                if os.path.isdir(project_id_path):
                    project_id_present.remove(project_id)

        log.info('Final litst of project directories containing inactive templates and job run files')
        log.info(project_id_present)
        for project_id in project_id_present:
            path = app.config['NOTEBOOK_MOUNT_PATH'] + app.config[
            'MINIO_DATA_BUCKET'] + "/" + "log/" + project_id
            if os.path.isdir(path):
                shutil.rmtree(path)
    except Exception as ex:
        log.debug(ex)

def snapshot_delete_from_db_minio(snapshot_name):
    snapshot_details = (db.session.query(DataSnapshot).filter(DataSnapshot.snapshot_name == snapshot_name))

    headers = {
        Headers.x_auth_userid: snapshot_details.with_entities('created_by').first()[0],
        Headers.x_auth_username: snapshot_details.with_entities('created_by').first()[0],
        Headers.x_auth_email: snapshot_details.with_entities('created_by').first()[0],
        Headers.x_project_id: snapshot_details.with_entities('project_id').first()[0],
    }
    NOTEBOOK_API_URL = app.config["NOTEBOOKS_API_SERVER_URL"]
    payload = {'snapshotname': snapshot_name}

    delete_snapshot_api = "{0}/v1/delete-snapshot".format(NOTEBOOK_API_URL)
    resp = requests.delete(delete_snapshot_api, headers=headers, params=payload)
    if resp.status_code == 200:
        print("Successfully deleted snapshot data for : {}".format(snapshot_name))
    else:
        print("Problem  deleting snapshot data for : {}".format(snapshot_name))


def remove_old_snapshot_delete_job(days):
    snapshots_to_keep = get_snapshot_newer_than_days(days)
    all_snapshot = get_all_snapshot()
    snapshot_to_be_deleted = all_snapshot - snapshots_to_keep
    for each_snapshot in snapshot_to_be_deleted:
        snapshot_delete_from_db_minio(each_snapshot)
