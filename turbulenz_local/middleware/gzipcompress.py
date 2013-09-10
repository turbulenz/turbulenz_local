# Copyright (c) 2010-2013 Turbulenz Limited

import io
import gzip
import logging
import mimetypes
import os

from os.path import join, normpath

# pylint: disable=F0401
from paste.deploy.converters import asint, aslist
# pylint: enable=F0401

from turbulenz_local.tools import compress_file


LOG = logging.getLogger(__name__)


def _get_file_stats(file_name):
    try:
        file_stat = os.stat(file_name)
        return file_stat.st_mtime, file_stat.st_size
    except OSError:
        return -1, 0


class GzipFileIter(object):
    __slots__ = ('file')

    def __init__(self, f):
        self.file = f

    def __iter__(self):
        return self

    def next(self):
        data = self.file.read(65536)
        if not data:
            raise StopIteration
        return data

    def close(self):
        self.file.close()


def _compress_response(response, response_buffer, compression_level):
    compressed_buffer = io.BytesIO()
    gzip_file = gzip.GzipFile(
        mode='wb',
        compresslevel=compression_level,
        fileobj=compressed_buffer
    )

    if response_buffer.tell() != 0:
        gzip_file.write(response_buffer.getvalue())
    response_buffer.close()

    for line in response:
        gzip_file.write(line)

    gzip_file.close()

    if hasattr(response, 'close'):
        response.close()

    compressed_response_data = compressed_buffer.getvalue()
    compressed_buffer.close()

    return [compressed_response_data], len(compressed_response_data)


class GzipMiddleware(object):
    """ GZip compress responses if encoding is accepted by client """

    def __init__(self, app, config):
        self.app = app
        self.compress_level = asint(config.get('gzip.compress_level', '5'))
        self.compress = set(aslist(config.get('gzip.compress', ''), ',', strip=True))
        self.do_not_compress = set(aslist(config.get('gzip.do_not_compress', ''), ',', strip=True))
        for m in (self.compress | self.do_not_compress):
            if mimetypes.guess_extension(m) is None:
                LOG.warning('Unrecognised mimetype in server configuration: %s', m)
        self.cache_dir = normpath(config.get('deploy.cache_dir', None))

    def __call__(self, environ, start_response):

        # if client does not accept gzip encoding, pass the request through
        if 'gzip' not in environ.get('HTTP_ACCEPT_ENCODING', ''):
            return self.app(environ, start_response)

        # capture the response headers and setup compression
        start_response_args = {
            'level': 0
        }

        def gzip_start_response(status, headers, exc_info=None):

            # We only need compress if the status is 200, this means we're sending data back.
            if status != '200 OK':
                # If status is 304 remove dummy tags
                if status.startswith('304'):
                    headers = [item for item in headers if item[0] != 'Accept-Ranges']
                return start_response(status, headers, exc_info)

            else:
                mimetype = None
                for k, v in headers:
                    if k == 'Content-Type':
                        mimetype = v.split(';')[0].split(',')[0]
                    elif k == 'Content-Length':
                        # Don't bother with small responses because the gzip file could actually be bigger
                        if int(v) <= 256:
                            return start_response(status, headers, exc_info)

                if not mimetype:
                    # This has no mimetype.
                    LOG.warning('Response with no mimetype: %s', environ.get('PATH_INFO', ''))
                    compression_level = 0
                elif mimetype in self.do_not_compress:
                    # This is a known mimetype that we don't want to compress.
                    compression_level = 0
                elif mimetype in self.compress:
                    # This is a know mimetype that we *do* want to compress.
                    compression_level = self.compress_level
                else:
                    LOG.warning('Response with mimetype not in compression lists: %s', mimetype)
                    compression_level = 1

                if compression_level != 0:
                    # save args so we can call start_response later
                    start_response_args['status'] = status
                    start_response_args['headers'] = headers
                    start_response_args['exc_info'] = exc_info

                    start_response_args['level'] = compression_level

                    response_buffer = io.BytesIO()
                    start_response_args['buffer'] = response_buffer
                    return response_buffer.write

                else:
                    return start_response(status, headers, exc_info)

        # pass on the request
        response = self.app(environ, gzip_start_response)

        compression_level = start_response_args['level']
        if compression_level != 0:

            response_buffer = start_response_args['buffer']
            response_length = 0

            # Check if it is a game file that could be pre-compressed
            if hasattr(response, 'get_game_file_path'):
                # Ignore whatever response we got
                response_buffer.close()
                response_buffer = None

                game_file_path = response.get_full_game_file_path()
                cached_game_file_path = join(self.cache_dir, response.get_game_file_path() + '.gz')

                cached_mtime, cached_size = _get_file_stats(cached_game_file_path)
                source_mtime, source_size = _get_file_stats(game_file_path)
                if cached_mtime < source_mtime:
                    if not compress_file(game_file_path, cached_game_file_path):
                        start_response(start_response_args['status'], start_response_args['headers'])
                        return response

                    # We round mtime up to the next second to avoid precision problems with floating point values
                    source_mtime = long(source_mtime) + 1
                    os.utime(cached_game_file_path, (source_mtime, source_mtime))

                    _, cached_size = _get_file_stats(cached_game_file_path)

                if cached_size < source_size:
                    if hasattr(response, 'close'):
                        response.close()
                        response = None

                    response = GzipFileIter(open(cached_game_file_path, 'rb'))
                    response_length = cached_size

                else:
                    start_response(start_response_args['status'], start_response_args['headers'])
                    return response

            else:
                response, response_length = _compress_response(response, response_buffer, compression_level)

            # override the content-length and content-encoding response headers
            headers = [ ]
            for name, value in start_response_args['headers']:
                name_lower = name.lower()
                if name_lower != 'content-length' and name_lower.find('-range') == -1:
                    headers.append((name, value))
            headers.append(('Content-Length', str(response_length)))
            headers.append(('Content-Encoding', 'gzip'))

            start_response(start_response_args['status'], headers, start_response_args['exc_info'])

        return response
