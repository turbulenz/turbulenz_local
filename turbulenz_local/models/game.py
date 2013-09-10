# Copyright (c) 2010-2013 Turbulenz Limited

import logging
import os
from os import listdir, access, R_OK
from os.path import join as join_path
from time import time, localtime, strftime

import json

# pylint: disable=F0401
import yaml
from paste.deploy.converters import asbool
# pylint: enable=F0401

from turbulenz_local.lib.exceptions import ApiException
from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.models.gamedetails import GameDetail, PathDetail, SlugDetail, ImageDetail, ListDetail, \
                                                   EngineDetail, AspectRatioDetail
from turbulenz_local.models.metrics import MetricsSession
from turbulenz_local.models.apiv1.badges import GameBadges, BadgesUnsupportedException
from turbulenz_local.models.apiv1.leaderboards import LeaderboardsList, LeaderboardError, \
                                                      LeaderboardsUnsupported
from turbulenz_local.models.apiv1.gamenotifications import GameNotificationKeysList, \
                                                           GameNotificationsUnsupportedException

from turbulenz_local.models.apiv1.store import StoreList, StoreError, \
                                                   StoreUnsupported
from turbulenz_local.tools import get_absolute_path, create_dir, load_json_asset


LOG = logging.getLogger(__name__)

class GameError(Exception):
    pass

class GameNotFoundError(GameError):
    pass

class GameDuplicateSlugError(GameError):
    pass

class GameSlugNotSpecifiedError(GameError):
    pass

class GamePathError(GameError):
    pass

class GamePathNotFoundError(GameError):
    pass

#######################################################################################################################

def read_manifest(game_path, manifest_name):
    """
    Try reading manifest game data in dictionary form from game_path.
    """
    try:
        game_path = get_absolute_path(game_path)
        game_path = join_path(game_path, manifest_name)
        f = open(unicode(game_path), 'r')
        try:
            data = yaml.load(f)
        finally:
            f.close()
    except IOError as e:
        LOG.error('Failed loading manifest: %s', str(e))
        raise GameError
    else:
        return data

def write_manifest(data, manifest_name):
    """
    Write the game metadata to a YAML manifest file
    """
    path = data.get('path')
    if not path:
        raise GamePathError('No path found in game data.\nData=' +\
                            '\n'.join(['%s:\t%s' % (k, v) for k, v in data.iteritems()]))
    path = get_absolute_path(path)

    # write the YAML data
    try:
        f = open(join_path(path, manifest_name), 'w')
        try:
            yaml.dump(data, f, default_flow_style=False)
        finally:
            f.close()
    except IOError as e:
        LOG.error('Failed writing manifest: %s', str(e))
        raise GamePathError('Failed writing manifest file.')

#######################################################################################################################

