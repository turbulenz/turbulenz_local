# Copyright (c) 2011-2012 Turbulenz Limited

import logging
LOG = logging.getLogger(__name__)

from re import compile as regex_compile
from time import time as time
from os import listdir, remove as remove_file
from os.path import join as join_path, splitext, exists as path_exists

from threading import Lock

# pylint: disable=F0401
from pylons import config
import yaml
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, create_dir
from turbulenz_local.lib.tools import create_id
from turbulenz_local.lib.exceptions import BadRequest, NotFound, Forbidden

class CompareAndSetInvalidToken(Exception):
    pass

class DataShare(object):

    read_only = 0
    read_and_write = 1
    valid_access_levels = [read_only, read_and_write]

    validate_key = regex_compile('^[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*$')

    def __init__(self, game):
        self.game = game
        self.lock = Lock()

        self.datashare_id = None
        # owners username
        self.owner = None
        self.created = None
        # the usernames of the joined players (includes owner)
        self.users = []

        self.joinable = None
        self.path = None
        self.store = {}
        self.deleted = False

    @classmethod
    def create(cls, game, owner):
        datashare = DataShare(game)
        with datashare.lock:
            datashare.datashare_id = create_id()
            datashare.owner = owner.username
            datashare.users = [owner.username]
            datashare.created = time()
            datashare.joinable = True
            datashare.write()
            return datashare

    @classmethod
    def from_file(cls, game, datashare_id):
        datashare = DataShare(game)
        with datashare.lock:
            datashare.datashare_id = datashare_id
            datashare.load()
            return datashare

    def datashare_access(self, user):
        username = user.username
        if username not in self.users:
            raise Forbidden('User "%s" has not joined '
                'data-share with id "%s"' % (username, self.datashare_id))

    def join(self, user):
        with self.lock:
            if self.deleted:
                raise NotFound('No data share with id "%s"' % self.datashare_id)
            if not self.joinable:
                raise Forbidden('Data share with id "%s" is not joinable' % self.datashare_id)
            if user.username not in self.users:
                self.users.append(user.username)
            self.write()

    def leave(self, user):
        with self.lock:
            try:
                self.users.remove(user.username)
            except ValueError:
                raise Forbidden('Cannot leave datashare "%s" current user has not joined' % self.datashare_id)
            if len(self.users) == 0:
                self._delete()
            else:
                self.write()

    def _delete(self):
        try:
            remove_file(self.path)
        except OSError:
            pass
        self.deleted = True

    def delete(self):
        with self.lock:
            self._delete()

    def get_path(self):
        if self.path is not None:
            return self.path

        try:
            path = config['datashare_db']
        except KeyError:
            LOG.error('datashare_db path config variable not set')
            raise

        path = get_absolute_path(join_path(path, self.game.slug, self.datashare_id + '.yaml'))
        self.path = path
        return path

    def load(self):
        path = self.get_path()
        if not path_exists(path):
            raise NotFound('No data share with id "%s"' % self.datashare_id)
        try:
            with open(path, 'r') as f:
                yaml_data = yaml.load(f)
                self.owner = yaml_data['owner']
                self.created = yaml_data['created']
                self.users = yaml_data['users']
                self.store = yaml_data['store']
                self.joinable = yaml_data['joinable']

        except (IOError, KeyError, yaml.YAMLError) as e:
            LOG.error('Failed loading datashare file "%s": %s', self.path, str(e))
            raise

    def write(self):
        path = self.get_path()
        try:
            with open(path, 'w') as f:
                yaml.dump(self.to_dict(), f)
        except IOError as e:
            LOG.error('Failed writing datashare file "%s": %s', self.path, str(e))
            raise

    def to_dict(self):
        return {
            'owner': self.owner,
            'created': self.created,
            'users': self.users,
            'joinable': self.joinable,
            'store': self.store
        }

    def summary_dict(self):
        return {
            'id': self.datashare_id,
            'owner': self.owner,
            'created': self.created,
            'joinable': self.joinable,
            'users': self.users
        }

    def key_summary_dict(self, key):
        store = self.store[key]
        return {
            'key': key,
            'ownedBy': store['ownedBy'],
            'access': store['access']
        }

    def _validate_access(self, access):
        try:
            access = int(access)
        except ValueError:
            raise BadRequest('Access level invalid. Access must be an integer.')

        if access not in self.valid_access_levels:
            raise BadRequest('Access level invalid. Must be one of %s' % str(self.valid_access_levels))
        return access

    def _set(self, key, value, owner, access):
        if value == '':
            try:
                del self.store[key]
            except KeyError:
                pass
            token = ''
        else:
            token = create_id()
            self.store[key] = {
                'ownedBy': owner,
                'value': value,
                'access': access,
                'token': token
            }
        self.write()
        return token

    def set(self, user, key, value):
        with self.lock:
            self.datashare_access(user)
            key = str(key)
            if not self.validate_key.match(key):
                raise BadRequest('Key can only contain alphanumeric characters hyphens and dots')

            if key in self.store:
                key_store = self.store[key]

                if key_store['access'] != self.read_only:
                    raise Forbidden('Forbidden: Key "%s" is read and write access'
                                    '(must use compare and set for read and write keys)' % key,
                                       {'reason': 'read_and_write'})
                owner = key_store['ownedBy']
                if owner != user.username:
                    raise Forbidden('Forbidden: Key "%s" is read only' % key, {'reason': 'read_only'})
            else:
                owner = user.username
            return self._set(key, value, owner, self.read_only)

    def compare_and_set(self, user, key, value, token):
        with self.lock:
            self.datashare_access(user)

            key = str(key)
            if not self.validate_key.match(key):
                raise BadRequest('Key can only contain alphanumeric characters hyphens and dots')

            if key in self.store:
                key_store = self.store[key]

                if key_store['access'] != self.read_and_write:
                    raise Forbidden('Forbidden: Key "%s" is read only access (must use set for read only keys)' % key,
                                       {'reason': 'read_only'})
                owner = key_store['ownedBy']

                # if the key is in the store then check its token
                if key_store['token'] != token:
                    raise CompareAndSetInvalidToken()
            else:
                owner = user.username
                # if the key is missing from the store make sure the token is unset
                if token:
                    raise CompareAndSetInvalidToken()

            return self._set(key, value, owner, self.read_and_write)

    def get(self, user, key):
        with self.lock:
            self.datashare_access(user)
            if not isinstance(key, unicode):
                raise BadRequest('Key must be a string')

            if not self.validate_key.match(key):
                raise BadRequest('Key can only contain alphanumeric characters hyphens and dots')

            return self.store.get(key)

    def get_keys(self, user):
        with self.lock:
            self.datashare_access(user)
            return [self.key_summary_dict(key) for key in self.store.iterkeys()]

    def set_joinable(self, user, joinable):
        with self.lock:
            self.datashare_access(user)
            self.joinable = joinable
            self.write()

    def reload(self):
        with self.lock:
            try:
                self.load()
            except NotFound:
                self._delete()


