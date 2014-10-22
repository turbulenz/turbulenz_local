# Copyright (c) 2011-2013 Turbulenz Limited
from logging import getLogger
from time import time

from turbulenz_local.controllers import BaseController
from turbulenz_local.decorators import jsonify
from turbulenz_local.models.userlist import get_current_user

import jwt

LOG = getLogger(__name__)


class GameauthtokenController(BaseController):
    ##
    ## FRONT CONTROLLER METHODS
    ##

    @classmethod
    @jsonify
    def game_auth_token(cls, slug):
        user = get_current_user()
        secret = slug
        expTime = time() + 3 * 60
        jwtPayload = jwt.encode({'username': user.username, 'exp': expTime}, secret)
        return {'ok': True, 'data': jwtPayload}
