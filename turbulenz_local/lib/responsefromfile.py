# Copyright (c) 2011,2013 Turbulenz Limited
from logging import getLogger

# pylint: disable=F0401
from tornado.web import RequestHandler
# pylint: enable=F0401

from os.path import join, relpath, pardir

# pylint: disable=R0904,W0221,E1101
class ResponseFromFileHandler(RequestHandler):

    log = getLogger('ResponseFromFileHandler')

    def __init__(self, application, request, **kwargs):
        self.path = None
        RequestHandler.__init__(self, application, request, **kwargs)

    def initialize(self, path):
        self.path = path

    def get(self, file_path):
        file_path = file_path.split("?")[0]
        file_path = join(self.path, file_path)

        # check that the path is under the responses directory
        if relpath(file_path, self.path)[:2] == pardir:
            self.set_status(400)
            self.finish('File path must be under the responses directory')

        try:
            f = open(file_path, 'r')
            file_contents = f.read()

            if hasattr(self.request, "connection"):
                self.request.connection.stream.set_close_callback(None)
            if len(file_contents) > 0:
                self.request.write(file_contents)
            self.request.finish()

            f.close()
            return

        except IOError:
            self.set_status(404)
            self.finish('File Not Found: %s' % file_path)


# pylint: enable=R0904,W0221,E1101
