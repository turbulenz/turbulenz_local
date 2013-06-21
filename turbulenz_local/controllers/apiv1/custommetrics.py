# Copyright (c) 2012-2013 Turbulenz Limited

from simplejson import loads

from turbulenz_local.lib.exceptions import ApiException, BadRequest
from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import secure_post

from turbulenz_local.controllers import BaseController

def _validate_event(event_key, event_value):
    try:
        event_key = str(event_key)
    except ValueError:
        raise ValueError('Event key should not contain non-ascii characters')

    if not event_key:
        raise ValueError('Event key must be a non-empty string')

    if isinstance(event_value, (str, unicode)):
        try:
            event_value = loads(event_value)
        except ValueError:
            raise ValueError('Event value must be a number or an array of numbers')

    if not isinstance(event_value, list):
        try:
            event_value = float(event_value)
        except (TypeError, ValueError):
            raise ValueError('Event value must be a number or an array of numbers')
    else:
        try:
            for index, value in enumerate(event_value):
                event_value[index] = float(value)
        except (TypeError, ValueError):
            raise ValueError('Event value array elements must be numbers')

    return event_key, event_value

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
            raise BadRequest('Invalid game session id')

        game = session.game
        if game is None:
            raise ApiException('No game with that slug')

        if slug != game.slug:
            raise BadRequest('Slug and game session do not match')

        try:
            event_key = params['key']
        except (TypeError, KeyError):
            raise BadRequest('Event key missing')

        try:
            event_value = params['value']
        except (TypeError, KeyError):
            raise BadRequest('Event value missing')
        del params['value']

        try:
            event_key, event_value = _validate_event(event_key, event_value)
        except ValueError as e:
            raise BadRequest(e.message)

        # If reaches this point, assume success
        return  {'ok': True, 'data': {'msg': 'Added "' + str(event_value) + '" for "' + event_key + '" ' \
                                             '(Simulation only - Custom events are only tracked on the game site)'}}


    @classmethod
    @custommetrics_service
    @secure_post
    def add_event_batch(cls, slug, params=None):
        # Only a validation simulation! Custom events are only tracked on the game site.
        try:
            session = cls.game_session_list.get_session(params['gameSessionId'])
        except (KeyError, TypeError):
            raise BadRequest('Invalid game session id')

        game = session.game
        if game is None:
            raise ApiException('No game with that slug')

        if slug != game.slug:
            raise BadRequest('Slug and game session do not match')

        try:
            event_batch = params['batch']
        except (TypeError, KeyError):
            raise BadRequest('Event batch missing')
        del params['batch']

        if not isinstance(event_batch, list):
            raise BadRequest('Event batch must be an array of events')

        for event in event_batch:
            try:
                event_key = event['key']
            except (TypeError, KeyError):
                raise BadRequest('Event key missing')

            try:
                event_value = event['value']
            except (TypeError, KeyError):
                raise BadRequest('Event value missing')

            try:
                event_key, event_value = _validate_event(event_key, event_value)
            except ValueError as e:
                raise BadRequest(e.message)

            try:
                event_time = float(event['timeOffset'])
            except (TypeError, KeyError):
                raise BadRequest('Event time offset missing')
            except ValueError:
                raise BadRequest('Event time offset should be a float')

            if event_time > 0:
                raise BadRequest('Event time offsets should be <= 0 to represent older events')

        # If reaches this point, assume success
        return  {'ok': True, 'data': {'msg': 'Added %d events ' \
                                             '(Simulation only - Custom events are only tracked on the game site)' %
                                             len(event_batch)}}
