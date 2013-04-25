# Copyright (c) 2011,2013 Turbulenz Limited
"""
Controller class for the asset lists
"""
import logging

from pylons import config, response

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.game import GamePathError, GamePathNotFoundError

LOG = logging.getLogger(__name__)


class ListController(BaseController):

    request_path = config.get('list.staticmax_url')

    @classmethod
    @jsonify
    def overview(cls, slug):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        return {
            'ok': True,
            'data': {
                'slug': game.slug,
                'staticFilePrefix' : 'staticmax',
                'mappingTable': game.mapping_table
            }
        }

    @classmethod
    @jsonify
    def assets(cls, slug, path=''):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        try:
            asset_list = game.get_asset_list(cls.request_path, path)
        except (GamePathError, GamePathNotFoundError) as e:
            response.status_int = 404
            return {'ok': False, 'msg': str(e)}
        else:
            return {
                'ok': True,
                'data': {
                    'items': [i.as_dict() for i in asset_list],
                    'path': path.strip('/'),
                    'mappingTable': game.has_mapping_table
                }
            }

    @classmethod
    @jsonify
    def files(cls, slug, path=''):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        try:
            asset_list = game.get_static_files(game.path, cls.request_path, path)
        except GamePathNotFoundError as e:
            response.status_int = 404
            return {'ok': False, 'msg': str(e)}
        else:
            return {
                'ok': True,
                'data': {
                    'items': [ i.as_dict() for i in asset_list ],
                    'path': path.strip('/'),
                    'mappingTable': game.has_mapping_table
                }
            }
