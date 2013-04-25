# Copyright (c) 2011-2013 Turbulenz Limited

from logging import getLogger
from threading import Lock
from time import time
from hashlib import sha1
from hmac import new as hmac_new
from base64 import urlsafe_b64encode

from pylons import request, response, config

from turbulenz_local.tools import get_remote_addr
from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.controllers import BaseController
from turbulenz_local.decorators import jsonify, postonly

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.multiplayer import MultiplayerSession, MultiplayerServer


LOG = getLogger(__name__)


def _calculate_registration_hmac(mpserver_secret, ip):
    h = hmac_new(mpserver_secret, str(ip), sha1)
    return urlsafe_b64encode(h.digest()).rstrip('=')

def _calculate_heartbeat_hmac(mpserver_secret, ip, num_players, active_sessions):
    h = hmac_new(mpserver_secret, str(ip), sha1)
    h.update(str(num_players))
    if active_sessions:
        h.update(str(active_sessions))
    return urlsafe_b64encode(h.digest()).rstrip('=')

def _calculate_client_hmac(secret, ip, session_id, client_id):
    h = hmac_new(secret, str(ip), sha1)
    h.update(str(session_id))
    h.update(str(client_id))
    return urlsafe_b64encode(h.digest()).rstrip('=')

def _calculate_session_hmac(mpserver_secret, ip, session_id):
    h = hmac_new(mpserver_secret, str(ip), sha1)
    h.update(str(session_id))
    return urlsafe_b64encode(h.digest()).rstrip('=')