# pylint: disable=R0902
class Game(object):

    _executable_extensions = ('.html', '.htm', '.tzjs', '.canvas.js', '.swf')

    def __init__(self, game_list, game_path=None, slug=None, games_root=None, deploy_enable=False, manifest_name=None):
        self.game_list = game_list
        self.slug = None
        self.title = None
        self.path = None
        self.cover_art = ImageDetail(self, 'cover_art.jpg')
        self.title_logo = ImageDetail(self, 'title_logo.jpg')
        self.modified = None
        self.deployed = None
        self.is_temporary = True
        self.plugin_main = None
        self.canvas_main = None
        self.flash_main = None
        self.mapping_table = None
        self.deploy_files = None
        self.has_mapping_table = None
        self.engine_version = EngineDetail('')
        self.is_multiplayer = False
        self.aspect_ratio = AspectRatioDetail('')
        # if game_path is set, load data,
        # otherwise create a temporary game
        if manifest_name is None:
            self.manifest_name = 'manifest.yaml'
        else:
            self.manifest_name = manifest_name
        if game_path is not None:
            self.load(game_path, self.manifest_name)
        elif slug is not None:
            self.update({'slug': slug})
        self.games_root = games_root
        self.deploy_enable = deploy_enable

    def update(self, data):
        """
        Update the game object with the values supplied
        """
        self._set_slug(data)
        self._set_path(data)
        self._set_title(data)
        self._set_images(data)
        self._set_dates(data)
        self.plugin_main = GameDetail(data.get('plugin_main'))
        self.canvas_main = GameDetail(data.get('canvas_main'))
        self.flash_main = GameDetail(data.get('flash_main'))
        self.mapping_table = GameDetail(data.get('mapping_table'))
        self.deploy_files = ListDetail(data.get('deploy_files', []))
        self.engine_version = EngineDetail(data.get('engine_version'))
        self.is_multiplayer = asbool(data.get('is_multiplayer', False))
        self.aspect_ratio = AspectRatioDetail(data.get('aspect_ratio'))

    def _set_slug(self, data):
        old_slug = self.slug
        self.slug = SlugDetail(data.get('slug'))
        if old_slug and not old_slug == self.slug:
            self.game_list.change_slug(old_slug, self.slug)

    def _set_path(self, data):
        self.path = PathDetail(data.get('path'))

    def _set_title(self, data):
        self.title = GameDetail(data.get('title'))

    def _set_images(self, data):
        cover_art = data.get('cover_art', None)
        if cover_art:
            self.cover_art = ImageDetail(self, cover_art)
        title_logo = data.get('title_logo', None)
        if title_logo:
            self.title_logo = ImageDetail(self, title_logo)

    def _set_dates(self, data):
        self.modified = data.get('modified', 'Never')
        self.deployed = data.get('deployed', 'Never')

    def save(self, attrs):
        """
        Save this game object in persistent storage.
        """
        # check that there's a path in the given attributes
        if 'path' not in attrs.keys():
            raise GamePathNotFoundError('No Path given')
        # check that it can be used
        if not create_dir(attrs['path']):
            raise GamePathError('Path "%s" could not be created.' % attrs['path'])

        # update the game
        self.update(attrs)
        # update modified time
        t = localtime(time())
        self.modified = strftime("%H:%M | %d/%m/%Y", t)
        # trim unnecessary values and write game to manifest file
        write_manifest(self.to_dict(), self.manifest_name)
        # if the game has been saved, it's not temporary anymore
        self.is_temporary = False

    def load(self, game_path=None, manifest_name=None):
        """
        Update this game with data loaded from the manifest file at
        the specified path. If 'dataPath' is not provided, simply reload
        the game.
        """
        # make sure data_path is set
        if game_path is None:
            game_path = self.path
        if manifest_name is None:
            manifest_name = self.manifest_name
        # get data from manifest file...
        game_data = read_manifest(game_path, manifest_name)
        # and update it with the actual path
        game_data['path'] = game_path
        # update game with data
        self.update(game_data)
        # if the game can be loaded, it's not temporary anymore
        self.is_temporary = False

    def get_path(self):
        return self.path

    def to_dict(self):
        """
        Convert the current object to a dict, with properly encoded and
        formatted values for dumping
        """
        # grab all attributes that should be saved into a dict
        data = {
            'path': self.path,
            'title': self.title,
            'slug': self.slug,
            'is_temp': self.is_temporary,
            'cover_art': self.cover_art.image_path,
            'title_logo': self.title_logo.image_path,
            'modified': self.modified,
            'deployed': self.deployed,
            'plugin_main': self.plugin_main,
            'canvas_main': self.canvas_main,
            'flash_main': self.flash_main,
            'mapping_table': self.mapping_table,
            'deploy_files': self.deploy_files.items,
            'engine_version': self.engine_version,
            'is_multiplayer': self.is_multiplayer,
            'has_notifications': self.has_notifications,
            'aspect_ratio': self.aspect_ratio
        }
        # attempt to format the data correctly
        for k, v in data.iteritems():
            try:
                data[k] = v.encode('utf8')
            except (KeyError, AttributeError):
                pass
        return data

    #iterate through the directories and add files to list
    @classmethod
    def iterate_dir(cls, path, files, directories):
        abs_static_path = get_absolute_path(path)

        for file_name in listdir(abs_static_path):
            if os.path.isdir(os.path.join(abs_static_path, file_name)) != True:
                #file_name is not directory
                parts = path.split('/')
                if len(parts) > 2:
                    directory = parts[-1]
                else:
                    directory = ''

                files.append(_File(file_name, file_name, directory, os.path.join(abs_static_path, file_name)))
            else:
                if (file_name not in directories):
                    directories[file_name] = _File(file_name)

        return directories.values() + files

    #get the assets not on the mapping table directly from staticmax/ directory
    def get_static_files(self, game_path, request_path, path):
        static_path = os.path.join(game_path, path) #request_path, path)
        static_path_obj = PathDetail(static_path)

        files = [ ]
        directories = { }
        if static_path_obj.is_correct():
            files = self.iterate_dir(static_path_obj, files, directories)
        else:
            raise GamePathNotFoundError('Path not valid')

        if len(files) > 0:
            return files
        return [ ]

    #get assets on the mapping table
    def get_asset_list(self, request_path, path=''):
        if self.path.is_correct():
            game_path = self.path
            abs_game_path = get_absolute_path(game_path)

            # Load mapping table
            j = load_json_asset(os.path.join(game_path, self.mapping_table))
            if j:
                # pylint: disable=E1103
                mapping_table = j.get('urnmapping') or j.get('urnremapping', {})
                # pylint: enable=E1103
                self.has_mapping_table = True
                files = [ ]
                directories = { }
                len_path = len(path)
                if not path.endswith('/') and len_path > 0:
                    len_path += 1
                for k, v in mapping_table.iteritems():
                    if k.startswith(path):
                        parts = k[len_path:].split('/')
                        if len(parts) == 1:
                            abs_file_path = os.path.join(abs_game_path, request_path, v)
                            files.append(_File(parts[0], v, '%s/%s' % (request_path, v), abs_file_path))
                        else:
                            if parts[0] not in directories:
                                directories[parts[0]] = _File(parts[0])

                result = directories.values() + files
                if len(result) == 0:
                    raise GamePathNotFoundError('Asset path does not exist: %s' % path)

                return result

            else:
                self.has_mapping_table = False
                # !!! What do we expect if the user asks for Assets and there is no mapping table?
                return self.get_static_files(game_path, request_path, path)

        else:
            raise GamePathError('Game path not found: %s' % self.path)

    @property
    def has_metrics(self):
        return MetricsSession.has_metrics(self.slug)

    @property
    def has_assets(self):
        asset_list = self.get_asset_list('')
        return len(asset_list) > 0

    @property
    def has_notifications(self):
        try:
            GameNotificationKeysList.get(self)
        except GameNotificationsUnsupportedException:
            return False

        return True

    def get_versions(self):
        # if the game path is defined, find play-html files.
        versions = [ ]
        if self.path.is_correct():
            abs_path = get_absolute_path(self.path)
            slug = self.slug + '/'
            executable_extensions = self._executable_extensions
            flash_dict = None
            for file_name in listdir(abs_path):
                if file_name.endswith(executable_extensions):
                    version = { 'title': os.path.basename(file_name),
                                'url': slug + file_name }
                    if file_name.endswith('.swf'):
                        if flash_dict is None:
                            flash_dict = {}
                            flash_config_path = join_path(abs_path, 'flash.yaml')
                            if access(flash_config_path, R_OK):
                                f = open(unicode(flash_config_path), 'r')
                                try:
                                    flash_dict = yaml.load(f)
                                finally:
                                    f.close()
                        version['flash'] = flash_dict
                    versions.append(version)
        return versions

    def set_deployed(self):
        self.deployed = strftime("%H:%M | %d/%m/%Y", localtime(time()))
        write_manifest(self.to_dict(), self.manifest_name)

    def check_completeness(self):
        errors = []
        tmp = []
        if not self.deploy_enable:
            tmp.append('"deploy" is disabled.')
        if self.is_temporary:
            tmp.append('Game is temporary.')

        path = self.path
        if not path or not path.is_set():
            tmp.append('No path set.')
            path_correct = False
        else:
            path_correct = path.is_correct()
            if not path_correct:
                tmp.append('Incorrect path set.')

        if tmp:
            errors.append(('settings', {'errors': tmp}))
            tmp = []

        plugin_main = self.plugin_main
        canvas_main = self.canvas_main
        flash_main = self.flash_main
        main_correct = True
        if (not plugin_main or not plugin_main.is_set()) and \
           (not canvas_main or not canvas_main.is_set()) and \
           (not flash_main or not flash_main.is_set()):
            tmp.append('No "main"-file set. Specify at least one of plugin or canvas main.')
            main_correct = False

        abs_path = get_absolute_path(path)
        if plugin_main:
            plugin_main = join_path(abs_path, plugin_main)
            if not access(plugin_main, R_OK):
                tmp.append('Can\'t access plugin "main"-file.')
        if canvas_main:
            canvas_main = join_path(abs_path, canvas_main)
            if not access(canvas_main, R_OK):
                tmp.append('Can\'t access canvas "main"-file.')
        if flash_main:
            if not flash_main.startswith('https://'):
                flash_main = join_path(abs_path, flash_main)
                if not access(flash_main, R_OK):
                    tmp.append('Can\'t access flash "main"-file.')

        mapping_table = self.mapping_table
        if (not mapping_table or not mapping_table.is_set()) and not flash_main:
            tmp.append('No mapping-table set.')
        elif path_correct and main_correct:
            mapping_table = join_path(abs_path, mapping_table)
            if not access(mapping_table, R_OK):
                tmp.append('Can\'t access mapping-table.')

        deploy_files = self.deploy_files
        if not deploy_files or not deploy_files.is_set():
            tmp.append('No deploy files set.')

        engine_version = self.engine_version
        if not engine_version or not engine_version.is_set():
            tmp.append('No engine version set.')
        elif not engine_version.is_correct():
            tmp.append('Invalid engine version set.')

        aspect_ratio = self.aspect_ratio
        if not aspect_ratio or not aspect_ratio.is_set():
            tmp.append('No aspect ratio set.')
        elif not aspect_ratio.is_correct():
            tmp.append('Invalid aspect ratio set.')

        if tmp:
            errors.append(('files', {'errors': tmp}))

        return (len(errors) == 0, {'Project-Settings': errors})


    @property
    def can_deploy(self):
        completeness = self.check_completeness()
        return completeness[0]


    def validate_yaml(self):
        result = {}

        try:
            badges = GameBadges(self)
        except BadgesUnsupportedException:
            pass
        except ApiException as e:
            result['Badges'] = [('badges.yaml', {
                'errors': ['%s' % e]
            })]
        else:
            issues = badges.validate()
            if issues:
                result['Badges'] = issues

        try:
            notification_keys = GameNotificationKeysList.get(self)
        except GameNotificationsUnsupportedException:
            pass
        except ApiException as e:
            result['Notifications'] = [('notifications.yaml', {
                'errors': ['%s' % e]
            })]
        else:
            issues = notification_keys.validate()
            if issues:
                result['Notifications'] = issues

        try:
            leaderboards = LeaderboardsList.load(self)
        except LeaderboardsUnsupported:
            pass
        except LeaderboardError as e:
            result['Leaderboards'] = [('leaderboards.yaml', {
                'errors': ['incorrect format: %s' % e]
            })]
        except KeyError as e:
            result['Leaderboards'] = [('leaderboards.yaml', {
                'errors': ['key %s could not be found.' % e]
            })]
        except ValidationException as e:
            result['Leaderboards'] = e.issues
        else:
            issues = leaderboards.issues
            if issues:
                result['Leaderboards'] = leaderboards.issues

        try:
            store = StoreList.load(self)
        except StoreUnsupported:
            pass
        except StoreError as e:
            result['Store'] = [('store.yaml', {
                'errors': ['incorrect format: %s' % e]
            })]
        except ValidationException as e:
            result['Store'] = e.issues
        else:
            issues = store.issues
            if issues:
                result['Store'] = store.issues

        try:
            for v in result.itervalues():
                for item in v:
                    if item[1]['errors']:
                        return (result, True)
        except (KeyError, IndexError):
            LOG.error('badly formatted result structure when checking YAML issues')
            return (result, True)
        return (result, False)



    ###################################################################################################################

    # Helpers - moved from helper class onto the object

    def status(self, fields):
        """
        Returns "complete", "incorrect" or "" (empty string) to represent status
        of the given field(s) towards publishing the specified game
        """
        # set everything grey until the game is not temporary anymore
        if self.is_temporary:
            return ''
        # accept both lists and single values
        if type(fields) is not list:
            fields = [fields]

        result = 'complete'
        for field in fields:
            field = self.__getattribute__(field)

            if not field.is_set():
                result = ''
            elif not field.is_correct():
                return "incorrect"
        return result

    def get_games_root(self):
        return self.games_root

