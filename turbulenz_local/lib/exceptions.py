# Copyright (c) 2011-2013 Turbulenz Limited

"""HTTP exceptions Apps

Provides API Level exceptions for webdevelopers
(those exceptions get caught and passed back as error Callbacks to the client)

"""
class PostOnlyException(BaseException):
    def __init__(self, value):
        super(PostOnlyException, self).__init__()
        self.value = value

    def __str__(self):
        return self.value


class GetOnlyException(BaseException):
    def __init__(self, value):
        super(GetOnlyException, self).__init__()
        self.value = value

    def __str__(self):
        return self.value


class ApiException(BaseException):
    def __init__(self, value, status='500 Internal Server Error', json_data=None):
        super(ApiException, self).__init__()
        self.value = value
        self.status = status
        self.json_data = json_data

    def __str__(self):
        return self.value


class InvalidGameSession(ApiException):
    def __init__(self):
        ApiException.__init__(self, 'Invalid game session id', '401 Unauthorized')


class NotFound(ApiException):
    def __init__(self, value, json_data=None):
        ApiException.__init__(self, value, '404 Not Found', json_data)


class BadRequest(ApiException):
    def __init__(self, value, json_data=None):
        ApiException.__init__(self, value, '400 Bad Request', json_data)


class Unauthorized(ApiException):
    def __init__(self, value, json_data=None):
        ApiException.__init__(self, value, '401 Unauthorized', json_data)


class Forbidden(ApiException):
    def __init__(self, value, json_data=None):
        ApiException.__init__(self, value, '403 Forbidden', json_data)


class ApiUnavailable(ApiException):
    pass

class ApiNotImplemented(ApiException):
    pass
