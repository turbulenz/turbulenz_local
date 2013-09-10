# Copyright (c) 2010-2013 Turbulenz Limited
"""Helper functions

Consists of functions to typically be used within templates, but also
available to Controllers. This module is available to templates as 'h'.
"""
import logging
import urllib2

from hashlib import md5
from urllib import urlencode
from os.path import join as path_join
from platform import system as platform_system

import simplejson as json

from yaml import load as yaml_load

# pylint: disable=F0401
from paste.deploy.converters import asbool, asint
# pyline: enable=F0401

from pylons import request

from turbulenz_local import SDK_VERSION, CONFIG_PATH
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.tools import slugify as slugify_fn

LOG = logging.getLogger(__name__)

#######################################################################################################################

def turbulenz_api(endpoint, timeout=5):
    try:
        f = urllib2.urlopen(endpoint, None, timeout)
        try:
            data = json.load(f)
        finally:
            f.close()
    except urllib2.URLError as e:
        LOG.error('Failed contacting: %s', endpoint)
        LOG.error(' >> %s', str(e))
        data = { }
    return data

def turbulenz_sdk_version(sdk_version):
    query = turbulenz_api(sdk_version)

    if query.get('ok', False):
        data = query.get('data', None)
        if data:
            os_mapping = {
                'Windows': 'windows',
                'Linux': 'linux',
                'Darwin': 'mac'
            }
            sysname = platform_system()
            os = os_mapping[sysname]
            this_os = data[os]
            latest_version = this_os['latest']
            all_versions = this_os['versions']
            if all_versions:
                latest_link = 'https://hub.turbulenz.com/download/%s' % \
                    all_versions[latest_version]['file']
            else:
                latest_link = ''
                latest_version = ''

            return {
                'newest': latest_version,
                'current': SDK_VERSION,
                'download': latest_link
            }

    return {
        'newest': '',
        'current': SDK_VERSION,
        'download': ''
    }

def turbulenz_engine_version(engine_version):
    query = turbulenz_api(engine_version)

    plugin_data = { }

    if query.get('ok', False):
        data = query.get('data', None)
        if data:
            os_list = ['Windows', 'Mac', 'Linux']

            for o in os_list:
                this_os = data[o]
                latest_plugin_version = this_os['latest']
                all_versions = this_os['versions']
                if all_versions:
                    latest_plugin_link = all_versions[latest_plugin_version]['file']
                else:
                    latest_plugin_link = ''
                    latest_plugin_version = ''

                os_data = {
                    'newest': latest_plugin_version,
                    'download': latest_plugin_link
                }
                plugin_data[o] = os_data

    return plugin_data

def _load_yaml_mapping(filename):
    try:
        f = open(filename)
        try:
            yaml_versions = yaml_load(f)
        finally:
            f.close()
    except IOError:
        yaml_versions = { }

    return yaml_versions

#######################################################################################################################

class Helpers(object):

    def __init__(self, config):
        self.sdk_data = turbulenz_sdk_version(config['sdk_version'])
        self.plugin_data = turbulenz_engine_version(config['engine_version'])

        self.gravatars_style = config.get('gravatars.style', 'monsterid')

        if asbool(config.get('scripts.development', False)):
            self.js_mapping = { }
            self.css_mapping = { }
            self.html_mapping = { }
        else:
            self.js_mapping = _load_yaml_mapping(path_join(CONFIG_PATH, 'js_versions.yaml'))
            self.css_mapping = _load_yaml_mapping(path_join(CONFIG_PATH, 'css_versions.yaml'))
            self.html_mapping = _load_yaml_mapping(path_join(CONFIG_PATH, 'html_versions.yaml'))

        self.deploy_enable = asbool(config.get('deploy.enable', False))
        self.deploy_host = config.get('deploy.host', '0.0.0.0')
        self.deploy_port = asint(config.get('deploy.port', 8080))
        self.viewer_app = config.get('viewer.app', 'viewer')

    def javascript_link(self, url):
        url = self.js_mapping.get(url, url)
        return '<script src="%s" type="text/javascript"></script>' % url

    def javascript_url(self, url):
        return self.js_mapping.get(url, url)

    def stylesheet_link(self, url):
        url = self.css_mapping.get(url, url)
        return '<link href="%s" media="screen" rel="stylesheet" type="text/css">' % url

    def stylesheet_url(self, url):
        return self.css_mapping.get(url, url)

    def html_url(self, url):
        return self.html_mapping.get(url, url)

    def gravatar_url(self, name, style=None, size=100):
        if not style:
            style = self.gravatars_style
        return 'http://www.gravatar.com/avatar/%s?%s' % (md5(name).hexdigest(),
                                                         urlencode({'d':style, 's':str(size)}))

    @classmethod
    def search_order(cls, match, default=False):
        value = request.params.get('search_order')
        if value == match:
            return ' selected="selected"'
        if not value and default:
            return ' selected="selected"'
        return ''

    @classmethod
    def search_keywords(cls):
        return request.params.get('search_keywords', '')

    def sdk_info(self):
        return json.JSONEncoder().encode(self.sdk_data)

    def plugin_info(self):
        return json.JSONEncoder().encode(self.plugin_data)

    def viewer_enabled(self):
        game = get_game_by_slug(self.viewer_app)
        return 'true' if game else 'false'

    @classmethod
    def sort_order(cls, order):
        classes = []
        if order is not None and order == request.params.get('sort_order', None):
            classes.append('sort')
            if request.params.get('sort_rev', False):
                classes.append('rev')
        if classes:
            return ' class="%s"' % ' '.join(classes)
        return ''

    @classmethod
    def slugify(cls, s):
        return slugify_fn(s)

#######################################################################################################################

def make_helpers(config):
    return Helpers(config)
