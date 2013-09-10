# Copyright (c) 2010-2011,2013 Turbulenz Limited

import logging
import yaml

from pylons import config

# pylint: disable=F0401
from paste.deploy.converters import asbool
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path
from turbulenz_local.models.metrics import MetricsSession
from turbulenz_local.models.game import Game, GameError, GameNotFoundError
from turbulenz_local.models.gamedetails import SlugDetail
from turbulenz_local.lib.deploy import Deployment

LOG = logging.getLogger(__name__)


class SlugError(Exception):
    pass

class GameList(object):
    _instance = None    # Singleton instance
    _reload = False     # Flag to be set if the list should be reloaded

    @classmethod
    def get_instance(cls):
        """
        Return an instance of GameList.
        Effectively implement a singleton pattern
        """
        if cls._instance is None or cls._reload:
            cls._instance = GameList()
            cls._reload = False
        return cls._instance


    def __init__(self):
        # create a dictionary {slug: game} to index games and
        # to keep track of the slugs already in use
        self._slugs = {}
        self._load_games()


    def list_all(self):
        return self._slugs.values()

    def _load_games(self):
        paths = load_paths(config['games.yaml'])
        if len(paths) != len(set(paths)):
            LOG.warn('duplicate paths in games.yaml found')

        games_root = config['games_root']
        deploy_enable = asbool(config.get('deploy.enable', False))

        for path in set(paths):
            try:
                game = Game(self, path, games_root=games_root, deploy_enable=deploy_enable)

            except GameError, e:
                LOG.error('error loading game from %s: %s', path, e)
            else:
                if game.slug in self._slugs.keys():
                    new_slug = self.make_slug_unique(game.slug)
                    game.slug = SlugDetail(new_slug)
                self._slugs[game.slug] = game
                LOG.info('game loaded from %s', path)


    def _reload_game(self, slug):

        if slug in self._slugs:
            path = self._slugs.get(slug).path

            games_root = config['games_root']
            deploy_enable = asbool(config.get('deploy.enable', False))

            try:
                game = Game(self, path, games_root=games_root, deploy_enable=deploy_enable)

            except GameError, e:
                LOG.error('error loading game from %s: %s', path, e)
            else:
                self._slugs[game.slug] = game


    def change_slug(self, old_slug, new_slug):
        if old_slug is not None and new_slug is not None:
            try:
                game = self._slugs[old_slug]
                del(self._slugs[old_slug])
                if new_slug in self._slugs.keys():
                    new_slug = SlugDetail(self.make_slug_unique(new_slug))
                    game.slug = new_slug
                self._slugs[new_slug] = game
            except KeyError:
                LOG.error('Error swapping slugs:' + old_slug + ' for ' + new_slug)
            else:
                MetricsSession.rename(old_slug, new_slug)
                cache_dir = config.get('deploy.cache_dir', None)
                Deployment.rename_cache(cache_dir, old_slug, new_slug)


    def save_game_list(self):
        """
        Save the list of games
        """
        game_paths = [game.path.encode('utf-8')\
                        for game in self._slugs.values()\
                        if game.path.is_correct()]

        try:
            f = open(config['games.yaml'], 'w')
            try:
                yaml.dump(game_paths, f)
            finally:
                f.close()
        except IOError, e:
            LOG.warn(str(e))


    def add_game(self):
        """
        Adds a temporary game to game_list.
        """
        slug = self.make_slug_unique('new-game')
        games_root = config['games_root']
        deploy_enable = asbool(config.get('deploy.enable', False))
        game = Game(self, slug=slug, games_root=games_root, deploy_enable=deploy_enable)
        self._slugs[slug] = game
        return game


    def delete_game(self, slug):
        """
        Deletes the game from the game list in games.yaml
        """
        try:
            del(self._slugs[slug])
        except KeyError:
            raise GameNotFoundError('Game not found: %s' % slug)
        else:
            self.save_game_list()


    def slug_in_use(self, slug, excepting=None):
        """
        Return True if the given slug is already being used in the GameList.
        Otherwise, or if the using game is equal to the one given as exception
        return False
        """
        if excepting is not None:
            return slug in self._slugs.keys() and self._slugs[slug] is not excepting
        else:
            return slug in self._slugs.keys()


    def path_in_use(self, query_path):
        """
        Return True if the given path is already being used in the GameList.
        Otherwise False.
        """
        # turn path absolute
        query_path = get_absolute_path(query_path)

        # check all games...
        for game in self._slugs.itervalues():
            # ... that have a path ...
            test_path = game.path
            if test_path is not None:

                # .. if they are using the given path
                test_path = get_absolute_path(test_path)
                if query_path ==  test_path:
                    return True

        return False


    def make_slug_unique(self, slug):
        """
        Makes sure the given slug is unique in the gamelist by attaching a counter
        to it if necessary.
        """
        existing_slugs = self._slugs.keys()
        counter = 1
        new_slug = slug
        while counter < 1000000:
            if new_slug in existing_slugs:
                new_slug = '%s-%i' % (slug, counter)
                counter += 1
            else:
                return new_slug
        raise SlugError('Exception when trying to make slug \'%s\' unique' % slug)


    def get_slugs(self):
        return self._slugs.keys()

    def get_by_slug(self, slug, reload_game=False):
        if reload_game:
            self._reload_game(slug)
        return self._slugs.get(slug)


#######################################################################################################################

def get_slugs():
    return GameList.get_instance().get_slugs()

def get_games():
    return GameList.get_instance().list_all()

def get_game_by_slug(slug, reload_game=False):
    return GameList.get_instance().get_by_slug(slug, reload_game)

def is_existing_slug(slug):
    return GameList.get_instance().slug_in_use(slug)

def load_paths(games_file):
    """
    Read game paths from YAML file.
    """
    try:
        f = open(games_file, 'r')
        try:
            paths = yaml.load(f)
        finally:
            f.close()
    except IOError, e:
        LOG.error('Exception when loading \'games.yaml\': %s', str(e))
        return []
    if paths is None:
        LOG.warn('No paths found in \'games.yaml\'')
        return []
    paths = [str(path) for path in paths]
    return paths
