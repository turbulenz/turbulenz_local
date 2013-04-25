# Copyright (c) 2012-2013 Turbulenz Limited

from logging import getLogger
from os.path import exists, join as path_join
from threading import Lock

# pylint: disable=F0401
import yaml
from pylons import config
# pylint: enable=F0401

from turbulenz_local.models.user import User
from turbulenz_local.tools import get_absolute_path
from turbulenz_local import CONFIG_PATH

LOG = getLogger(__name__)


class UserList(object):
    _instance = None    # Singleton instance
    _cls_lock = Lock()  # Class lock so only one instance is created

    @classmethod
    def get_instance(cls):
        with cls._cls_lock:
            if cls._instance is None:
                cls._instance = UserList()
            return cls._instance

    def __init__(self):
        self.users = {}
        self.active = None
        self.lock = Lock()
        self._read_users()

    def _add_user(self, user_info):
        user = User(user_info)
        self.users[user.username.lower()] = user
        return user

    def to_dict(self):
        users = [u.to_dict() for u in self.users.values()]
        # order the default users after the standard ones for easier editing
        try:
            users = sorted(users, key=lambda u: u.default)
        except AttributeError:
            pass
        return {
            'active': self.active,
            'users': users
        }

    def _write_users(self):
        yaml_obj = self.to_dict()
        path = config['user.yaml']
        try:
            with open(path, 'wt') as f:
                yaml.dump(yaml_obj, f)
        except IOError as e:
            LOG.error('Failed writing users: %s' % str(e))

    def _read_users(self):
        do_save = False
        try:
            path = config['user.yaml']
        except KeyError:
            LOG.error('Config variable not set for path to "user.yaml"')

        if exists(get_absolute_path(path)):
            try:
                f = open(path, 'rt')
                try:
                    user_info = yaml.load(f)
                    if 'users' in user_info:
                        self.active = user_info.get('active', None)
                        for u in user_info['users']:
                            user = self._add_user(u)
                            if self.active is None:
                                self.active = user.username
                    else:
                        user = self._add_user(user_info)
                        self.active = user.username
                        do_save = True
                finally:
                    f.close()
            except IOError as e:
                LOG.error('Failed loading users: %s' % str(e))
        else:
            self._add_user(User.default_username)
            self.active = User.default_username
            do_save = True

        try:
            path = path_join(CONFIG_PATH, 'defaultusers.yaml')
            f = open(path, 'rt')
            try:
                user_info = yaml.load(f)
                for u in user_info['users']:
                    # dont overwrite changed user settings
                    if u['username'].lower() not in self.users:
                        user = User(u, default=True)
                        username = user.username.lower()
                        self.users[username] = user
                        do_save = True
            finally:
                f.close()
        except IOError as e:
            LOG.error('Failed loading default users: %s' % str(e))
        except KeyError:
            LOG.error('Username missing for default user "defaultusers.yaml"')
        except ValueError:
            LOG.error('Username invalid for default user "defaultusers.yaml"')

        if do_save:
            self._write_users()

    def get_user(self, username):
        try:
            return self.users[username.lower()]
        except KeyError:
            LOG.info('No user with username %s adding user with defaults' % username)
            return self._add_user(username)

    def get_current_user(self):
        return self.users[self.active.lower()]

    def set_current_user(self, username):
        with self.lock:
            if username in self.users:
                self.active = username
                return self.users[username.lower()]
            else:
                self.active = username
                return self._add_user(username)


def get_user(username):
    return UserList.get_instance().get_user(username)


def get_current_user():
    return UserList.get_instance().get_current_user()


def set_current_user(username):
    UserList.get_instance().set_current_user(username)
