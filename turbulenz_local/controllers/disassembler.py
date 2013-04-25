# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for actions pertaining to a specified game
"""

import logging
import os.path

import simplejson as json

from pylons import request, response, tmpl_context as c, config
from pylons.controllers.util import abort

# pylint: disable=F0401
from paste.deploy.converters import asint
# pylint: enable=F0401

from turbulenz_tools.utils.disassembler import Disassembler, Json2htmlRenderer
from turbulenz_local.middleware.compact import CompactMiddleware as Compactor
from turbulenz_local.controllers import BaseController, render
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.userlist import get_user
from turbulenz_local.models.apiv1.userdata import UserData
from turbulenz_local.tools import get_absolute_path

LOG = logging.getLogger(__name__)


def get_asset(asset, slug, userdata=None):
    game = get_game_by_slug(slug)

    if userdata:
        # asset = user / key
        (username, key) = asset.split('/', 1)
        user = get_user(username)
        userdata = UserData(user=user, game=game)
        json_asset = json.loads(userdata.get(key))
        filename = key + '.txt'
    else:
        filename = get_absolute_path(os.path.join(game.path, asset))
        with open(filename, 'r') as handle:
            json_asset = json.load(handle)
    return (json_asset, filename)


class DisassemblerController(BaseController):

    default_depth = asint(config.get('disassembler.default_depth', '2'))
    default_list_cull = asint(config.get('disassembler.default_dict_cull', '5'))
    default_dict_cull = asint(config.get('disassembler.default_list_cull', '5'))

    @classmethod
    def app(cls, slug, asset):
        game = get_game_by_slug(slug)
        if not game:
            abort(404, 'Invalid game: %s' % slug)

        try:
            depth = int(request.params.get('depth', cls.default_depth))
            list_cull = int(request.params.get('list_cull', cls.default_list_cull))
            dict_cull = int(request.params.get('dict_cull', cls.default_dict_cull))
            expand = bool(request.params.get('expand', False))
            userdata = int(request.params.get('userdata', 0))
        except TypeError as e:
            abort(404, 'Invalid parameter: %s' % str(e))

        depth = max(1, depth)
        list_cull = max(1, list_cull)
        dict_cull = max(1, dict_cull)

        node = request.params.get('node', None)
        if node:
            try:
                (json_asset, filename) = get_asset(asset, slug, userdata)

                link_prefix = '/disassemble/%s' % slug

                disassembler = Disassembler(Json2htmlRenderer(), list_cull, dict_cull, depth, link_prefix)
                response.status = 200
                Compactor.disable(request)
                return disassembler.mark_up_asset({'root': json_asset}, expand, node)
            except IOError as e:
                abort(404, str(e))
            except json.JSONDecodeError as e:
                _, ext = os.path.splitext(filename)
                if ext == '.json':
                    abort(404, 'Failed decoding JSON asset: %s\nError was: %s' % (asset, str(e)))
                else:
                    abort(404, 'Currently unable to disassemble this asset: %s' % asset)
        else:
            c.game = game
            local_context = { 'asset': asset,
                              'list_cull': list_cull,
                              'dict_cull': dict_cull,
                              'depth': depth,
                              'userdata': userdata }
            return render('/disassembler/disassembler.html', local_context)
