# Copyright (c) 2012-2013 Turbulenz Limited

from simplejson import loads

# pylint: disable=F0401
from pylons import response
# pylint: enable=F0401

from turbulenz_local.lib.exceptions import ApiException
from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import secure_post

from turbulenz_local.controllers import BaseController


class CustommetricsController(BaseController):

    custommetrics_service = ServiceStatus.check_status_decorator('customMetrics')

    @classmethod
    @custommetrics_service
    @secure_post
    def add_event(cls, slug, params=None):
        # Only a validation simulation! Custom events are only tracked on the game site.
        try:
            session = cls.game_session_list.get_session(params['gameSessionId'])
        except (KeyError, TypeError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Invalid game session id'}

        game = session.game
        if game is None:
            raise ApiException('No game with that slug')

        if slug != game.slug:
            response.status_int = 400
            return {'ok': False, 'msg': 'Slug and game session do not match'}

        try:
            event_key = str(params['key'])
        except (TypeError, KeyError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Event key missing'}
        except ValueError:
            response.status_int = 400
            return {'ok': False, 'msg': 'Event key should not contain non-ascii characters'}

        if not event_key:
            response.status_int = 400
            return {'ok': False, 'msg': 'Event key must be a non-empty string'}

        try:
            event_value = params['value']
        except (TypeError, KeyError):
            response.status_int = 400
            return {'ok': False, 'msg': 'Event value missing'}
        del params['value']

        if isinstance(event_value, (str, unicode)):
            try:
                event_value = loads(event_value)
            except ValueError:
                response.status_int = 400
                return {'ok': False, 'msg': 'Event value must be a number or an array of numbers'}

        if not isinstance(event_value, list):
            try:
                event_value = float(event_value)
            except (TypeError, ValueError):
                response.status_int = 400
                return {'ok': False, 'msg': 'Event value must be a number or an array of numbers'}
        else:
            try:
                for index, value in enumerate(event_value):
                    event_value[index] = float(value)
            except (TypeError, ValueError):
                response.status_int = 400
                return {'ok': False, 'msg': 'Event value array elements must be numbers'}

        # If reaches this point, assume success
        response.status_int = 200
        return  {'ok': True, 'data': {'msg': 'Added "' + str(event_value) + '" for "' + event_key + '" ' \
                                             '(Simulation only - Custom events are only tracked on the game site)'}}