#######################################################################################################################

def _shortern(string, length=30):
    if not string:
        return string
    str_len = len(string)
    if str_len > length:
        return '...%s' % (string[-length:])
    return string

#######################################################################################################################

class _File(object):
    def __init__(self, name, request_name=None, request_path=None, abs_file_path=None):
        self.name = name
        self.short_name = _shortern(name)
        self.request_name = request_name
        self.short_request_name = _shortern(request_name)
        self.request_path = request_path
        self.abs_file_path = abs_file_path
        if abs_file_path:
            try:
                self.size = os.path.getsize(abs_file_path)
            except OSError:
                self.size = 0
        else:
            self.size = 0

    def can_view(self):
        if self.request_name:
            _, ext1 = os.path.splitext(self.name)
            _, ext2 = os.path.splitext(self.request_name)
            return ext1 not in ['.cgfx'] and ext2 == '.json'
        return False

    def can_disassemble(self):
        if self.request_name:
            _, ext = os.path.splitext(self.request_name)
            return ext == '.json'
        return False

    def is_json(self):
        if self.request_name:
            abs_static_path = self.abs_file_path or get_absolute_path(self.request_name)
            try:
                json_handle = open(abs_static_path)
                json.load(json_handle)
            except IOError as e:
                LOG.error(str(e))
                return False
            except ValueError as e:
                #Expected if file is not valid json
                return False
        else:
            return False
        return True

    def is_directory(self):
        return (self.request_name is None)

    def as_dict(self):
        return {
            'assetName': self.name,
            'requestName': self.request_name,
            'canView': self.can_view(),
            'canDisassemble': self.can_disassemble(),
            'isDirectory': self.is_directory(),
            'size': self.get_size()
        }

    def get_size(self):
        return self.size
