# Copyright (c) 2012-2013 Turbulenz Limited

from logging import getLogger
from os.path import exists, join as path_join
from threading import Lock

# pylint: disable=F0401
import yaml
from pylons import config
# pylint: enable=F0401

from pylons import request, response

from turbulenz_local.models.user import User
from turbulenz_local.tools import get_absolute_path
from turbulenz_local.lib.exceptions import BadRequest
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
        self.lock = Lock()
        self._read_users()

    def _add_user(self, user_info):
        user = User(user_info)
        self.users[user.username] = user
        return user

    def to_dict(self):
        users = [u.to_dict() for u in self.users.values()]
        # order the default users after the standard ones for easier editing
        try:
            users = sorted(users, key=lambda u: u.default)
        except AttributeError:
            pass
        return {
            'users': users
        }

    def _write_users(self):
        yaml_obj = self.to_dict()
        path = config['user.yaml']
        try:
            with open(path, 'w') as f:
                yaml.dump(yaml_obj, f)
        except IOError as e:
            LOG.error('Failed writing users: %s', str(e))

    def _read_users(self):
        do_save = False
        try:
            path = config['user.yaml']
        except KeyError:
            LOG.error('Config variable not set for path to "user.yaml"')

        if exists(get_absolute_path(path)):
            try:
                f = open(path, 'r')
                try:
                    user_info = yaml.load(f)
                    if user_info is not None:
                        if 'users' in user_info:
                            for u in user_info['users']:
                                user = self._add_user(u)
                        else:
                            user = self._add_user(user_info)
                            do_save = True
                finally:
                    f.close()
            except IOError as e:
                LOG.error('Failed loading users: %s', str(e))
        else:
            self._add_user(User.default_username)
            do_save = True

        try:
            path = path_join(CONFIG_PATH, 'defaultusers.yaml')
            f = open(path, 'r')
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
            LOG.error('Failed loading default users: %s', str(e))
        except KeyError:
            LOG.error('Username missing for default user "defaultusers.yaml"')
        except ValueError:
            LOG.error('Username invalid for default user "defaultusers.yaml"')

        if do_save:
            self._write_users()

    def get_user(self, username):
        username_lower = username.lower()
        with self.lock:
            try:
                return self.users[username_lower]
            except KeyError:
                LOG.info('No user with username "%s" adding user with defaults', username)
                try:
                    user = self._add_user(username_lower)
                    self._write_users()
                    return user
                except ValueError as e:
                    raise BadRequest(str(e))

    def get_current_user(self):
        username = request.cookies.get('local')
        if username:
            return self.get_user(username)
        else:
            return self.login_user(User.default_username)

    def login_user(self, username_lower):
        with self.lock:
            if username_lower in self.users:
                user = self.users[username_lower]
            else:
                try:
                    user = self._add_user(username_lower)
                    self._write_users()
                except ValueError as e:
                    raise BadRequest(str(e))

        # 315569260 seconds = 10 years
        response.set_cookie('local', username_lower, httponly=False, max_age=315569260)
        return user


def get_user(username):
    return UserList.get_instance().get_user(username)


def get_current_user():
    return UserList.get_instance().get_current_user()


def login_user(username):
    return UserList.get_instance().login_user(username)
