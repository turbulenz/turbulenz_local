# Copyright (c) 2010-2013 Turbulenz Limited

from logging import getLogger
from os import access, R_OK
from os.path import join, normpath
from mimetypes import guess_type

# pylint: disable=F0401
from paste.fileapp import FileApp
# pylint: enable=F0401

from turbulenz_local.models.gamelist import GameList
from turbulenz_local.tools import get_absolute_path

LOG = getLogger(__name__)

class StaticGameFilesMiddleware(object):
    """
    Serves static files from virtual game paths mapped to real game path
    """

    def __init__(self, app, staticmax_max_age=0):
        self.app = app
        self.staticmax_max_age = staticmax_max_age
        self.cached_apps = {}
        self.game_list = GameList.get_instance()
        self.utf8_mimetypes = set(['text/html', 'application/json'])

    def __call__(self, environ, start_response):
        request_path = environ.get('PATH_INFO', '')

        # check if the request is for static files at all
        path_parts = request_path.strip('/').split('/', 2)
        if len(path_parts) == 3 and path_parts[0] in ['play', 'game-meta']:

            slug = path_parts[1]
            game = self.game_list.get_by_slug(slug)
            if game and game.path.is_set():
                asset_path = path_parts[2]
                file_asset_path = normpath(join(get_absolute_path(game.path), asset_path))

                def build_file_iter(f, block_size):
                    return StaticFileIter(file_asset_path, normpath(join(slug, asset_path)), f, block_size)

                def remove_ranges_start_response(status, headers, exc_info=None):
                    if status == '200 OK':
                        headers = [t for t in headers if t[0] != 'Accept-Ranges' and t[0] != 'Content-Range']
                    return start_response(status, headers, exc_info)

                # check if the request is already cached
                app = self.cached_apps.get(request_path)
                if app:
                    environ['wsgi.file_wrapper'] = build_file_iter

                    try:
                        return app(environ, remove_ranges_start_response)
                    except OSError as e:
                        LOG.error(e)

                elif access(file_asset_path, R_OK):
                    content_type, _ = guess_type(file_asset_path)
                    if content_type in self.utf8_mimetypes:
                        content_type += '; charset=utf-8'

                    app = FileApp(file_asset_path, content_type=content_type)

                    if asset_path.startswith('staticmax'):
                        app.cache_control(max_age=self.staticmax_max_age)
                    else:
                        app.cache_control(max_age=0)

                    self.cached_apps[request_path] = app

                    environ['wsgi.file_wrapper'] = build_file_iter
                    return app(environ, remove_ranges_start_response)

                start_response(
                    '404 Not Found',
                    [('Content-Type', 'text/html; charset=UTF-8'),
                    ('Content-Length', '0')]
                )
                return ['']

        return self.app(environ, start_response)


class StaticFileIter(object):
    __slots__ = ('full_game_file_path', 'game_file_path', 'file', 'block_size')

    def __init__(self, full_game_file_path, game_file_path, f, block_size):
        self.full_game_file_path = full_game_file_path
        self.game_file_path = game_file_path
        self.file = f
        self.block_size = block_size

    def get_full_game_file_path(self):
        return self.full_game_file_path

    def get_game_file_path(self):
        return self.game_file_path

    def __iter__(self):
        return self

    def next(self):
        data = self.file.read(self.block_size)
        if not data:
            raise StopIteration
        return data

    def close(self):
        self.file.close()
