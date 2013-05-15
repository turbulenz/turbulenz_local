# Copyright (c) 2010-2013 Turbulenz Limited
"""The devserver WSGI application"""

import logging
import os
import mimetypes

from beaker.middleware import CacheMiddleware, SessionMiddleware
from jinja2 import Environment, FileSystemLoader

# pylint: disable=F0401
from paste.registry import RegistryManager
from paste.deploy.converters import asbool, asint
# pylint: enable=F0401

from pylons import config
from pylons.wsgiapp import PylonsApp
from routes.middleware import RoutesMiddleware
from webob.util import status_reasons

from turbulenz_local.helpers import make_helpers
from turbulenz_local.routing import make_map
from turbulenz_local.middleware import MetricsMiddleware, LoggingMiddleware, GzipMiddleware, \
                                           StaticGameFilesMiddleware, StaticFilesMiddleware, \
                                           CompactMiddleware, EtagMiddleware, ErrorMiddleware

from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.models.gamesessionlist import GameSessionList

LOG = logging.getLogger(__name__)

def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config`` object"""
    # Pylons paths
    root = os.path.dirname(os.path.abspath(__file__))
    paths = dict(root=root,
                 controllers=os.path.join(root, 'controllers'),
                 static_external_paths=[os.path.join(root, 'public', 'external')],
                 static_development_paths=[os.path.join(root, 'public', 'development')],
                 static_release_paths=[os.path.join(root, 'public', 'release')],
                 static_viewer_paths=[os.path.realpath(os.path.join(root, '..', '..'))],
                 templates=[os.path.join(root, 'templates')])

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package='turbulenz_local', paths=paths)

    config['routes.map'] = make_map()
    config['pylons.app_globals'] = Globals()
    config['pylons.h'] = make_helpers(config)

    # Create the Jinja2 Environment
    config['pylons.app_globals'].jinja2_env = Environment(loader=FileSystemLoader(paths['templates']))

    # Jinja2's unable to request c's attributes without strict_c
    config['pylons.strict_c'] = True

    # CONFIGURATION OPTIONS HERE (note: all config options will override
    # any Pylons config options)
    config['pylons.response_options']['headers'] = {'Cache-Control': 'public, max-age=0',
                                                    'Pragma': 'no-cache'}


def __add_customisations():
    status_reasons[429] = 'Too Many Requests'


def __init_controllers():
    ServiceStatus.set_ok('userdata')
    ServiceStatus.set_ok('gameProfile')
    ServiceStatus.set_ok('leaderboards')
    ServiceStatus.set_ok('gameSessions')
    ServiceStatus.set_ok('badges')
    ServiceStatus.set_ok('profiles')
    ServiceStatus.set_ok('multiplayer')
    ServiceStatus.set_ok('customMetrics')
    ServiceStatus.set_ok('store')
    ServiceStatus.set_ok('datashare')
    ServiceStatus.set_ok('notifications')

    GameSessionList.get_instance().purge_sessions()


def make_app(global_conf, full_stack=True, static_files=True, **app_conf):
    """Create a Pylons WSGI application and return it

    ``global_conf``
        The inherited configuration for this application. Normally from
        the [DEFAULT] section of the Paste ini file.

    ``full_stack``
        Whether or not this application provides a full WSGI stack (by
        default, meaning it handles its own exceptions and errors).
        Disable full_stack when this application is "managed" by another
        WSGI middleware.

    ``static_files``
        Whether this application serves its own static files; disable
        when another web server is responsible for serving them.

    ``app_conf``
        The application's local configuration. Normally specified in the
        [app:<name>] section of the Paste ini file (where <name>
        defaults to main).
    """
    # Configure the Pylons environment
    load_environment(global_conf, app_conf)

    # Add missing mime types
    for k, v in app_conf.iteritems():
        if k.startswith('mimetype.'):
            mimetypes.add_type(v, k[8:])

    # The Pylons WSGI app
    app = PylonsApp()

    # Routing/Session/Cache Middleware
    app = RoutesMiddleware(app, config['routes.map'])
    if asbool(config.get('etag.enable', True)):
        app = EtagMiddleware(app, config)
    if asbool(config.get('compact.enable', True)):
        app = CompactMiddleware(app, config)
    app = SessionMiddleware(app, config)
    app = CacheMiddleware(app, config)

    # CUSTOM MIDDLEWARE HERE (filtered by error handling middlewares)
    if asbool(full_stack):
        app = ErrorMiddleware(app, config)

    # Establish the Registry for this application
    app = RegistryManager(app)

    if asbool(static_files):
        # Serve static files
        max_age = asint(config.get('cache_max_age.staticmax', 1))
        static_external_paths = config['pylons.paths']['static_external_paths']
        static_development_paths = config['pylons.paths']['static_development_paths']
        static_release_paths = config['pylons.paths']['static_release_paths']
        static_viewer_paths = config['pylons.paths']['static_viewer_paths']

        # Order is important for performance
        # file paths will be check sequentially the first time the file is requested
        if asbool(config.get('scripts.development', False)):
            all_path_items = [(path, 0) for path in static_development_paths]
        else:
            all_path_items = [(path, 28800) for path in static_development_paths]
        all_path_items.extend([(path, max_age) for path in static_external_paths])
        all_path_items.extend([(path, max_age) for path in static_release_paths])

        if asbool(config.get('viewer.development', 'false')):
            # We only need to supply the jslib files with the viewer in development mode
            all_path_items.extend([(path, 0) for path in static_viewer_paths])
            all_path_items.extend([(os.path.join(path, 'jslib'), 0) for path in static_viewer_paths])

        app = StaticFilesMiddleware(app, all_path_items)
        app = StaticGameFilesMiddleware(app, staticmax_max_age=max_age)

    app = GzipMiddleware(app, config)
    app = MetricsMiddleware(app, config)
    app = LoggingMiddleware(app, config)

    __add_customisations()
    __init_controllers()

    # Last middleware is the first middleware that gets executed for a request, and last for a response
    return app

class Globals(object):
    """Globals acts as a container for objects available throughout the life of the application"""

    def __init__(self):
        """One instance of Globals is created during application initialization and is available during requests via
        the 'app_globals' variable
        """
