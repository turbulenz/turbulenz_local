# Copyright (c) 2010-2011,2013 Turbulenz Limited

from os.path import normcase, join, isfile
from mimetypes import guess_type

# pylint: disable=F0401
from paste.fileapp import FileApp
# pylint: enable=F0401


class StaticFilesMiddleware(object):
    """
    Serves static files from virtual paths mapped to real paths
    """

    def __init__(self, app, path_items):
        self.app = app
        self.path_items = path_items
        self.cached_apps = {}
        self.utf8_mimetypes = set(['text/html', 'application/json'])

    def __call__(self, environ, start_response):

        request_path = environ.get('PATH_INFO', '')

        app = self.cached_apps.get(request_path)
        if app:
            return app(environ, start_response)

        if not request_path.endswith('/'):
            relative_request_path = request_path.lstrip('/')

            for root_dir, max_cache in self.path_items:

                file_asset_path = normcase(join(root_dir, relative_request_path))

                if isfile(file_asset_path):
                    content_type, _ = guess_type(file_asset_path)
                    if content_type in self.utf8_mimetypes:
                        content_type += '; charset=utf-8'

                    app = FileApp(file_asset_path, content_type=content_type)

                    if max_cache:
                        app.cache_control(max_age=max_cache)
                    else:
                        app.cache_control(max_age=0)

                    self.cached_apps[request_path] = app

                    return app(environ, start_response)

        return self.app(environ, start_response)
