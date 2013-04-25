# Copyright (c) 2011-2013 Turbulenz Limited
from time import time
from logging import getLogger
from weakref import WeakValueDictionary
from socket import TCP_NODELAY, IPPROTO_TCP

from tornado.web import RequestHandler

from turbulenz_local.lib.websocket import WebSocketHandler


# pylint: disable=R0904,W0221
class MultiplayerHandler(WebSocketHandler):

    log = getLogger('MultiplayerHandler')

    sessions = {}

    def __init__(self, application, request, **kwargs):
        WebSocketHandler.__init__(self, application, request, **kwargs)
        self.session_id = None
        self.client_id = None
        self.session = None
        self.version = None

    def _log(self):
        pass

    def select_subprotocol(self, subprotocols):
        if 'multiplayer' in subprotocols:
            return 'multiplayer'
        return None

    def allow_draft76(self):
        return True

    def open(self, session_id, client_id):
        socket = self.stream.socket
        socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        remote_address = "%s:%u" % socket.getpeername()
        version = self.request.headers.get("Sec-WebSocket-Version")
        self.log.info('New client from "%s" joins session "%s" with id "%s". Sec-WebSocket-Version: %s',
                      remote_address,
                      session_id,
                      client_id,
                      version)
        self.session_id = session_id
        self.client_id = client_id
        session = self.sessions.get(session_id, None)
        if session is None:
            self.sessions[session_id] = session = WeakValueDictionary()
        session[client_id] = self
        self.session = session
        if version in ("7", "8", "13"): #frame format for these versions is identical for us
            self.version = 8
        else:
            self.version = version

    def on_message(self, message):
        #self.log.info(message)

        session = self.session
        if session is not None:

            if isinstance(message, unicode):
                message = message.encode("utf-8")

            separator_index = message.find(':')
            if separator_index < 1:
                if separator_index == -1:
                    message = self.client_id + ':' + message
                else: # separator_index == 0
                    message = self.client_id + message
                clients = [client for client in session.itervalues() if client != self]
            else:
                destination = message[:separator_index]
                message = self.client_id + message[separator_index:]
                session_get = session.get
                clients = []
                for client_id in destination.split(','):
                    # Passing self as default allows us to cover both errors and self
                    client = session_get(client_id, self)
                    if client != self:
                        clients.append(client)

            version = self.version
            frame = self.ws_connection.create_frame(message)
            for client in clients:
                try:
                    if version == client.version:
                        client.ws_connection.stream.write(frame)
                    else:
                        client.ws_connection.stream.write(client.ws_connection.create_frame(message))
                except IOError:
                    client_id = client.client_id
                    self.log.info('Client "%s" write failed.', client_id)
                    client.session_id = None
                    client.session = None
                    del session[client_id]
                    self.notify_client_left(self.session_id, client_id)

            try:
                if len(session) == 0:
                    session_id = self.session_id
                    self.session_id = None
                    self.session = None
                    del self.sessions[session_id]
                    self.log.info('Deleted empty session "%s".', session_id)
            except KeyError:
                pass

    def on_close(self):
        session = self.session
        if session is not None:
            self.session = None

            session_id = self.session_id
            client_id = self.client_id

            self.log.info('Client "%s" left session "%s".', client_id, session_id)

            try:
                del session[client_id]

                if len(session) == 0:
                    self.session_id = None
                    del self.sessions[session_id]
                    self.log.info('Deleted empty session "%s".', session_id)
            except KeyError:
                pass

            self.notify_client_left(session_id, client_id)

    @classmethod
    def session_status(cls, session_id):

        session = cls.sessions.get(session_id, None)
        if session is None:
            return None

        return session.iterkeys()

    @classmethod
    def merge_sessions(cls, session_id_a, session_id_b):

        cls.log.info('Merging sessions "%s" and "%s"',
                     session_id_a, session_id_b)

        sessions = cls.sessions
        session_a = sessions.get(session_id_a, None)
        session_b = sessions.get(session_id_b, None)
        if session_a is None or session_b is None:
            return False

        if len(session_a) < len(session_b):
            session_b.update(session_a)

            for client in session_a.itervalues():
                client.session = session_b
                client.session_id = session_id_b

            sessions[session_id_a] = session_b

        else:
            session_a.update(session_b)

            for client in session_b.itervalues():
                client.session = session_a
                client.session_id = session_id_a

            sessions[session_id_b] = session_a

        return True

    @classmethod
    def notify_client_left(cls, session_id, client_id):
        from turbulenz_local.controllers.apiv1.multiplayer import MultiplayerController
        MultiplayerController.remove_player(session_id, client_id)


class MultiplayerStatusHandler(RequestHandler):

    def set_default_headers(self):
        self.set_header('Server', 'tz')

    def get(self):
        response_data = '{"ok":true}'
        self.set_header('Cache-Control', 'public, max-age=0')
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        self.set_header("Content-Length", str(len(response_data)))
        self.set_header("Etag", int(time()))
        self.write(response_data)


class SessionStatusHandler(RequestHandler):

    def set_default_headers(self):
        self.set_header('Server', 'tz')

    def get(self, session_id):

        client_ids = MultiplayerHandler.session_status(session_id)

        if client_ids is None:
            response_data = '{"ok":false}'
            self.set_status(404)
        else:
            response_data = '{"ok":true,"data":{"playerids":[' + ','.join(client_ids) + ']}}'

        self.set_header('Cache-Control', 'private, max-age=0')
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        self.set_header("Content-Length", str(len(response_data)))
        self.set_header("Etag", int(time()))
        self.write(response_data)
# pylint: enable=R0904
