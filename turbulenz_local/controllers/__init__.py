# Copyright (c) 2010-2013 Turbulenz Limited
"""The base Controller API

Provides the BaseController class for subclassing.
"""
from pylons.controllers import WSGIController
from pylons.templating import render_jinja2 as render

from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.lib.exceptions import InvalidGameSession

class BaseController(WSGIController):

    def __call__(self, environ, start_response):
        """Invoke the Controller"""
        # WSGIController.__call__ dispatches to the Controller method
        # the request is routed to. This routing information is
        # available in environ['pylons.routes_dict']
        return WSGIController.__call__(self, environ, start_response)


    game_session_list = GameSessionList.get_instance()

    @classmethod
    def _get_gamesession(cls, params):
        """ Get the user id and project version id for this game session """
        try:
            session = cls.game_session_list.get_session(params['gameSessionId'])
            if session is None:
                raise InvalidGameSession()
            return session
        except (KeyError, TypeError):
            raise InvalidGameSession()
