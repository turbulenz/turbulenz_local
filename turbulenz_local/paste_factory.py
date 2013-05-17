# Copyright (c) 2011-2013 Turbulenz Limited
from time import strftime, gmtime
from logging import getLogger
from os.path import dirname, join as path_join

# pylint: disable=F0401
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.web import Application, FallbackHandler
from tornado.wsgi import WSGIContainer
from tornado.escape import utf8

from paste.deploy.converters import asbool
# pylint: enable=F0401

from turbulenz_local.lib.multiplayer import MultiplayerHandler, MultiplayerStatusHandler, SessionStatusHandler
from turbulenz_local.lib.responsefromfile import ResponseFromFileHandler
from turbulenz_local.handlers.localv1.save import SaveFileHandler

# pylint: disable=R0904
class DevserverWSGIContainer(WSGIContainer):

    logger = getLogger('DevserverWSGIContainer')

    new_line = b'\r\n'
    empty_string = b''

    def __call__(self, request):
        parts = []
        parts_append = parts.append

        base_header = strftime('\r\nDate: %a, %d %b %Y %H:%M:%S GMT', gmtime()) + '\r\nServer: tornado\r\n'
        if not request.supports_http_1_1():
            if request.headers.get('Connection', '').lower() == 'keep-alive':
                base_header += 'Connection: Keep-Alive\r\n'

        def start_response(status, response_headers, exc_info=None):
            parts_append(utf8('HTTP/1.1 ' + status + base_header))
            for key, value in response_headers:
                parts_append(utf8(key + ': ' + value + '\r\n'))
            parts_append(self.new_line)
            return None

        environ = WSGIContainer.environ(request)
        environ['wsgi.multiprocess'] = False # Some EvalException middleware fails if set to True

        app_response = self.wsgi_application(environ, start_response)
        if not parts:
            raise Exception('WSGI app did not call start_response')

        if request.method != 'HEAD':
            parts.extend(app_response)

        if hasattr(app_response, 'close'):
            app_response.close()
        app_response = None

        if hasattr(request, "connection"):
            # Now that the request is finished, clear the callback we
            # set on the IOStream (which would otherwise prevent the
            # garbage collection of the RequestHandler when there
            # are keepalive connections)
            request.connection.stream.set_close_callback(None)

        request.write(self.empty_string.join(parts))
        try:
            request.finish()
        except IOError as e:
            self.logger.error('Exception when writing response: %s', str(e))

    def _log(self, status_code, request):
        pass

class DevserverApplication(Application):

    def log_request(self, handler):
        pass
# pylint: enable=R0904


def run(wsgi_app, global_conf,
        host='0.0.0.0', port='8080',
        multiplayer=False,
        testing=False):

    port = int(port)
    multiplayer = asbool(multiplayer)
    testing = asbool(testing)

    wsgi_app = DevserverWSGIContainer(wsgi_app)

    handlers = []

    if multiplayer:
        handlers.append(('/multiplayer/(.*)/(.*)', MultiplayerHandler))
        handlers.append(('/api/v1/multiplayer/status', MultiplayerStatusHandler))
        handlers.append(('/api/v1/multiplayer/status/session/(.*)', SessionStatusHandler))

    if testing:
        raw_response_dir = path_join(dirname(__file__), 'raw-response')
        handlers.append(('/raw-response/(.*)',
                         ResponseFromFileHandler, dict(path=raw_response_dir)))

    handlers.append(('/local/v1/save/([^/]+)/(.*)', SaveFileHandler))

    handlers.append(('.*', FallbackHandler, dict(fallback=wsgi_app)))

    tornado_app = DevserverApplication(handlers, transforms=[])
    handlers = None

    server = HTTPServer(tornado_app)
    server.listen(port, host)

    print 'Serving on %s:%u view at http://127.0.0.1:%u' % (host, port, port)
    IOLoop.instance().start()
