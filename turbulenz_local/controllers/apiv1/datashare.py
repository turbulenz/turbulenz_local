# Copyright (c) 2012 Turbulenz Limited

# pylint: disable=F0401
from pylons import request
from paste.deploy.converters import asbool
# pylint: enable=F0401

from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import jsonify, postonly, secure_post, secure_get

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.models.apiv1.datashare import DataShareList, CompareAndSetInvalidToken
from turbulenz_local.models.userlist import get_current_user

from turbulenz_local.models.gamelist import get_game_by_slug

from turbulenz_local.lib.exceptions import BadRequest, NotFound

class DatashareController(BaseController):
    """ DataShareController consists of all the datashare methods
    """

    datashare_service = ServiceStatus.check_status_decorator('datashare')
    game_session_list = GameSessionList.get_instance()

    # Testing only - Not available on the Gamesite
    @classmethod
    @postonly
    @datashare_service
    @jsonify
    def remove_all(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            raise NotFound('No game with slug %s' % slug)
        DataShareList.get(game).remove_all()
        return {'ok': True }

    @classmethod
    @postonly
    @datashare_service
    @jsonify
    def create(cls, slug):
        game = get_game_by_slug(slug)
        datashare = DataShareList.get(game).create_datashare(get_current_user())
        return {'ok': True, 'data': {'datashare': datashare.summary_dict()}}

    @classmethod
    @postonly
    @datashare_service
    @jsonify
    def join(cls, slug, datashare_id):
        game = get_game_by_slug(slug)
        datashare = DataShareList.get(game).get(datashare_id)
        datashare.join(get_current_user())
        return {'ok': True, 'data': {'users': datashare.users}}

    @classmethod
    @postonly
    @datashare_service
    @jsonify
    def leave(cls, slug, datashare_id):
        game = get_game_by_slug(slug)
        DataShareList.get(game).leave_datashare(get_current_user(), datashare_id)
        return {'ok': True}

    @classmethod
    @datashare_service
    @secure_post
    def set_properties(cls, slug, datashare_id, params=None):
        game = get_game_by_slug(slug)
        datashare = DataShareList.get(game).get(datashare_id)
        if 'joinable' in params:
            try:
                joinable = asbool(params['joinable'])
            except ValueError:
                raise BadRequest('Joinable must be a boolean value')
            datashare.set_joinable(get_current_user(), joinable)
        return {'ok': True}

    @classmethod
    @datashare_service
    @jsonify
    def find(cls, slug):
        game = get_game_by_slug(slug)
        username = request.params.get('username')
        datashares = DataShareList.get(game).find(get_current_user(), username_to_find=username)
        return {'ok': True, 'data': {'datashares': [datashare.summary_dict() for datashare in datashares]}}

    @classmethod
    @datashare_service
    @secure_get
    def read(cls, datashare_id, params=None):
        session = cls._get_gamesession(params)
        datashare = DataShareList.get(session.game).get(datashare_id)
        datashare_keys = datashare.get_keys(session.user)
        return {'ok': True, 'data': {'keys': datashare_keys}}

    @classmethod
    @datashare_service
    @secure_get
    def read_key(cls, datashare_id, key, params=None):
        session = cls._get_gamesession(params)
        datashare = DataShareList.get(session.game).get(datashare_id)
        datashare_key = datashare.get(session.user, key)
        return {'ok': True, 'data': datashare_key}

    @classmethod
    @datashare_service
    @secure_post
    def set_key(cls, datashare_id, key, params=None):
        session = cls._get_gamesession(params)
        datashare = DataShareList.get(session.game).get(datashare_id)
        value = params.get('value')
        new_token = datashare.set(session.user, key, value)
        return {'ok': True, 'data': {'token': new_token}}

    @classmethod
    @datashare_service
    @secure_post
    def compare_and_set_key(cls, datashare_id, key, params=None):
        session = cls._get_gamesession(params)
        datashare = DataShareList.get(session.game).get(datashare_id)

        value = params.get('value')
        token = params.get('token')
        try:
            new_token = datashare.compare_and_set(session.user, key, value, token)
            return {'ok': True, 'data': {'wasSet': True, 'token': new_token}}
        except CompareAndSetInvalidToken:
            return {'ok': True, 'data': {'wasSet': False}}
