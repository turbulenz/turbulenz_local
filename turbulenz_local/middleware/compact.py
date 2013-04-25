# Copyright (c) 2010-2011,2013 Turbulenz Limited

from StringIO import StringIO

# pylint: disable=C0103
try:
    from turbulenz_tools.utils.htmlmin import HTMLMinifier
except ImportError:
    HTMLMinifier = None
# pylint: enable=C0103

class CompactMiddleware(object):

    def __init__(self, app, config):
        # pylint: disable=F0401
        from paste.deploy.converters import asbool
        # pylint: enable=F0401
        self.app = app
        self.compact_html = asbool(config.get('compact.html', True))
        self.compact_script = asbool(config.get('compact.script', True))

    @classmethod
    def disable(cls, request):
        request.environ['compact.html'] = False

    @classmethod
    def enable(cls, request):
        request.environ['compact.html'] = True

    def __call__(self, environ, start_response):
        if not self.compact_html:
            return self.app(environ, start_response)

        start_response_args = {}

        def compact_start_response(status, headers, exc_info=None):
            # We only need compress if the status is 200, this means we're sending data back.
            if status == '200 OK':
                for k, v in headers:
                    if k == 'Content-Type':
                        mimetype = v.split(';')[0].split(',')[0]
                        if mimetype == 'text/html':
                            start_response_args['compact'] = True

                            start_response_args['status'] = status
                            start_response_args['headers'] = headers
                            start_response_args['exc_info'] = exc_info

                            response_buffer = StringIO()
                            start_response_args['buffer'] = response_buffer
                            return response_buffer.write

            return start_response(status, headers, exc_info)

        # pass on the request
        response = self.app(environ, compact_start_response)

        # compact
        if start_response_args.get('compact', False):

            response_headers = start_response_args['headers']
            response_buffer = start_response_args['buffer']

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

            if environ.get('compact.html', True) and HTMLMinifier:
                output = StringIO()
                compactor = HTMLMinifier(output.write, self.compact_script)
                compactor.feed(response_data)
                response_data = output.getvalue()

                headers = [ ]
                for name, value in response_headers:
                    name_lower = name.lower()
                    if name_lower != 'content-length' and name_lower.find('-range') == -1:
                        headers.append((name, value))
                headers.append(('Content-Length', str(len(response_data))))
                response_headers = headers

            response = [response_data]

            start_response(start_response_args['status'], response_headers, start_response_args['exc_info'])

        return response
