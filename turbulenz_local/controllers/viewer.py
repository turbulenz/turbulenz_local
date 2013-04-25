# Copyright (c) 2010-2011,2013 Turbulenz Limited
"""
Controller class for the viewer
"""
import logging

from pylons import config
from pylons.controllers.util import abort, redirect

from turbulenz_local.controllers import BaseController
from turbulenz_local.models.gamelist import get_game_by_slug

LOG = logging.getLogger(__name__)

class ViewerController(BaseController):

    viewer_app = config.get('viewer.app', 'viewer')
    viewer_type = config.get('viewer.type', 'canvas')
    viewer_mode = config.get('viewer.mode', 'release')

    @classmethod
    def app(cls, slug, asset):
        game = get_game_by_slug(slug)
        if not game:
            abort(404, 'Game does not exist: %s' % slug)

        asset_url = '/play/' + slug + '/'
        querystring = '?assetpath=%s&baseurl=%s&mapping_table=%s' % (asset, asset_url, game.mapping_table)
        viewer_url = '/%s#/play/%s/%s.%s.%s.html' % (querystring, cls.viewer_app, cls.viewer_app,
                                                   cls.viewer_type, cls.viewer_mode)
        redirect(viewer_url)

