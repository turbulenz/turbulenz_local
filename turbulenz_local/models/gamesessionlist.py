# Copyright (c) 2011-2013 Turbulenz Limited

import logging
from os.path import exists
from turbulenz_local.tools import get_absolute_path
from turbulenz_local.models.userlist import get_user
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.lib.tools import create_id
from turbulenz_local.lib.exceptions import InvalidGameSession
from threading import Lock
from time import time

# pylint: disable=F0401
import yaml
from pylons import config
# pylint: enable=F0401

LOG = logging.getLogger(__name__)


class GameSession(object):

    def __init__(self, game, user, gamesession_id=None, created=None):
        self.game = game
        self.user = user

        if gamesession_id is None:
            gamesession_id = create_id()
        self.gamesession_id = gamesession_id

        if created is None:
            created = int(time())
        self.created = created


    @classmethod
    def from_dict(cls, gamesession):
        game = get_game_by_slug(gamesession['game'])
        # remove any sessions pointing at old games / users
        if game:
            return GameSession(game,
                               get_user(gamesession['user']),
                               gamesession.get('gameSessionId', None),
                               gamesession.get('created', None))
        else:
            raise InvalidGameSession()


    def to_dict(self):
        try:
            return {
                'gameSessionId': self.gamesession_id,
                'user': self.user.username,
                'game': str(self.game.slug),
                'created': self.created
            }
        except AttributeError:
            raise InvalidGameSession()


class GameSessionList(object):
    _instance = None    # Singleton instance
    _reload = False     # Flag to be set if the list should be reloaded

    def __init__(self):
        self.lock = Lock()
        self.lock.acquire()
        self._sessions = {}
        path = config.get('gamesessions.yaml', 'gamesessions.yaml')
        self.path = get_absolute_path(path)
        self.load_sessions()
        self.lock.release()


    @classmethod
    def get_instance(cls):
        """
        Return an instance of GameList.
        Effectively implement a singleton pattern
        """
        if cls._instance is None or cls._reload:
            cls._instance = GameSessionList()
            cls._reload = False
        return cls._instance


    # for debugging
    def list(self):
        arraylist = [ ]
        for s in self._sessions.values():
            arraylist.append(s.to_dict())
        return arraylist


    def purge_sessions(self):
        self.lock.acquire()
        self.load_sessions()

        purge_time = time() - (1 * 86400)  # 1 day
        delete_sessions = []
        for string_id in self._sessions:
            s = self._sessions[string_id]
            if s.created < purge_time:
                delete_sessions.append(string_id)

        for s in delete_sessions:
            del self._sessions[s]

        self.write_sessions()
        self.lock.release()


    def load_sessions(self):
        path = self.path
        self._sessions = {}

        if exists(path):
            f = open(path, 'r')
            try:
                gamesessions = yaml.load(f)
                if isinstance(gamesessions, dict):
                    for string_id in gamesessions:
                        file_gamesession = gamesessions[string_id]
                        try:
                            self._sessions[string_id] = GameSession.from_dict(file_gamesession)
                        except InvalidGameSession:
                            pass
                else:
                    LOG.error('Gamesessions file incorrectly formated')
            except (yaml.parser.ParserError, yaml.parser.ScannerError):
                pass
            finally:
                f.close()


    def write_sessions(self):
        f = open(self.path, 'w')
        file_sessions = {}
        ghost_sessions = set()
        for string_id in self._sessions:
            session = self._sessions[string_id]
            try:
                file_sessions[string_id] = session.to_dict()
            except InvalidGameSession:
                ghost_sessions.add(string_id)

        # remove any invalid sessions
        for g in ghost_sessions:
            del self._sessions[g]

        try:
            yaml.dump(file_sessions, f)
        finally:
            f.close()


    def create_session(self, user, game):
        if (user is None or
            game is None):
            return None
        session = GameSession(game, user)
        self.lock.acquire()
        self._sessions[session.gamesession_id] = session
        self.write_sessions()
        self.lock.release()
        return session.gamesession_id


    def remove_session(self, string_id):
        self.lock.acquire()
        sessions = self._sessions
        if (string_id in sessions):
            del sessions[string_id]
            self.write_sessions()
            self.lock.release()
            return True
        else:
            self.lock.release()
            return False


    def get_session(self, string_id):
        self.lock.acquire()
        session = self._sessions.get(string_id, None)
        self.lock.release()
        return session


    def update_session(self, session):
        self.lock.acquire()
        self._sessions[session.gamesession_id] = session
        self.write_sessions()
        self.lock.release()
