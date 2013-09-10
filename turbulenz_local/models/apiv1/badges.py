# Copyright (c) 2011-2013 Turbulenz Limited

import logging
LOG = logging.getLogger(__name__)

from os import access, R_OK
from os.path import join as join_path
from os.path import normpath as norm_path

from threading import Lock

from turbulenz_local.lib.exceptions import ApiException

# pylint: disable=F0401
from pylons import config
import yaml
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, create_dir

REQUIRED_BADGE_KEYS = ['key', 'title', 'description', 'points', 'shape']

class BadgesUnsupportedException(Exception):
    pass

class GameBadges(object):
    badges = []
    userbadges = {}
    userbadges_path = None

    def __init__(self, game):
        self.lock = Lock()

        self.game = game
        self.userbadges_path = None

        self.abs_game_path = get_absolute_path(game.path)

        try:
            self.lock.acquire()
            yaml_path = norm_path(get_absolute_path(join_path(game.path, 'badges.yaml')))
            if not access(yaml_path, R_OK):
                raise BadgesUnsupportedException()
            f = open(unicode(yaml_path), 'r')
            try:
                self.badges = yaml.load(f)

            finally:
                f.close()
        except IOError as e:
            LOG.error('Failed loading badges: %s', str(e))
            raise ApiException('Failed loading badges.yaml file %s' % str(e))
        finally:
            self.lock.release()


    def validate(self):
        result = []

        count = 0
        for badge in self.badges:
            count += 1
            errors = []
            # collect keys that are missing from the badge or are not filled in
            for key in REQUIRED_BADGE_KEYS:
                if not badge.get(key, False):
                    errors.append('missing key: "%s"' % key)

            icon_path = badge.get('imageresource', {}).get('icon', False)

            warnings = []
            if not icon_path:
                warnings.append('missing key: "imageresource.icon"')

            if icon_path:
                icon_path = join_path(self.abs_game_path, icon_path)
                if not access(icon_path, R_OK):
                    errors.append('icon "%s" couldn\'t be accessed.' % icon_path)

            identifier = badge.get('title', badge.get('key', 'Badge #%i' % count))

            if errors or warnings:
                result.append((identifier, {'errors': errors, 'warnings': warnings}))

        return result

    def _set_userbadges_path(self):
        if not self.userbadges_path:
            try:
                path = config['userbadges_db']
            except KeyError:
                LOG.error('badges_db path config variable not set')
                return

            if not create_dir(path):
                LOG.error('Game badges path \"%s\" could not be created.', path)
            self.userbadges_path = norm_path(join_path(get_absolute_path(path), self.game.slug) + '.yaml')

    def upsert_badge(self, ub):
        self._set_userbadges_path()
        self.lock.acquire()
        try:
            with open(unicode(self.userbadges_path), 'r') as f:
                self.userbadges = yaml.load(f)
        except IOError:
            pass

        try:
            #upsert the badge under the key of the user and the badgename
            if not ub['username'] in self.userbadges:
                self.userbadges[ub['username']] = {}
            self.userbadges[ub['username']][ub['badge_key']] = ub

            with open(unicode(self.userbadges_path), 'w') as f:
                yaml.dump(self.userbadges, f, default_flow_style=False)
        except IOError as e:
            LOG.error('Failed writing userbadges file "%s": %s', self.userbadges_path, str(e))
            raise Exception('Failed writing userbadge file %s %s' % (self.userbadges_path, str(e)))
        finally:
            self.lock.release()

    def find_userbadges_by_user(self, username):
        self._set_userbadges_path()
        self.lock.acquire()
        try:
            self.userbadges = {}

            f = open(unicode(self.userbadges_path), 'r')
            try:
                self.userbadges = yaml.load(f)
                f.close()

                return self.userbadges[username]

            except KeyError:
                return {}
            finally:
                f.close()
        except IOError:
            return {}
        finally:
            self.lock.release()

    def get_userbadge(self, username, key):
        self._set_userbadges_path()
        self.lock.acquire()
        try:
            self.userbadges = {}

            f = open(unicode(self.userbadges_path), 'r')
            try:
                self.userbadges = yaml.load(f)
                f.close()

                return self.userbadges[username][key]

            except (KeyError, TypeError):
                return {}
            finally:
                f.close()
        except IOError:
            return {}
        finally:
            self.lock.release()

    def get_badge(self, key):
        for badge in self.badges:
            if badge['key'] == key:
                return badge
        return None

class Badges(object):
    game_badges = None
    slug = None

    @classmethod
    def load(cls, game):
        if not cls.slug == game.slug or not cls.game_badges:
            cls.game_badges = GameBadges(game)
            cls.slug = game.slug
        return cls.game_badges

    @classmethod
    def get_singleton(cls, game):
        if not cls.slug == game.slug or not cls.game_badges:
            return cls.load(game)
        return cls.game_badges
