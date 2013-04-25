# Copyright (c) 2011-2013 Turbulenz Limited

from base64 import urlsafe_b64encode
from hmac import new as hmac_new
from hashlib import sha1
from urllib2 import urlopen, URLError
from simplejson import load as json_load
from time import time

from turbulenz_local.lib.multiplayer import MultiplayerHandler


def _calculate_new_client_hmac(secret, ip, session_id, client_id):
    h = hmac_new(secret, str(ip), sha1)
    h.update(session_id)
    h.update(client_id)
    return urlsafe_b64encode(h.digest()).rstrip('=')

def _calculate_merge_session_hmac(secret, session_id_a, session_id_b):
    h = hmac_new(secret, str(session_id_a), sha1)
    h.update(session_id_b)
    return urlsafe_b64encode(h.digest()).rstrip('=')


class MultiplayerSession(object):

    __slots__ = ('session_id', 'game', 'num_slots', 'players', 'public', 'server', 'secret')

    def __init__(self, session_id, game, num_slots, server, secret):
        self.session_id = session_id
        self.game = game
        self.num_slots = num_slots
        self.players = {}
        self.public = False
        self.server = server
        self.secret = secret

    def get_player_address(self, request_host, request_ip, player_id):
        if self.secret is not None:
            hmac = _calculate_new_client_hmac(self.secret, request_ip, self.session_id, player_id)
            return 'ws://%s/multiplayer/%s/%s/%s' % (self.server, self.session_id, player_id, hmac)
        else:
            return 'ws://%s/multiplayer/%s/%s' % (request_host, self.session_id, player_id)

    def can_join(self, player_id):
        players = self.players
        return player_id in players or len(players) < self.num_slots

    def add_player(self, player_id, ip):
        self.players[player_id] = ip

    def remove_player(self, player_id):
        try:
            del self.players[player_id]
        except KeyError:
            pass

    def has_player(self, player_id):
        return player_id in self.players

    def get_player_ip(self, player_id):
        return self.players.get(player_id, None)

    def get_num_players(self):
        return len(self.players)

    def get_max_num_players(self):
        return self.num_slots

    def can_merge(self, other):
        if self != other:
            if self.public and other.public:
                if self.game == other.game:
                    if self.server == other.server:
                        other.update_status()
                        return (len(self.players) + len(other.players)) <= min(self.num_slots, other.num_slots)
        return False

    def merge(self, other):
        merged = False
        if self.secret is None:
            merged = MultiplayerHandler.merge_sessions(self.session_id, other.session_id)
        else:
            hmac = _calculate_merge_session_hmac(self.secret, self.session_id, other.session_id)
            url = 'http://%s/api/v1/multiplayer/session/merge/%s/%s/%s' % (self.server,
                                                                           self.session_id,
                                                                           other.session_id,
                                                                           hmac)
            try:
                f = urlopen(url)
                try:
                    response = json_load(f)
                    # pylint: disable=E1103
                    merged = response['ok']
                    # pylint: enable=E1103
                finally:
                    f.close()
            except (URLError, KeyError):
                pass
        if merged:
            self.players.update(other.players)
        return merged

    def get_info(self, request_host):
        if self.secret is not None:
            server_address = self.server
        else:
            server_address = request_host
        return {
            '_id': self.session_id,
            'game': self.game,
            'numslots': self.num_slots,
            'players': self.players.keys(),
            'public': self.public,
            'server': server_address
        }

    def update_status(self):
        playerids = None

        if self.secret is None:
            playerids = MultiplayerHandler.session_status(self.session_id)
        else:
            url = 'http://%s/api/v1/multiplayer/status/session/%s' % (self.server, self.session_id)
            try:
                f = urlopen(url)
                try:
                    response = json_load(f)
                    # pylint: disable=E1103
                    if response['ok']:
                        data = response.get('data', None)
                        if data is not None:
                            playerids = data.get('playerids', None)
                    # pylint: enable=E1103
                finally:
                    f.close()
            except URLError:
                # Switch to internal server
                self.server = None
                self.secret = None
                return
            except KeyError:
                return

        playerids = set(playerids or [])
        players = self.players
        for player_id in players.keys():
            if player_id not in playerids:
                del players[player_id]


class MultiplayerServer(object):

    __slots__ = ('port', 'updated', 'numplayers')

    def __init__(self, params):
        self.port = int(params['port'])
        self.updated = time()
        self.numplayers = 0

    def update(self, params):
        self.numplayers = int(params['numplayers'])
        self.updated = time()
