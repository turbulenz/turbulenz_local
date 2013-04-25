# Copyright (c) 2011,2013 Turbulenz Limited

import logging

from pylons import response

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import GameList, get_game_by_slug
from turbulenz_local.models.gamesessionlist import GameSessionList

LOG = logging.getLogger(__name__)

class GamesController(BaseController):

    @classmethod
    @jsonify
    def list(cls):
        game_list = { }
        games = GameList.get_instance().list_all()
        for game in games:
            game_list[game.slug] = game.to_dict()
        return {'ok': True, 'data': game_list}

    @classmethod
    @jsonify
    def new(cls):
        game = GameList.get_instance().add_game()
        return {'ok': True, 'data': game.slug}

    @classmethod
    @jsonify
    def details(cls, slug):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}
        return {'ok': True, 'data': game.to_dict()}

    @classmethod
    @jsonify
    def sessions(cls):
        game_session_list = GameSessionList.get_instance()
        return {'ok': True, 'data': game_session_list.list()}
