# Copyright (c) 2010-2013 Turbulenz Limited

import mimetypes

from time import time
from paste import request

from turbulenz_local.models.gamelist import GameList
from turbulenz_local.models.metrics import MetricsSession


class MetricsMiddleware(object):

    def __init__(self, app, config):
        self.app = app
        self.user_id_counter = int(time() - 946080000)
        self.cookie_session_name = config.get('metrics.user.key', 'metrics_id')
        self.gamelist = GameList.get_instance()

    def __call__(self, environ, start_response):
        # check whether the the request should be logged, i.e. starts with
        # 'play' and is longer than a mere request for the playable-versions
        # page
        request_path = environ.get('PATH_INFO', '')
        path_parts = request_path.strip('/').split('/', 2)

        if len(path_parts) == 3 and path_parts[0] == 'play':
            slug = path_parts[1]

            if self.gamelist.get_by_slug(slug):
                file_name = path_parts[2]

                # find user id on cookies or create a new one
                cookies = request.get_cookies(environ)
                if cookies.has_key(self.cookie_session_name):
                    user_id = cookies[self.cookie_session_name].value
                    is_new_user = False
                else:
                    self.user_id_counter += 1
                    user_id = '%x' % self.user_id_counter
                    is_new_user = True

                slug_sessions = MetricsSession.get_sessions(slug)

                # make sure there is a session when an html file is requested
                # ignore otherwise
                session = slug_sessions.get(user_id, None)
                if file_name.endswith(('.html', '.htm')) or \
                   (file_name.endswith(('.tzjs', '.canvas.js', '.swf')) and 'HTTP_REFERER' in environ and \
                    not environ['HTTP_REFERER'].endswith(('.html', '.htm'))):
                    if session:
                        session.finish()
                        session = None
                    try:
                        session = MetricsSession(slug)
                    except IOError:
                        return self.app(environ, start_response)
                    slug_sessions[user_id] = session

                elif not session:
                    return self.app(environ, start_response)

                # define function to capture status and headers from response
                response_headers = []
                def metrics_start_response(status, headers, exc_info=None):
                    if is_new_user:
                        headers.append(('Set-Cookie',
                                        '%s=%s; Path=/play/%s/' % (self.cookie_session_name, user_id, slug)))
                    response_headers.append(status)
                    response_headers.append(headers)
                    return start_response(status, headers, exc_info)

                # pass through request and get response
                response = self.app(environ, metrics_start_response)

                status = response_headers[0]
                file_size = 0
                if status.startswith('404'):
                    file_type = 'n/a'
                else:
                    file_type = None
                    if status.startswith('200'):
                        for k, v in response_headers[1]:
                            if k == 'Content-Length':
                                file_size = v
                                if file_type:
                                    break
                            elif k == 'Content-Type':
                                file_type = v
                                if file_size:
                                    break
                    else:
                        for k, v in response_headers[1]:
                            if k == 'Content-Type':
                                file_type = v
                                break
                    if not file_type:
                        file_type = mimetypes.guess_type(file_name)[0]
                        if not file_type:
                            file_type = 'n/a'
                    else:
                        file_type = file_type.split(';')[0].split(',')[0]
                session.append(file_name, file_size, file_type, status)

                # send the response back up the WSGI layers
                return response

        return self.app(environ, start_response)
