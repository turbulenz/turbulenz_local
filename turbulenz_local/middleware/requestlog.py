# Copyright (c) 2010-2011,2013 Turbulenz Limited

from datetime import datetime
import logging
import re
import sys

# pylint: disable=F0401
from paste.deploy.converters import asbool
# pylint: enable=F0401

try:
    from turbulenz_tools.utils.coloured_writer import ColouredWriter
    HANDLER = logging.StreamHandler(ColouredWriter(sys.stdout, sys.stderr))
except ImportError:
    HANDLER = logging.StreamHandler()

HANDLER.setFormatter(logging.Formatter('%(message)s'))
HANDLER.setLevel(logging.INFO)
LOG = logging.getLogger(__name__)
LOG.addHandler(HANDLER)
LOG.setLevel(logging.INFO)

class LoggingMiddleware(object):
    """
    Output a message to STDOUT per response.
    """

    def __init__(self, app, config):
        self.app = app
        self.log_all_requests = asbool(config.get('logging.log_all_requests'))
        self.log_pattern = asbool(config.get('logging.log_pattern'))
        self.log_pattern_re = config.get('logging.log_pattern_re')
        self.log_request_headers = asbool(config.get('logging.log_request_headers'))
        self.log_response_name = asbool(config.get('logging.log_response_name'))
        self.log_response_headers = asbool(config.get('logging.log_response_headers'))
        self.remove_letters_re = re.compile('[^\d]')

    def __call__(self, environ, start_response):
        request_path = environ.get('PATH_INFO', '')

        # If we don't log all the requests then look at the request path to see if it is an asset request.
        # If not, send the request onto the next middleware.
        if not self.log_all_requests:
            path_parts = request_path.strip('/').split('/', 2)

            if len(path_parts) != 3 or path_parts[0] != 'play':
                return self.app(environ, start_response)

        if self.log_request_headers or self.log_response_headers:
            log_headers = (not self.log_pattern) or (re.match(self.log_pattern_re, request_path) is not None)
        else:
            log_headers = False

        if log_headers:
            if self.log_request_headers:
                LOG.info("Request Headers:")
                for k, v in environ.iteritems():
                    if k.startswith('HTTP_'):
                        LOG.info("\t%s: %s", k, v)

        # capture headers from response
        start_response_args = {}
        def logging_start_response(status, headers, exc_info=None):
            start_response_args['status'] = status
            start_response_args['headers'] = headers
            return start_response(status, headers, exc_info)

        # pass through request
        response = self.app(environ, logging_start_response)
        response_headers = dict(start_response_args['headers'])

        if self.log_response_name:
            now = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
            status = start_response_args.get('status', '200')
            message = '"%s %s" %s %s' % (environ.get('REQUEST_METHOD'),
                                         request_path,
                                         self.remove_letters_re.sub('', status),
                                         response_headers.get('Content-Length', 0))
            LOG.info("[%s] %s", now, message)

        if log_headers:
            if self.log_response_headers:
                LOG.info("Response Headers:")
                for (k, v) in response_headers.iteritems():
                    LOG.info("\t%s: %s", k, v)

        return response
