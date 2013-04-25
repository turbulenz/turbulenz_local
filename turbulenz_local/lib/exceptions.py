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


class ApiException(BaseException):
    def __init__(self, value, status='500 Internal Server Error'):
        super(ApiException, self).__init__()
        self.value = value
        self.status = status

    def __str__(self):
        return self.value


class InvalidGameSession(ApiException):
    def __init__(self):
        ApiException.__init__(self, 'Invalid game session id', '401 Unauthorized')


class NotFound(ApiException):
    def __init__(self, value):
        ApiException.__init__(self, value, '404 Not Found')


class BadRequest(ApiException):
    def __init__(self, value):
        ApiException.__init__(self, value, '400 Bad Request')


class ApiUnavailable(ApiException):
    pass

class ApiNotImplemented(ApiException):
    pass
