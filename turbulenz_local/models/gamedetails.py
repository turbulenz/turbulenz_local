# Copyright (c) 2010-2013 Turbulenz Limited

from os import access, W_OK, R_OK
from os.path import join as join_path
from re import compile as re_compile

from turbulenz_local.tools import slugify, get_absolute_path
from turbulenz_local import SDK_VERSION

# Version must be of the format X.X
ENGINEVERSION_PATTERN = re_compile('^(\d+\.)(\d+)$')
if SDK_VERSION:
    ENGINEVERSION = '.'.join(SDK_VERSION.split('.')[0:2])
else:
    ENGINEVERSION = 'unset'

# Aspect ratio must be of the format x:y with x and y being integers or floats
ASPECT_RATIO_PATTERN = re_compile('^(?=.*[1-9])\d+(\.\d+)?:(?=.*[1-9])\d+(\.\d+)?$')
DEFAULT_ASPECT_RATIO = '16:9'

# pylint: disable=R0904
class GameDetail(str):
    def __new__(cls, value):
        if not value:
            value = ''
        return str.__new__(cls, value.strip())

    def is_set(self):
        return self.__str__() != ''

    def is_correct(self):
        return self.is_set()


class EngineDetail(str):
    def __new__(cls, value):
        if not value:
            value = ENGINEVERSION
        else:
            value = str(value).strip()
        return str.__new__(cls, value)

    def is_set(self):
        return self.__str__() != ''

    def is_correct(self):
        if ENGINEVERSION_PATTERN.match(self.__str__()):
            # Existence of the particular engine referenced should be
            # checked on the Hub
            return True
        else:
            return False


class AspectRatioDetail(str):
    def __new__(cls, value):
        if not value:
            value = DEFAULT_ASPECT_RATIO
        return str.__new__(cls, value.strip())

    def is_set(self):
        return self.__str__() != ''

    def is_correct(self):
        if ASPECT_RATIO_PATTERN.match(self.__str__()):
            return True
        else:
            return False


class PathDetail(GameDetail):
    def __new__(cls, value):
        return GameDetail.__new__(cls, value)

    def is_correct(self):
        try:
            abs_path = get_absolute_path(self.__str__())
            return access(abs_path, W_OK)
        except (AttributeError, TypeError):
            # TODO: These are thrown by get_absolute_path when called on None and probably shouldn't be needed
            return False


class SlugDetail(str):
    def __new__(cls, value=None):
        if not value:
            value = 'new-game'
        else:
            value = slugify(value)
        return str.__new__(cls, value)

    def is_set(self):
        return self.__str__() != ''

    def is_correct(self):
        return slugify(self.__str__()) == self.__str__()
# pylint: enable=R0904


class ImageDetail(object):
    def __init__(self, game, image_path):
        self.game = game
        self.image_path = image_path

        if self.is_correct():
            self.image_path = image_path
        else:
            self.image_path = ''

    def is_correct(self):
        try:
            path = get_absolute_path(self.game.path)
            path = join_path(path, self.image_path)
        except (AttributeError, TypeError):
            # TODO: These are thrown by get_absolute_path when called on None and probably shouldn't be needed
            return None
        else:
            return access(path, R_OK)

    def __repr__(self):
        return '/%s/%s' % (self.game.slug, self.image_path)


class ListDetail(object):
    def __init__(self, src):
        if isinstance(src, basestring):
            items = src.splitlines()
            items = [item.strip() for item in items]
            items = [item.encode('utf8') for item in items if item]
        else:
            items = src
        self.items = items

    def is_set(self):
        return len(self.items) > 0

    def is_correct(self):
        return self.is_set()

    def __repr__(self):
        return '\n'.join(self.items)

    def getlist(self):
        return self.items