class GameDataShareList(object):

    def __init__(self, game):
        self.game = game
        self.datashares = {}
        self.lock = Lock()

        self.path = self.create_path()

    def create_path(self):
        try:
            path = config['datashare_db']
        except KeyError:
            LOG.error('datashare_db path config variable not set')
            raise

        # Create datashare folder
        path = join_path(path, self.game.slug)
        if not create_dir(path):
            LOG.error('DataShare path \"%s\" could not be created.', path)
            raise IOError('DataShare path \"%s\" could not be created.' % path)
        return get_absolute_path(path)

    def get_datashare_ids(self):
        try:
            return [splitext(filename)[0] for filename in listdir(self.path)]
        except OSError:
            self.create_path()
            return []

    def load_all(self):
        for datashare_id in self.get_datashare_ids():
            self.load_id(datashare_id)

    def load_id(self, datashare_id):
        if datashare_id in self.datashares:
            return self.datashares[datashare_id]

        datashare = DataShare.from_file(self.game, datashare_id)
        self.datashares[datashare_id] = datashare
        return datashare

    def find(self, user, username_to_find=None):
        with self.lock:
            self.load_all()

            result = []
            for datashare in self.datashares.itervalues():
                # only display joinable datashares or datashares that the current user is already joined to
                if datashare.joinable or user.username in datashare.users:
                    if username_to_find == None or username_to_find in datashare.users:
                        result.append(datashare)
                        result.sort(key=lambda a: -a.created)
                        if len(result) > 64:
                            del result[64]
            return result

    def get(self, datashare_id):
        with self.lock:
            return self.load_id(datashare_id)

    def create_datashare(self, user):
        with self.lock:
            datashare = DataShare.create(self.game, user)
            self.datashares[datashare.datashare_id] = datashare
            return datashare

    def leave_datashare(self, user, datashare_id):
        with self.lock:
            datashare = self.load_id(datashare_id)
            datashare.leave(user)
            if datashare.deleted:
                del self.datashares[datashare.datashare_id]

    def remove_all(self):
        with self.lock:
            self.load_all()
            for datashare in self.datashares.itervalues():
                datashare.delete()
            self.datashares = {}

    def reset_all(self):
        with self.lock:
            deleted_datashares = []
            for datashare in self.datashares.itervalues():
                datashare.reload()
                if datashare.deleted:
                    deleted_datashares.append(datashare.datashare_id)

            for datashare_id in deleted_datashares:
                del self.datashares[datashare_id]


class DataShareList(object):
    game_datashares = {}

    @classmethod
    def load(cls, game):
        game_datashare = GameDataShareList(game)
        cls.game_datashares[game.slug] = game_datashare
        return game_datashare


    @classmethod
    def get(cls, game):
        try:
            return cls.game_datashares[game.slug]
        except KeyError:
            return cls.load(game)

    # forces a reload of all files
    @classmethod
    def reset(cls):
        for game_datashare in cls.game_datashares.itervalues():
            game_datashare.reset_all()
