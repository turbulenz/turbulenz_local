# Copyright (c) 2012-2013 Turbulenz Limited

from logging import getLogger

# pylint: disable=F0401
from pylons import config
import yaml
# pylint: enable=F0401

from os import remove, listdir, rmdir
from os.path import join as join_path, exists as path_exists
from threading import Lock

from turbulenz_local.models.userlist import get_user
from turbulenz_local.tools import get_absolute_path, create_dir

LOG = getLogger(__name__)


class GameProfileError(Exception):
    pass


class GameProfile(object):

    def __init__(self, user, game):
        self.lock = Lock()
        self.game = game
        self.user = user

        try:
            path = config['gameprofile_db']
        except KeyError:
            LOG.error('gameprofile_db path config variable not set')
            return

        # Create gameprofile folder and user folder on the game path
        path = join_path(path, game.slug)
        if not create_dir(path):
            error_msg = 'User GameProfile path \"%s\" could not be created.' % path
            LOG.error(error_msg)
            raise GameProfileError(error_msg)
        self.path = get_absolute_path(path)

        self.defaults = {}
        default_yaml_path = unicode(get_absolute_path(join_path(game.path, 'defaultgameprofiles.yaml')))
        if path_exists(default_yaml_path):
            with open(default_yaml_path, 'r') as f:
                try:
                    file_defaults = yaml.load(f)
                    self.defaults = dict((v['user'], v['value']) for v in file_defaults['profiles'])
                except (yaml.YAMLError, KeyError, TypeError) as e:
                    LOG.error('Failed loading default game profiles: %s', str(e))


    def get(self, usernames):
        path = self.path
        game_profiles = {}
        with self.lock:
            for username in usernames:
                profile_path = join_path(path, username + '.txt')
                try:
                    with open(unicode(profile_path), 'r') as fin:
                        value = fin.read()
                except IOError:
                    if username in self.defaults:
                        value = self.defaults[username]
                    else:
                        continue
                game_profiles[username] = {'value': value}
        return {'profiles': game_profiles}


    def set(self, value):
        profile_path = join_path(self.path, self.user.username + '.txt')
        with self.lock:
            try:
                with open(unicode(profile_path), 'w') as fout:
                    fout.write(value)
            except IOError as e:
                error_msg = 'Failed setting game profile: %s' % str(e)
                LOG.error(error_msg)
                raise GameProfileError(error_msg)
        return True


    def remove(self):
        profile_path = join_path(self.path, self.user.username + '.txt')
        with self.lock:
            try:
                if path_exists(profile_path):
                    remove(profile_path)
            except IOError as e:
                error_msg = 'Failed removing game profile: %s' % str(e)
                LOG.error(error_msg)
                raise GameProfileError(error_msg)
        return True

    @classmethod
    def remove_all(cls, game):
        try:
            path = join_path(config['gameprofile_db'], game.slug)
        except KeyError:
            LOG.error('gameprofile_db path config variable not set')
            return
        for f in listdir(path):
            split_ext = f.rsplit('.', 1)
            if split_ext[1] == 'txt':
                GameProfile(get_user(split_ext[0]), game).remove()
        try:
            rmdir(path)
        except OSError:
            pass    # Skip if directory in use or not empty
