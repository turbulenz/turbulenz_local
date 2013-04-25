# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for actions pertaining to a specified game
"""
import logging

# pylint: disable=F0401
from pylons import response
# pylint: enable=F0401

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import get_game_by_slug

LOG = logging.getLogger(__name__)

class PlayController(BaseController):
    """
    Controller class for the 'play' branch of the URL tree.
    """

    @classmethod
    @jsonify
    def versions(cls, slug):
        """
        Display a list of all play pages in the game's folder.
        """
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        versions = game.get_versions()
        if versions:
            versions.sort(key=lambda s: (s['title'], s))
        else:
            versions = ''

        return {
            'ok': True,
            'data': {
                'game': game.title,
                'versions': versions
            }
        }
