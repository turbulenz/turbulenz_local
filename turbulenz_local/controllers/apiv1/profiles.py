# Copyright (c) 2011-2013 Turbulenz Limited
from logging import getLogger

from turbulenz_local.lib.servicestatus import ServiceStatus

from turbulenz_local.controllers import BaseController
from turbulenz_local.decorators import jsonify
from turbulenz_local.models.userlist import get_current_user


LOG = getLogger(__name__)


class ProfilesController(BaseController):
    """ ProfilesController consists of all the Profiles methods
    """

    profiles_service = ServiceStatus.check_status_decorator('profiles')

    ##
    ## FRONT CONTROLLER METHODS
    ##

    @classmethod
    @profiles_service
    @jsonify
    def user(cls):
        user = get_current_user()
        user_profile = {'username': user.username,
                        'displayname': user.username,
                        'age': user.age,
                        'language': user.language,
                        'country': user.country,
                        'avatar': user.avatar,
                        'guest': user.guest}
        return {'ok': True, 'data': user_profile}
