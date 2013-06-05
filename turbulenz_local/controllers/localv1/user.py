# Copyright (c) 2011-2013 Turbulenz Limited

from pylons import request, response

from turbulenz_local.decorators import jsonify, postonly
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.userlist import login_user, get_current_user


class UserController(BaseController):

    @classmethod
    @postonly
    @jsonify
    def login(cls):
        username = request.params.get('username')
        login_user(str(username).lower())
        return {'ok': True}


    @classmethod
    @jsonify
    def get_user(cls):
        username = get_current_user().username
        # 315569260 seconds = 10 years
        response.set_cookie('local', username, httponly=False, max_age=315569260)
        return {'ok': True, 'data': {'username': username}}
