# Copyright (c) 2012-2013 Turbulenz Limited

from logging import getLogger
from simplejson import loads

# pylint: disable=F0401
from pylons import response, request, config
# pylint: enable=F0401

from turbulenz_local.decorators import secure_post, jsonify
from turbulenz_local.lib.servicestatus import ServiceStatus

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.models.apiv1.gameprofile import GameProfile
from turbulenz_local.models.gamelist import get_game_by_slug


LOG = getLogger(__name__)


class GameprofileController(BaseController):
    """ GameprofileController consists of all the GameProfile methods
    """

    game_session_list = GameSessionList.get_instance()

    game_profile_service = ServiceStatus.check_status_decorator('gameProfile')

    max_size = int(config.get('gameprofile.max_size', 1024))
    max_list_length = int(config.get('gameprofile.max_list_length', 64))

    @classmethod
    def __get_profile(cls, params):
        """ Get the user and game for this game session """
        try:
            session = cls.game_session_list.get_session(params['gameSessionId'])
            return GameProfile(session.user, session.game)
        except (KeyError, TypeError):
            return None

    @classmethod
    @game_profile_service
    @jsonify
    def read(cls):
        params = request.params
        try:
            usernames = loads(params['usernames'])
        except (KeyError, TypeError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing username information'}
        except ValueError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Badly formated username list'}

        if not isinstance(usernames, list):
            response.status_int = 400
            return {'ok': False, 'msg': '\'usernames\' must be a list'}
        max_list_length = cls.max_list_length
        if len(usernames) > max_list_length:
            response.status_int = 413
            return {'ok': False, 'msg': 'Cannot request game profiles ' \
                                        'for more than %d users at once' % max_list_length}

        profile = cls.__get_profile(params)
        if profile is None:
            response.status_int = 400
            return {'ok': False, 'msg': 'No session with that ID exists'}

        return {'ok': True, 'data': profile.get(usernames)}

    @classmethod
    @game_profile_service
    @secure_post
    def set(cls, params=None):
        try:
            value = str(params['value'])
        except (KeyError, TypeError):
            response.status_int = 400
            return {'ok': False, 'msg': 'No profile value provided to set'}
        except ValueError:
            response.status_int = 400
            return {'ok': False, 'msg': '\'value\' should not contain non-ascii characters'}

        value_length = len(value)
        if value_length > cls.max_size:
            response.status_int = 413
            return {'ok': False, 'msg': 'Value length should not exceed %d' % cls.max_size}

        profile = cls.__get_profile(params)
        if profile is None:
            response.status_int = 400
            return {'ok': False, 'msg': 'No session with that ID exists'}

        profile.set(value)
        return {'ok': True}

    @classmethod
    @game_profile_service
    @secure_post
    def remove(cls, params=None):
        profile = cls.__get_profile(params)
        if profile is None:
            response.status_int = 400
            return {'ok': False, 'msg': 'No session with that ID exists'}

        profile.remove()
        return {'ok': True}

    # testing only
    @classmethod
    @game_profile_service
    @jsonify
    def remove_all(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 400
            return {'ok': False, 'msg': 'No game with that slug exists'}

        GameProfile.remove_all(game)
        return {'ok': True}
