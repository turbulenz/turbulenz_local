# Copyright (c) 2011-2013 Turbulenz Limited

import logging

# pylint: disable=F0401
from pylons import response
# pylint: enable=F0401

from turbulenz_local.decorators import secure_get, secure_post
from turbulenz_local.lib.servicestatus import ServiceStatus

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.models.apiv1.userdata import UserData, UserDataKeyError


LOG = logging.getLogger(__name__)

def _set_json_headers(headers):
    headers['Pragma'] = 'no-cache'
    headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

class UserDataGameNotFound(Exception):
    pass

class UserdataController(BaseController):
    """ UserdataController consists of all the Userdata methods
    """

    game_session_list = GameSessionList.get_instance()

    userdata_service = ServiceStatus.check_status_decorator('userdata')

    @classmethod
    @userdata_service
    @secure_get
    def read_keys(cls, params=None):
        _set_json_headers(response.headers)
        userdata = UserData(cls._get_gamesession(params))

        return {'ok': True, 'keys': userdata.get_keys()}

    @classmethod
    @userdata_service
    @secure_get
    def exists(cls, key, params=None):
        _set_json_headers(response.headers)
        userdata = UserData(cls._get_gamesession(params))

        return {'ok': True, 'exists': userdata.exists(key)}

    @classmethod
    @userdata_service
    @secure_get
    def read(cls, key, params=None):
        _set_json_headers(response.headers)
        userdata = UserData(cls._get_gamesession(params))

        try:
            value = userdata.get(key)
        except UserDataKeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Key does not exist'}
        else:
            return {'ok': True,  'value': value}

    @classmethod
    @userdata_service
    @secure_post
    def set(cls, key, params=None):
        userdata = UserData(cls._get_gamesession(params))

        value = params['value']

        userdata.set(key, value)
        return {'ok': True}

    @classmethod
    @userdata_service
    @secure_post
    def remove(cls, key, params=None):
        userdata = UserData(cls._get_gamesession(params))

        try:
            userdata.remove(key)
        except UserDataKeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Key does not exist'}
        else:
            return {'ok': True}

    @classmethod
    @userdata_service
    @secure_post
    def remove_all(cls, params=None):
        userdata = UserData(cls._get_gamesession(params))

        userdata.remove_all()
        return {'ok': True}
