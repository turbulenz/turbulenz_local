# Copyright (c) 2011-2013 Turbulenz Limited

from decorator import decorator

from turbulenz_local.lib.exceptions import ApiUnavailable, ApiNotImplemented

# pylint: disable=F0401
from paste.deploy.converters import asbool
# pylint: enable=F0401

class InvalidStatus(BaseException):
    pass

class ServiceStatus(object):

    # interval in seconds to poll our service status URL
    polling_interval = 4

    services_status = {}
    # requests are not queued up client-side if this is true
    # (should be true for any long polling interval to avoid
    # overloading our services)
    default_discard_requests = False

    @classmethod
    def set_ok(cls, service_name):
        cls.services_status[service_name] = {
            'status': 'ok',
            'running': True,
            'discardRequests': cls.default_discard_requests,
            'description': 'ok'
        }

    @classmethod
    def set_poll_interval(cls, value):
        cls.polling_interval = value

    @classmethod
    def get_poll_interval(cls):
        return cls.polling_interval

    @classmethod
    def set_status(cls, service_name, status):
        try:
            service_running = asbool(status['running'])
            cls.services_status[service_name] = {
                'status': 'ok' if service_running else 'unavailable',
                'running': service_running,
                'discardRequests': asbool(status.get('discardRequests', cls.default_discard_requests)),
                'description': status.get('description', 'ok' if service_running else 'unavailable')
            }
        except (KeyError, AttributeError):
            raise InvalidStatus()

    @classmethod
    def get_status(cls, service_name):
        try:
            return cls.services_status[service_name]
        except:
            raise ApiNotImplemented()

    @classmethod
    def get_status_list(cls):
        return cls.services_status

    @classmethod
    def check_status_decorator(cls, service_name):
        @decorator
        def wrapped_decorator(func, *args, **kwargs):
            service_status = cls.get_status(service_name)
            if service_status['running']:
                return func(*args, **kwargs)
            else:
                raise ApiUnavailable(service_status)

        return wrapped_decorator
