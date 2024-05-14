#! -*- coding: utf-8 -*-

""" MOSAIC Notebook Json template class """

import time
import random


def create_mosaicnotebook(notebook_name, notebook_id):
    """
    Creates mosic notebook json
    :param notebook_name: name of the notebook
    :param notebook_id: id of the notebook
    :return: notebook json
    """
    mosaicnotebook = MOSAICNotebook(notebook_name, notebook_id)
    #notebook_json = json.dumps(moasicnotebook.__dict__)
    return mosaicnotebook.__dict__


# pylint: disable=useless-object-inheritance
class MOSAICNotebook(object):
    """Mosaic Notebook"""
    def __init__(self, notebook_name, notebook_id):
        """
        Json format for MOSAIC notebook
        :param notebook_name:
        :param notebook_id:
        """
        self.paragraphs = []
        paragraph = {
            'user': "",
            'config': {},
            'settings': {
                'params': {},
                'forms': {}},
            'apps': [],
            'jobName': self.generate_job_name(),
            'id': self.generate_paragraph_id(),
            'dateCreated': time.strftime("%b %d, %Y %I:%M:%S %p"),
            'status': "READY",
            'progressUpdateIntervalMs': 500}
        self.paragraphs.append(paragraph)
        self.name = notebook_name
        # pylint: disable=invalid-name
        self.id = notebook_id
        self.angularObjects = {}
        self.config = {}
        self.info = {}

    def generate_paragraph_id(self):
        """
        Generates paragaph id for empty paragraph
        :return: paragraph_id
        """
        date = time.strftime("%Y%m%d-%I%M%S")
        para_id = "{}_{}".format(date, self.__hash__())
        return para_id

    # pylint: disable=no-self-use
    def generate_job_name(self):
        """
        Generate job name for paragraph
        :return: job_name
        """
        current_time = round(time.time() * 1000)
        job_name = "paragraph_{}_{}".format(
            str(current_time), random.randint(
                100000000, 999999999))
        return job_name
