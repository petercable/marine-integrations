#!/usr/bin/env python

"""
@package  ion.services.sa.instrument_management.sensor_device_worker
@author   Ian Katz
"""

#from pyon.core.exception import BadRequest, NotFound
from pyon.public import AT, RT

from ion.services.sa.resource_worker import ResourceWorker

class SensorDeviceWorker(ResourceWorker):
    """
    @brief resource management for SensorDevice resources
    """

    def _primary_object_name(self):
        return RT.SensorDevice

    def _primary_object_label(self):
        return "sensor_device"

    def link_model(self, sensor_device_id='', sensor_model_id=''):
        return self.link_resources(sensor_device_id, AT.hasModel, sensor_model_id)

    def unlink_model(self, sensor_device_id='', sensor_model_id=''):
        return self.unlink_resources(sensor_device_id, AT.hasModel, sensor_model_id)

    def find_having_model(self, sensor_model_id):
        return self._find_having(AT.hasModel, sensor_model_id)

    def find_stemming_model(self, sensor_device_id):
        return self._find_stemming(sensor_device_id, AT.hasModel, RT.SensorModel)
