# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for deploying a game
"""
################################################################################
# pylint:disable=W0212
import sys
if "darwin" == sys.platform: # and 0 == sys.version.find("2.7.2"):

    # Monkey path socket.sendall to handle EAGAIN (Errno 35) on mac.
    # Ideally, httplib.send would handle EAGAIN, but it just calls
    # sendall.  The code below this patches httplib, but relies on
    # accessing internal variables.  OTOH, socket.sendall can be
    # implemented using only calls to public methods, so should be
    # safer to override.

    import socket
    import time
    def socket_socket_sendall(self, data):
        while len(data) > 0:
            try:
                bytes_sent = self.send(data)
                data = data[bytes_sent:]
            except socket.error, e:
                if str(e) == "[Errno 35] Resource temporarily unavailable":
                    time.sleep(0.1)
                else:
                    raise e
    socket._socketobject.sendall = socket_socket_sendall

    # Monkey patch httplib to handle EAGAIN socket errors on maxosx.
    # send() is the original function from httplib with
    # socket.sendall() replaced by self._dosendall().  _dosendall() calls
    # socket.send() handling Errno 35 by retrying.

    # import httplib
    # import array
    # def httplib_httpconnection__dosendall(self, data):
    #     while len(data) > 0:
    #         try:
    #             bytes_sent = self.sock.send(data)
    #             data = data[bytes_sent:]
    #         except socket.error, e:
    #             if str(e) == "[Errno 35] Resource temporarily unavailable":
    #                 time.sleep(0.1)
    #             else:
    #                 raise e
    # def httplib_httpconnection_send(self, data):
    #     """Send `data' to the server."""
    #     if self.sock is None:
    #         if self.auto_open:
    #             self.connect()
    #         else:
    #             raise httplib.NotConnected()
    #
    #     if self.debuglevel > 0:
    #         print "send:", repr(data)
    #     blocksize = 8192
    #     if hasattr(data,'read') and not isinstance(data, array.array):
    #         if self.debuglevel > 0: print "sendIng a read()able"
    #         datablock = data.read(blocksize)
    #         while datablock:
    #             self._dosendall(datablock)
    #             datablock = data.read(blocksize)
    #     else:
    #         self._dosendall(data)
    # httplib.HTTPConnection._dosendall = httplib_httpconnection__dosendall
    # httplib.HTTPConnection.send = httplib_httpconnection_send

# pylint:enable=W0212
################################################################################

from urllib3 import connection_from_url
from urllib3.exceptions import HTTPError, SSLError
from threading import Thread
from logging import getLogger
from simplejson import loads as json_loads

from pylons import request, response, config

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import get_game_by_slug, GameError
from turbulenz_local.lib.deploy import Deployment


LOG = getLogger(__name__)

class DeployController(BaseController):
    """
    Controller class for the 'deploy' branch of the URL tree.
    """
    _deploying = {}

    base_url = config.get('deploy.base_url', None)
    hub_pool = None
    cookie_name = config.get('deploy.cookie_name', None)
    cache_dir = config.get('deploy.cache_dir', None)

    @classmethod
    def _create_deploy_info(cls, game, hub_project, hub_version, hub_versiontitle, hub_cookie):

        deploy_info = Deployment(game,
                                 cls.hub_pool,
                                 hub_project,
                                 hub_version,
                                 hub_versiontitle,
                                 hub_cookie,
                                 cls.cache_dir)

        thread = Thread(target=deploy_info.deploy, args=[])
        thread.daemon = True
        thread.start()

        deploy_key = hub_project + hub_version
        cls._deploying[deploy_key] = deploy_info


    @classmethod
    def _get_projects_for_upload(cls, hub_headers, username, rememberme=False):

        try:
            r = cls.hub_pool.request('POST',
                                     '/dynamic/upload/projects',
                                     headers=hub_headers,
                                     redirect=False)

        except (HTTPError, SSLError) as e:
            LOG.error(e)
            response.status_int = 500
            return {'ok': False, 'msg': str(e)}

        if r.status != 200:
            if r.status == 503:
                response.status_int = 503
                # pylint: disable=E1103
                return {'ok': False, 'msg': json_loads(r.data).get('msg', 'Service currently unavailable.')}
                # pylint: enable=E1103
            response.status_int = 500
            return {'ok': False, 'msg': 'Wrong Hub answer.'}

        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        return {
            'ok': True,
            'cookie': hub_headers.get('Cookie') if rememberme else None,
            'user': username,
            # pylint: disable=E1103
            'projects': json_loads(r.data).get('projects', [])
            # pylint: enable=E1103
        }


    # pylint: disable=R0911
    @classmethod
    @jsonify
    def login(cls):
        """
        Start deploying the game.
        """
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        hub_pool = connection_from_url(cls.base_url, maxsize=8, timeout=8.0)
        if not hub_pool or not cls.cookie_name:
            response.status_int = 500
            return {'ok': False, 'msg': 'Wrong deployment configuration.'}

        cls.hub_pool = hub_pool

        form = request.params
        try:
            login_name = form['login']
            credentials = {
                'login': login_name,
                'password': form['password'],
                'source': '/local'
            }
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing user login information.'}

        try:
            r = hub_pool.request('POST',
                                 '/dynamic/login',
                                 fields=credentials,
                                 retries=1,
                                 redirect=False)
        except (HTTPError, SSLError) as e:
            LOG.error(e)
            response.status_int = 500
            return {'ok': False, 'msg': str(e)}

        if r.status != 200:
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong user login information.'}

        cookie = r.headers.get('set-cookie', None)
        login_info = json_loads(r.data)

        # pylint: disable=E1103
        if not cookie or cls.cookie_name not in cookie or login_info.get('source') != credentials['source']:
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong user login information.'}
        # pylint: enable=E1103

        hub_headers = {'Cookie': cookie}

        return cls._get_projects_for_upload(hub_headers, login_name, form.get('rememberme'))
    # pylint: enable=R0911


    # pylint: disable=R0911
    @classmethod
    @jsonify
    def try_login(cls):
        """
        Try to login automatically and return deployable projects.
        """
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        hub_pool = connection_from_url(cls.base_url, maxsize=8, timeout=8.0)
        if not hub_pool or not cls.cookie_name:
            response.status_int = 500
            return {'ok': False, 'msg': 'Wrong deployment configuration.'}

        cls.hub_pool = hub_pool

        try:
            hub_headers = {'Cookie': request.params['cookie']}
            r = hub_pool.request('POST',
                                 '/dynamic/user',
                                 headers=hub_headers,
                                 retries=1,
                                 redirect=False
            )
            # pylint: disable=E1103
            username = json_loads(r.data).get('username')
            # pylint: enable=E1103

            status = r.status

        except (HTTPError, SSLError) as e:
            LOG.error(e)
            response.status_int = 500
            return {'ok': False, 'msg': str(e)}
        except KeyError:
            status = 400

        if status != 200:
            response.status_int = 401
            return {'ok': False, 'msg': 'Wrong user login information.'}

        return cls._get_projects_for_upload(hub_headers, username, True)
    # pylint: enable=R0911


    @classmethod
    @jsonify
    def start(cls):
        """
        Start deploying the game.
        """
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        hub_pool = cls.hub_pool
        if not hub_pool or not cls.cookie_name:
            response.status_int = 500
            return {'ok': False, 'msg': 'Wrong deployment configuration.'}

        form = request.params
        try:
            cookie_value = form[cls.cookie_name]
            game = form['local']
            hub_project = form['project']
            hub_version = form['version']
            hub_versiontitle = form.get('versiontitle', '')
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong project information.'}

        game = get_game_by_slug(game)
        if not game or not game.path.is_set() or not game.path.is_correct():
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong game to upload.'}

        hub_cookie = '%s=%s' % (cls.cookie_name, cookie_value)

        cls._create_deploy_info(game, hub_project, hub_version, hub_versiontitle, hub_cookie)

        return {
            'ok': True,
            'data': 'local=%s&project=%s&version=%s' % (game.slug, hub_project, hub_version)
        }

    @classmethod
    @jsonify
    def progress(cls):
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        form = request.params
        try:
            hub_project = form['project']
            hub_version = form['version']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong project information.'}

        deploy_key = hub_project + hub_version
        deploy_info = cls._deploying.get(deploy_key, None)
        if not deploy_info:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown deploy session.'}

        if deploy_info.error:
            LOG.error(deploy_info.error)
            response.status_int = 400
            return {'ok': False, 'msg': deploy_info.error}

        num_files = deploy_info.num_files
        if deploy_info.done:
            if not num_files:
                return {
                    'ok': True,
                    'data': {
                        'total_files': 1,
                        'num_files': 1,
                        'num_bytes': 1,
                        'uploaded_files': 1,
                        'uploaded_bytes': 1
                    }
                }

        return {
            'ok': True,
            'data': {
                'total_files': deploy_info.total_files,
                'num_files': deploy_info.num_files,
                'num_bytes': deploy_info.num_bytes,
                'uploaded_files': deploy_info.uploaded_files,
                'uploaded_bytes': deploy_info.uploaded_bytes
            }
        }

    # pylint: disable=R0911
    @classmethod
    @jsonify
    def postupload_progress(cls):
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        form = request.params
        try:
            hub_project = form['project']
            hub_version = form['version']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Wrong project information.'}

        deploy_key = hub_project + hub_version
        deploy_info = cls._deploying.get(deploy_key, None)
        if not deploy_info:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown deploy session.'}

        if deploy_info.error:
            LOG.error(deploy_info.error)
            response.status_int = 400
            return {'ok': False, 'msg': deploy_info.error}

        if not deploy_info.done:
            return {
                    'ok': True,
                    'data': {
                        'total': 1,
                        'processed': 0
                    }
                }

        if not deploy_info.hub_session:
            response.status_int = 404
            return {'ok': False, 'msg': 'No deploy session found.'}

        try:
            r = cls.hub_pool.request('POST',
                                     '/dynamic/upload/progress/%s' % deploy_info.hub_session,
                                     headers={'Cookie': deploy_info.hub_cookie},
                                     redirect=False)
        except (HTTPError, SSLError) as e:
            LOG.error(e)
            response.status_int = 500
            return {'ok': False, 'msg': 'Post-upload progress check failed.'}

        if r.status != 200:
            response.status_int = 500
            return {'ok': False, 'msg': 'Wrong Hub answer.'}

        r_data = json_loads(r.data)
        # pylint: disable=E1103
        progress = int(r_data.get('progress', -1))
        upload_info = str(r_data.get('info', ''))
        failed = r_data.get('failed', False)
        # pylint: enable=E1103

        if failed:
            response.status_int = 500
            return {'ok': False, 'msg': 'Post-upload processing failed: %s' % upload_info}
        if -1 == progress:
            response.status_int = 500
            return {'ok': False, 'msg': 'Invalid post-upload progress.'}
        if 100 <= progress:
            del cls._deploying[deploy_key]

            try:
                cls.hub_pool.request('POST',
                                     '/dynamic/logout',
                                     headers={'Cookie': deploy_info.hub_cookie},
                                     redirect=False)
            except (HTTPError, SSLError) as e:
                LOG.error(e)

            try:
                game = form['local']
            except KeyError:
                response.status_int = 400
                return {'ok': False, 'msg': 'Wrong request.'}

            game = get_game_by_slug(game)
            if game:
                game.set_deployed()

        return {
            'ok': True,
            'data': {
                'total': 100,
                'processed': progress,
                'msg': upload_info
            }
        }
    # pylint: enable=R0911

    @classmethod
    @jsonify
    def cancel(cls):
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'

        form = request.params
        try:
            hub_project = form['project']
            hub_version = form['version']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing deploy information.'}

        deploy_key = hub_project + hub_version
        deploy_info = cls._deploying.get(deploy_key, None)
        if not deploy_info:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown deploy session.'}

        deploy_info.cancel()

        del cls._deploying[deploy_key]

        try:
            cls.hub_pool.request('POST',
                                 '/dynamic/logout',
                                 headers={'Cookie': deploy_info.hub_cookie},
                                 redirect=False)
        except (HTTPError, SSLError) as e:
            LOG.error(e)

        return {'ok':True, 'data':''}


    @classmethod
    @jsonify
    def check(cls, slug):

        # get game
        game = get_game_by_slug(slug)

        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug.'}

        try:
            game.load()
        except GameError:
            response.status_int = 405
            return {'ok': False, 'msg': 'Can\'t deploy a temporary game.'}

        # check if game is deployable
        complete, issues = game.check_completeness()
        if not complete:
            response.status_int = 400
            return {'ok': False, 'msg': issues}

        issues, critical = game.validate_yaml()
        if not issues:
            return {'ok': True, 'msg': ''}
        elif critical:
            response.status_int = 400
        return {'ok': False, 'msg': issues}
