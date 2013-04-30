# Copyright (c) 2011-2013 Turbulenz Limited

from traceback import format_exc
from logging import getLogger

# pylint: disable=F0401
from paste.deploy.converters import asbool
# pylint: enable=F0401

from simplejson import JSONEncoder
# pylint: disable=C0103
_json_encoder = JSONEncoder(encoding='utf-8', separators=(',',':'))
# pylint: enable=C0103

from turbulenz_local.lib.exceptions import PostOnlyException, ApiUnavailable, ApiNotImplemented, ApiException

LOG = getLogger(__name__)

class ErrorMiddleware(object):
    """
    Catch errors and report.
    """
    error_response = ['{"ok":false,"msg":"Request could not be processed!"}']
    error_headers = [('Content-Type', 'application/json; charset=utf-8'),
                     ('Content-Length', str(len(error_response[0])))]

    postonly_response = ['{"ok":false,"msg":"Post Only!"}']
    postonly_headers = [('Content-Type', 'application/json; charset=utf-8'),
                        ('Cache-Control', 'no-store'),
                        ('Content-Length', str(len(postonly_response[0]))),
                        ('Allow', 'POST')]

    def __init__(self, app, config):
        self.app = app
        self.config = config

    def __call__(self, environ, start_response):
        try:
            # To see exceptions thrown above this call (i.e. higher in the middleware stack
            # and exceptions in this file) see the devserver/devserver.log file
            return self.app(environ, start_response)
        except ApiUnavailable as e:
            json_data = _json_encoder.encode(e.value)
            msg = '{"ok":false,"msg":"Service Unavailable","data":%s}' % json_data
            headers = [('Content-Type', 'application/json; charset=utf-8'),
                       ('Content-Length', str(len(msg)))]
            start_response('503 Service Unavailable', headers)
            return [msg]
        except ApiNotImplemented:
            start_response('501 Not Implemented', self.error_headers)
            return self.error_headers
        except ApiException as e:
            json_msg_data = _json_encoder.encode(e.value)
            if e.json_data:
                msg = '{"ok":false,"msg":%s,"data":%s}' % (json_msg_data, _json_encoder.encode(e.json_data))
            else:
                msg = '{"ok":false,"msg":%s}' % json_msg_data
            headers = [('Content-Type', 'application/json; charset=utf-8'),
                       ('Content-Length', str(len(msg)))]
            start_response(e.status, headers)
            return [msg]
        except PostOnlyException:
            start_response('405 Method Not Allowed', self.postonly_headers)
            return self.postonly_response
        except:
            log_msg = 'Exception when processing request: %s' % environ['PATH_INFO']
            trace_string = format_exc()

            LOG.error(log_msg)
            LOG.error(trace_string)
            if asbool(self.config.get('debug')):
                print(log_msg)
                print(trace_string)

            start_response('500 Internal Server Error', self.error_headers)
            return self.error_response
