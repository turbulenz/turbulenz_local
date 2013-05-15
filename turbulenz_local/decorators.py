# Copyright (c) 2011,2013 Turbulenz Limited

from warnings import warn

from decorator import decorator
from simplejson import JSONEncoder, JSONDecoder

from pylons import request, response
from urlparse import urlparse

from turbulenz_local.lib.exceptions import PostOnlyException, GetOnlyException

# pylint: disable=C0103
_json_encoder = JSONEncoder(encoding='utf-8', separators=(',',':'))
_json_decoder = JSONDecoder(encoding='utf-8')
# pylint: enable=C0103

@decorator
def postonly(func, *args, **kwargs):
    try:
        _postonly()
        return func(*args, **kwargs)
    except PostOnlyException as e:
        return e


def _postonly():
    if request.method != 'POST':
        headers = response.headers
        headers['Content-Type'] = 'application/json; charset=utf-8'
        headers['Cache-Control'] = 'no-store, no-cache, max-age=0'
        headers['Allow'] = 'POST'
        response.status_int = 405
        raise PostOnlyException('{"ok":false,"msg":"Post Only!"}')


def _getonly():
    if request.method != 'GET':
        headers = response.headers
        headers['Content-Type'] = 'application/json; charset=utf-8'
        headers['Cache-Control'] = 'no-store, no-cache, max-age=0'
        headers['Allow'] = 'GET'
        response.status_int = 405
        raise GetOnlyException('{"ok":false,"msg":"Get Only!"}')

@decorator
def jsonify(func, *args, **kwargs):
    return _jsonify(func(*args, **kwargs))

def _jsonify(data):
    # Sometimes we get back a string and we don't want to double-encode
    # Checking for basestring instance catches both unicode and str.
    if not isinstance(data, basestring):

        if isinstance(data, (list, tuple)):
            msg = "JSON responses with Array envelopes are susceptible to " \
                  "cross-site data leak attacks, see " \
                  "http://pylonshq.com/warnings/JSONArray"
            warn(msg, Warning, 2)

        data = _json_encoder.encode(data)

    if 'callback' in request.params:
        response.headers['Content-Type'] = 'text/javascript; charset=utf-8'
        cbname = str(request.params['callback'])
        data = '%s(%s);' % (cbname, data)
    else:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'

    return data

@decorator
def secure_get(func, *args, **kwargs):
    try:
        _getonly()
        return _secure(request.GET, func, *args, **kwargs)
    except GetOnlyException as e:
        return e.value

@decorator
def secure_post(func, *args, **kwargs):
    try:
        _postonly()
        return _secure(request.POST, func, *args, **kwargs)
    except PostOnlyException as e:
        return e.value

def _secure(requestparams, func, *args, **kwargs):
    if 'data' in requestparams:
        data = _json_decoder.decode(requestparams['data'])
        if data is None:
            data = dict()
    else:
        data = dict()
        data.update(requestparams)

    args = args[:-1] + (data,)

    func_result = func(*args, **kwargs)

    # pylint: disable=E1101
    func_result['requestUrl'] = urlparse(request.url).path
    # pylint: enable=E1101

    return _jsonify(func_result)
