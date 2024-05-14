#! -*- coding: utf-8 -*-
"""kombu utils module"""
import kombu
# pylint: disable=import-error
from socketio import KombuManager


# pylint: disable=too-few-public-methods
class CustomKombuManager(KombuManager):
    """Custome kombu manager"""

    def _queue(self):
        queue_name = 'flask-socketio.flask-socketio'
        return kombu.Queue(
            queue_name,
            self._exchange(),
            durable=False,
            queue_arguments={'x-expires': 300000}
        )
