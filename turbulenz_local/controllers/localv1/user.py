# Copyright (c) 2011-2013 Turbulenz Limited

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.userlist import set_current_user, get_current_user


class UserController(BaseController):

    @classmethod
    @jsonify
    def set_user(cls, username):
        set_current_user(str(username))
        return {'ok': True}


    @classmethod
    @jsonify
    def get_user(cls):
        return {'ok': True, 'data': get_current_user().username}
