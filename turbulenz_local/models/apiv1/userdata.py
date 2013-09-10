# Copyright (c) 2011-2013 Turbulenz Limited

import logging
import os

# pylint: disable=F0401
from pylons import config
# pylint: enable=F0401

from os.path import join as join_path

from turbulenz_local.tools import get_absolute_path, create_dir

LOG = logging.getLogger(__name__)


class UserDataPathError(Exception):
    pass


class UserDataError(Exception):
    pass


class UserDataKeyError(Exception):
    pass


class UserData(object):

    def __init__(self, session=None, game=None, user=None):
        if session is None:
            self.game = game
            self.user = user
        else:
            self.game = session.game
            self.user = session.user

        try:
            path = config['userdata_db']
        except KeyError:
            LOG.error('userdata_db path config variable not set')
            return

        # Create userdata folder and user folder on the game path
        path = join_path(path, self.game.slug, self.user.username)
        if not create_dir(path):
            raise UserDataPathError('User UserData path \"%s\" could not be created.' % path)
        self.path = get_absolute_path(path)


    def get_keys(self):
        key_files = os.listdir(self.path)
        list_array = []

        for key_file in key_files:
            try:
                f = open(unicode(join_path(self.path, key_file)), 'r')
                (key, ext) = os.path.splitext(key_file)
                if (ext == '.txt'):
                    try:
                        list_array.append(key)
                    finally:
                        f.close()
            except IOError, e:
                LOG.error('Failed listing userdata: %s', str(e))
                raise UserDataError

        # keys and values
        #for key_file in key_files:
        #    try:
        #        f = open(unicode(join_path(self.path, key_file)), 'r')
        #        (key, ext) = os.path.splitext(key_file)
        #        if (ext == '.txt'):
        #            try:
        #                list_array.append({
        #                    'key': key,
        #                    'value': f.read()
        #                    })
        #            finally:
        #                f.close()
        #    except IOError, e:
        #        LOG.error('Failed listing userdata: %s', str(e))
        #        raise UserDataError

        return list_array


    def exists(self, key):
        key_path = join_path(self.path, key + '.txt')
        return os.path.exists(key_path)


    def get(self, key):
        key_path = join_path(self.path, key + '.txt')
        try:
            f = open(unicode(key_path), 'r')
            try:
                value = f.read()
            finally:
                f.close()
        except IOError:
            raise UserDataKeyError
        return value


    def set(self, key, value):
        key_path = join_path(self.path, key + '.txt')
        try:
            f = open(unicode(key_path), 'w')
            try:
                f.write(value)
            finally:
                f.close()
        except IOError, e:
            LOG.error('Failed setting userdata: %s', str(e))
            raise UserDataError
        else:
            return True


    def remove(self, key):
        key_path = join_path(self.path, key + '.txt')
        try:
            if os.path.exists(key_path):
                os.remove(key_path)
            else:
                raise UserDataKeyError
        except IOError, e:
            LOG.error('Failed removing userdata: %s', str(e))
            raise UserDataError
        else:
            return True


    def remove_all(self):
        key_paths = os.listdir(self.path)

        for key_path in key_paths:
            (_, ext) = os.path.splitext(key_path)
            if (ext == '.txt'):
                try:
                    os.remove(unicode(join_path(self.path, key_path)))
                except IOError, e:
                    LOG.error('Failed removing userdata: %s', str(e))
                    raise UserDataError

        return True
