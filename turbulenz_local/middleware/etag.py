# Copyright (c) 2010-2011,2013 Turbulenz Limited

from io import BytesIO
from hashlib import sha1
from base64 import urlsafe_b64encode

# pylint: disable=F0401
from paste.deploy.converters import asint
# pylint: enable=F0401


class EtagMiddleware(object):
    """ Add Etag header if missing """

    def __init__(self, app, config):
        self.app = app
        self.min_size = asint(config.get('etag.min_size', 1))

    def __call__(self, environ, start_response):

        if environ.get('REQUEST_METHOD') != 'GET':
            return self.app(environ, start_response)

        client_etag = environ.get('HTTP_IF_NONE_MATCH', None)

        # capture the response headers
        etag_info = {}
        start_response_args = {}
        min_size = self.min_size

        def etag_start_response(status, headers, exc_info=None):

            # We only need to calculate Etags if the status is 200
            # this means we're sending data back.
            if status != '200 OK':
                return start_response(status, headers, exc_info)

            for k, v in headers:
                if k == 'Etag':
                    if v:
                        etag_info['response_etag'] = v
                        if client_etag == v:
                            status = '304 Not Modified'
                            # Only return cookies because they may have side effects
                            headers = [item for item in headers if item[0] == 'Set-Cookie']
                            headers.append(('Etag', v))
                        return start_response(status, headers, exc_info)
                elif k == 'Content-Length':
                    # Don't bother with small responses because the Etag will actually be bigger
                    if int(v) <= min_size:
                        return start_response(status, headers, exc_info)

            # save args so we can call start_response later
            start_response_args['status'] = status
            start_response_args['headers'] = headers
            start_response_args['exc_info'] = exc_info

            response_buffer = BytesIO()

            etag_info['buffer'] = response_buffer

            return response_buffer.write

        # pass on the request
        response = self.app(environ, etag_start_response)

        # If there is a buffer then status is 200 and there is no Etag on the response
        response_buffer = etag_info.get('buffer', None)
        if response_buffer:

            # check if we can just read the data directly from the response
            if response_buffer.tell() == 0 and \
               isinstance(response, list) and \
               len(response) == 1 and \
               isinstance(response[0], basestring):

                response_data = response[0]

            else:

                for line in response:
                    response_buffer.write(line)

                if hasattr(response, 'close'):
                    response.close()

                response_data = response_buffer.getvalue()

            response_buffer.close()

            response_etag = sha1()
            response_etag.update(response_data)
            response_etag = '%s-%x' % (urlsafe_b64encode(response_etag.digest()).strip('='),
                                       len(response_data))

            headers = start_response_args['headers']

            if client_etag == response_etag:
                status = '304 Not Modified'
                headers = [item for item in headers if item[0] == 'Set-Cookie']
                response = ['']
            else:
                status = start_response_args['status']
                response = [response_data]

            headers.append(('Etag', response_etag))

            start_response(status, headers, start_response_args['exc_info'])

        else:
            response_etag = etag_info.get('response_etag', None)
            # If there is an Etag and is equal to the client one we are on a 304
            if response_etag and client_etag == response_etag:
                response = ['']

        return response