class MultiplayerController(BaseController):
    """ MultiplayerController consists of all the multiplayer methods
    """

    multiplayer_service = ServiceStatus.check_status_decorator('multiplayer')

    secret = config.get('multiplayer.secret', None)

    lock = Lock()
    last_player_id = 0
    last_session_id = 0

    sessions = {}

    servers = {}

    ##
    ## FRONT CONTROLLER METHODS
    ##

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def create(cls, slug):

        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown game.'}

        try:
            num_slots = int(request.params['slots'])
            _ = request.params['gameSessionId'] # Check for compatibility with gamesite API which does use this
        except (KeyError, ValueError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        with cls.lock:

            cls.last_player_id += 1
            player_id = str(cls.last_player_id)

            sessions = cls.sessions

            cls.last_session_id += 1
            session_id = str(cls.last_session_id)

            server_address = None
            secret = None

            if cls.secret is not None:
                stale_time = time() - 80
                for ip, server in cls.servers.iteritems():
                    if stale_time < server.updated:
                        server_address = '%s:%d' % (ip, server.port)
                        secret = cls.secret
                        break

            session = MultiplayerSession(session_id, slug, num_slots, server_address, secret)

            LOG.info('Created session %s (%d slots)', session_id, num_slots)

            sessions[session_id] = session

            request_ip = get_remote_addr(request)

            session.add_player(player_id, request_ip)

            LOG.info('Player %s joins session %s', player_id, session_id)

            info = {'server': session.get_player_address(request.host, request_ip, player_id),
                    'sessionid': session_id,
                    'playerid': player_id,
                    'numplayers': session.get_num_players()}
            return {'ok': True, 'data': info}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def join(cls):
        params = request.params
        try:
            session_id = params['session']
            _ = request.params['gameSessionId'] # Check for compatibility with gamesite API which does use this
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        try:
            session = cls.sessions[session_id]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        with cls.lock:

            session.update_status()

            request_ip = get_remote_addr(request)

            player_id = params.get('player', None)
            if player_id is None:
                cls.last_player_id += 1
                player_id = str(cls.last_player_id)
            else:
                stored_ip = session.get_player_ip(player_id)
                if stored_ip is not None and request_ip != stored_ip:
                    response.status_int = 401
                    return {'ok': False}

            if session.can_join(player_id):
                session.add_player(player_id, request_ip)

                LOG.info('Player %s joins session %s', player_id, session_id)

                info = {'server': session.get_player_address(request.host, request_ip, player_id),
                        'sessionid': session_id,
                        'playerid': player_id,
                        'numplayers': session.get_num_players()}

                return {'ok': True, 'data': info}

            response.status_int = 409
            return {'ok': False, 'msg': 'No slot available.'}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def join_any(cls, slug):
        params = request.params
        try:
            _ = params['gameSessionId'] # Check for compatibility with gamesite API which does use this
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing game information.'}

        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown game.'}

        with cls.lock:

            cls.last_player_id += 1
            player_id = str(cls.last_player_id)

            sessions = cls.sessions
            session = session_id = None
            for existing_session in sessions.itervalues():
                if existing_session.game == slug:
                    existing_session.update_status()
                    if existing_session.can_join(player_id):
                        session = existing_session
                        session_id = existing_session.session_id
                        break

            if session is not None:
                request_ip = get_remote_addr(request)

                session.add_player(player_id, request_ip)

                LOG.info('Player %s joins session %s', player_id, session_id)

                info = {'server': session.get_player_address(request.host, request_ip, player_id),
                        'sessionid': session_id,
                        'playerid': player_id,
                        'numplayers': session.get_num_players()}
            else:
                # No session to join
                info = {}
            return {'ok': True, 'data': info}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def leave(cls):
        params = request.params
        try:
            session_id = params['session']
            player_id = params['player']
            _ = params['gameSessionId'] # Check for compatibility with gamesite API which does use this
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        sessions = cls.sessions
        try:
            session = sessions[session_id]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        with cls.lock:

            if session.has_player(player_id):

                request_ip = get_remote_addr(request)

                stored_ip = session.get_player_ip(player_id)
                if stored_ip is not None and request_ip != stored_ip:
                    response.status_int = 401
                    return {'ok': False}

                LOG.info('Player %s leaving session %s', player_id, session_id)

                session.remove_player(player_id)

                cls._clean_empty_sessions()

        return {'ok': True}


    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def make_public(cls):
        params = request.params
        try:
            session_id = params['session']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        sessions = cls.sessions
        try:
            session = sessions[session_id]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        session.public = True

        return {'ok': True}

    @classmethod
    @multiplayer_service
    @jsonify
    def list_all(cls):
        request_host = request.host

        sessions = []
        for session in cls.sessions.itervalues():
            session.update_status()
            sessions.append(session.get_info(request_host))

        return {'ok': True, 'data': sessions}

    @classmethod
    @jsonify
    def list(cls, slug):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown game.'}

        request_host = request.host

        sessions = []
        for session in cls.sessions.itervalues():
            if session.game == slug:
                session.update_status()
                sessions.append(session.get_info(request_host))

        return {'ok': True, 'data': sessions}

    @classmethod
    @multiplayer_service
    @jsonify
    def read(cls):
        params = request.params
        try:
            session_id = params['session']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        try:
            session = cls.sessions[session_id]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        session.update_status()

        return {'ok': True, 'data': session.get_info(request.host)}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def register(cls):
        remote_addr = get_remote_addr(request)

        try:
            params = request.params
            host = params.get('host', remote_addr)
            hmac = params['hmac']
            server = MultiplayerServer(params)
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing server information.'}
        except ValueError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Incorrect server information.'}

        calculated_hmac = _calculate_registration_hmac(cls.secret, remote_addr)
        if hmac != calculated_hmac:
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid server information.'}

        LOG.info('Multiplayer server registered from %s as %s:%d', remote_addr, host, server.port)

        cls.servers[host] = server

        return {'ok': True}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def heartbeat(cls):
        remote_addr = get_remote_addr(request)
        try:
            params = request.params
            host = params.get('host', remote_addr)
            num_players = params.get('numplayers')
            hmac = params['hmac']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing server information.'}

        calculated_hmac = _calculate_heartbeat_hmac(cls.secret, remote_addr, num_players, None)
        if hmac != calculated_hmac:
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid server information.'}

        try:
            server = cls.servers[host]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown server IP.'}

        try:
            server.update(request.params)
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing server information.'}
        except ValueError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Incorrect server information.'}

        #LOG.info('%s: %s', host, str(server))

        return {'ok': True}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def unregister(cls):
        remote_addr = get_remote_addr(request)

        params = request.params
        host = params.get('host', remote_addr)
        try:
            hmac = params['hmac']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        calculated_hmac = _calculate_registration_hmac(cls.secret, remote_addr)
        if hmac != calculated_hmac:
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid server information.'}

        try:
            server = cls.servers[host]
            del cls.servers[host]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown server IP.'}

        LOG.info('Multiplayer server unregistered from %s:%d', host, server.port)
        return {'ok': True}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def client_leave(cls):
        remote_addr = get_remote_addr(request)

        params = request.params
        try:
            session_id = params['session']
            player_id = params['client']
            hmac = params['hmac']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        calculated_hmac = _calculate_client_hmac(cls.secret, remote_addr, session_id, player_id)
        if hmac != calculated_hmac:
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid server information.'}

        sessions = cls.sessions
        try:
            session = sessions[session_id]
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        with cls.lock:

            if session.has_player(player_id):

                request_ip = get_remote_addr(request)

                stored_ip = session.get_player_ip(player_id)
                if stored_ip is not None and request_ip != stored_ip:
                    response.status_int = 401
                    return {'ok': False}

                LOG.info('Player %s left session %s', player_id, session_id)

                session.remove_player(player_id)

                cls._clean_empty_sessions()

        return {'ok': True}

    @classmethod
    @postonly
    @multiplayer_service
    @jsonify
    def delete_session(cls):
        remote_addr = get_remote_addr(request)

        params = request.params
        try:
            session_id = params['session']
            hmac = params['hmac']
        except KeyError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing session information.'}

        calculated_hmac = _calculate_session_hmac(cls.secret, remote_addr, session_id)
        if hmac != calculated_hmac:
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid server information.'}

        try:
            with cls.lock:
                del cls.sessions[session_id]
                LOG.info('Deleted empty session: %s', session_id)
        except KeyError:
            response.status_int = 404
            return {'ok': False, 'msg': 'Unknown session.'}

        return {'ok': True}

    @classmethod
    def _clean_empty_sessions(cls):
        # Needed because of merges
        sessions = cls.sessions
        to_delete = [session_id
                     for session_id, existing_session in sessions.iteritems()
                     if 0 == existing_session.get_num_players()]
        for session_id in to_delete:
            LOG.info('Deleting empty session: %s', session_id)
            del sessions[session_id]


    # Internal API used by internal mp server
    @classmethod
    def remove_player(cls, session_id, player_id):
        try:
            sessions = cls.sessions
            session = sessions[session_id]
            with cls.lock:
                if session.has_player(player_id):

                    LOG.info('Player %s left session %s', player_id, session_id)

                    session.remove_player(player_id)

                    cls._clean_empty_sessions()

        except KeyError:
            pass
