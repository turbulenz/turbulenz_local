# Copyright (c) 2011-2013 Turbulenz Limited

# pylint: disable=F0401
from pylons import response, request
# pylint: enable=F0401

from turbulenz_local.decorators import jsonify#, postonly
from turbulenz_local.lib.servicestatus import ServiceStatus, InvalidStatus
from turbulenz_local.controllers import BaseController

class ServicestatusController(BaseController):

    @classmethod
    @jsonify
    def read_list(cls):
        try:
            return {'ok': True, 'data': {
                'services': ServiceStatus.get_status_list(),
                'pollInterval': ServiceStatus.get_poll_interval()
            }}
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing service name'}

    @classmethod
    def read(cls, slug):
        return cls.read_list()

    @classmethod
    #@postonly
    @jsonify
    def set(cls, service_name):
        try:
            ServiceStatus.set_status(service_name, request.params)
            return {'ok': True}
        except InvalidStatus:
            response.status_int = 400
            msg = 'Missing or invalid service status arguments. Must be running, discardRequests or description'
            return {'ok': False, 'msg': msg}

    @classmethod
    #@postonly
    @jsonify
    def set_poll_interval(cls):
        try:
            poll_interval = float(request.params['value'])
            if poll_interval <= 0:
                raise ValueError
            ServiceStatus.set_poll_interval(poll_interval)
            return {'ok': True}
        except (KeyError, ValueError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Polling interval must be a positive value'}
