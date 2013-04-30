# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for actions pertaining to a specified game
"""
import logging

# pylint: disable=F0401
from pylons import request, response
# pylint: enable=F0401

from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import jsonify

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.userlist import get_current_user
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.models.apiv1.store import StoreList
from turbulenz_local.models.apiv1.datashare import DataShareList
from turbulenz_local.models.apiv1.gamenotifications import GameNotificationKeysList

LOG = logging.getLogger(__name__)


class GamesController(BaseController):
    """
    Controller class for the 'play' branch of the URL tree.
    """

    gamesession_service = ServiceStatus.check_status_decorator('gameSessions')

    @classmethod
    @gamesession_service
    @jsonify
    def create_session(cls, slug, mode=None):
        """
        Returns application settings for local.
        """
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        if 'canvas' == mode:
            prefix = 'play/%s/' % slug
        else:
            prefix = ''
        mapping_table = 'mapping_table.json'
        if game:
            mapping_table = str(game.mapping_table)

        user = get_current_user()
        game_session_list = GameSessionList.get_instance()
        game_session_id = game_session_list.create_session(user, game)

        StoreList.reset()
        DataShareList.reset()
        GameNotificationKeysList.reset()

        return {
            'ok': True,
            'mappingTable':
            {
                'mappingTableURL': prefix + mapping_table,
                'mappingTablePrefix': prefix + 'staticmax/',
                'assetPrefix': 'missing/'
            },
            'gameSessionId': game_session_id
        }

    @classmethod
    @gamesession_service
    @jsonify
    def destroy_session(cls):
        """
        Ends a session started with create_session.
        """
        try:
            game_session_id = request.params['gameSessionId']
            user = get_current_user()
            game_session_list = GameSessionList.get_instance()
            session = game_session_list.get_session(game_session_id)
            if session is not None:
                if session.user.username == user.username:
                    game_session_list.remove_session(game_session_id)
                    return {'ok': True}
                else:
                    response.status_int = 400
                    return {'ok': False, 'msg': "Attempted to end a session that is not owned by you"}
            else:
                response.status_int = 400
                return {'ok': False, 'msg': 'No session with ID "%s" exists' % game_session_id}

        except TypeError, e:
            response.status_int = 400
            return {'ok': False, 'msg': 'Something is missing: %s' % str(e)}
        except KeyError, e:
            response.status_int = 400
            return {'ok': False, 'msg': 'Something is missing: %s' % str(e)}
