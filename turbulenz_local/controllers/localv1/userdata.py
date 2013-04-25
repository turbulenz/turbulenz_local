# Copyright (c) 2011-2013 Turbulenz Limited

import logging
from os import listdir
from os.path import join, exists

# pylint: disable=F0401
from pylons import response, config
from pylons.controllers.util import forward, abort

from paste.fileapp import FileApp
# pylint: enable=F0401

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.userlist import get_user
from turbulenz_local.models.game import _File
from turbulenz_local.models.apiv1.userdata import UserData
from turbulenz_local.models.gamelist import get_game_by_slug

LOG = logging.getLogger(__name__)


class UserdataController(BaseController):
    """ UserdataController consists of all the Userdata methods
    """

    datapath = config.get('userdata_db')

    @classmethod
    @jsonify
    def overview(cls, slug):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        abs_static_path = join(cls.datapath, slug)
        users = listdir(abs_static_path) if exists(abs_static_path) else [ ]

        return {
            'ok': True,
            'data': {
                'title': game.title,
                'slug': game.slug,
                'userdata': exists(join(cls.datapath, slug)),
                'users': users
            }
        }

    @classmethod
    @jsonify
    def userkeys(cls, slug, username):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        # !!! Move this into the user model
        user_path = join(cls.datapath, slug, username)
        if not exists(user_path):
            response.status_int = 404
            return {'ok': False, 'msg': 'User does not exist: %s' % slug}

        userdata = UserData(user=get_user(username), game=game)
        if userdata is None:
            response.status_int = 400
            return {'ok': False, 'msg': 'No session with that ID exists'}
        data_list = userdata.get_keys()

        userdata = { }
        for i in data_list:
            file_path = join(cls.datapath, slug, username, i) + '.txt'
            f = _File(i, file_path, username, file_path)
            userdata[f.name] = {
                'assetName': f.name,
                'isJson': f.is_json(),
                'size': f.get_size()
            }

        return {
            'ok': True,
            'data': userdata
        }

    @classmethod
    def as_text(cls, slug, username, key):
        filepath = join(cls.datapath, slug, username, '%s.txt' % key)
        headers = [('Content-Type', 'text/plain'), ('Content-Disposition', 'attachment; filename=%s' % key) ]

        try:
            text = forward(FileApp(filepath, headers))
        except OSError:
            abort(404, 'Game does not exist: %s' % slug)
        else:
            return text
