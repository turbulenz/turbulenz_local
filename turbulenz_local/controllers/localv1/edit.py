# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for actions pertaining to a specified game
"""

import os
import logging

from os.path import join as path_join, normpath as norm_path

from pylons import request, response

from turbulenz_local.decorators import jsonify
from turbulenz_local.tools import get_absolute_path, slugify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import GameList, get_game_by_slug
from turbulenz_local.models.game import GamePathNotFoundError, GamePathError, GameNotFoundError, GameError

LOG = logging.getLogger(__name__)

def _details(game):
    return {
        'ok': True,
        'data': {
            'status': {
                'directory': game.status(['slug', 'path']),
                'path': game.status('path'),
                'definition': game.status(['title', 'slug'])
            },
            'isCorrect': {
                'path': game.path.is_correct(),
                'slug': game.slug.is_correct(),

            },
            'isTemporary': game.is_temporary,
            'path': game.path,
            'gameRoot': norm_path(game.get_games_root()),
            'title': game.title,
            'title_logo': game.title_logo.image_path,
            'slug': game.slug,
            'pluginMain': game.plugin_main,
            'canvasMain': game.canvas_main,
            'mappingTable': game.mapping_table,
            'deployFiles': game.deploy_files.getlist(),
            'deployable': game.can_deploy,
            'engine_version': game.engine_version,
            'is_multiplayer': game.is_multiplayer,
            'aspect_ratio': game.aspect_ratio

        }
    }

class EditController(BaseController):
    """
    Controller class for the 'edit' branch of the URL tree.
    """

    @classmethod
    @jsonify
    def overview(cls, slug):
        """
        Show "Manage Game" form.
        """
        game = get_game_by_slug(slug, reload_game=True)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        return _details(game)

    @classmethod
    @jsonify
    def load(cls, slug):
        """
        Send a signal to load a game from the path specified in the request
        parameters.
        """
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        path = request.params.get('path', None)
        if not path:
            response.status_int = 400
            return {'ok': False, 'msg': 'Path not specified'}

        try:
            game.load(path)
        except GameError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Unable to load details for game: %s' % slug}
        else:
            GameList.get_instance().save_game_list()

        return _details(game)

    @classmethod
    @jsonify
    def save(cls, slug):
        """
        Send a signal to save the data passed via the request parameters
        to a game.
        """
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        try:
            game.save(dict(request.params))
        except (GamePathNotFoundError, GamePathError) as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        else:
            GameList.get_instance().save_game_list()

        return _details(game)

    @classmethod
    @jsonify
    def delete(cls, slug):
        """
        Deletes a game.
        """
        try:
            GameList.get_instance().delete_game(slug)
        except GameNotFoundError as e:
            response.status_int = 404
            return {'ok': False, 'msg': str(e)}

        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'
        return {'ok': True}

    @classmethod
    @jsonify
    def directory_options(cls):
        directory = request.params.get('dir', None)
        if not directory:
            response.status_int = 400
            return {'ok': False, 'msg': 'Directory not specified'}

        directory = directory.strip()

        # Test for characters not legal in Windows paths
        if not set(directory).isdisjoint(set('*?"<>|\0')):
            response.status_int = 400
            return {'ok': False, 'msg': 'Bad directory'}

        try:
            absDir = get_absolute_path(directory)
        except TypeError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Bad directory'}

        options = {
            'absDir': norm_path(absDir),
            'dir': directory
        }

        if not os.access(absDir, os.F_OK):
            options['create'] = True
        else:
            if not os.access(absDir, os.W_OK):
                options['inaccessible'] = True
            elif os.access(path_join(absDir, 'manifest.yaml'), os.F_OK):
                if GameList.get_instance().path_in_use(absDir):
                    options['inUse'] = True
                else:
                    options['overwrite'] = True
            else:
                options['usable'] = True

        return {'ok': True, 'data': options}

    @classmethod
    @jsonify
    def create_slug(cls):
        title = request.params.get('title', None)
        if not title:
            response.status_int = 400
            return {'ok': False, 'msg': 'Title not specified'}

        base_slug = slugify(title)
        unique_slug = GameList.get_instance().make_slug_unique(base_slug)
        if base_slug == unique_slug:
            return {
                'ok': True,
                'data': base_slug,
            }
        else:
            return {
                'ok': True,
                'data': unique_slug,
                # TODO fix this! unique_slug can be up to 6 characters longer
                'msg': 'added %s to avoid slug clash.' % unique_slug[-2:]
            }
