# Copyright (c) 2013 Turbulenz Limited
from logging import getLogger
from os.path import join as path_join, dirname, normpath

from tornado.web import RequestHandler

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.tools import get_absolute_path, create_dir

LOG = getLogger(__name__)

# pylint: disable=R0904,W0221,E1103
class SaveFileHandler(RequestHandler):

    def set_default_headers(self):
        self.set_header('Server', 'tz')

    def post(self, slug, filename):
        """
        Saves given contents to file to game folder.
        """
        game = get_game_by_slug(slug)
        if not game:
            self.set_status(404)
            return self.finish({'ok': False, 'msg': 'Game does not exist: %s' % slug})

        if not filename:
            self.set_status(400)
            return self.finish({'ok': False, 'msg': 'Missing filename'})

        if '..' in filename:
            self.set_status(403)
            return self.finish({'ok': False, 'msg': 'Cannot write outside game folder'})

        content_type = self.request.headers.get('Content-Type', '')
        if content_type and 'application/x-www-form-urlencoded' in content_type:
            content = self.get_argument('content')
            binary = False
        else:
            content = self.request.body
            binary = True

        self.request.body = None
        self.request.arguments = None

        file_path = path_join(get_absolute_path(game.get_path()), normpath(filename))

        file_dir = dirname(file_path)
        if not create_dir(file_dir):
            LOG.error('Failed to create directory at "%s"', file_dir)
            self.set_status(500)
            return self.finish({'ok': False, 'msg': 'Failed to create directory'})

        if content:
            if not binary:
                try:
                    content = content.encode('utf-8')
                except UnicodeEncodeError as e:
                    LOG.error('Failed to encode file contents: %s', str(e))
                    self.set_status(500)
                    return self.finish({'ok': False, 'msg': 'Failed to encode file contents'})

            LOG.info('Writing file at "%s" (%d bytes)', file_path, len(content))

        else:
            LOG.info('Writing empty file at "%s"', file_path)

        try:
            file_obj = open(file_path, 'wb')
            try:
                file_obj.write(content)
            finally:
                file_obj.close()
        except IOError as e:
            LOG.error('Failed to write file at "%s": %s', file_path, str(e))
            self.set_status(500)
            return self.finish({'ok': False, 'msg': 'Failed to write file'})

        return self.finish({'ok': True})

