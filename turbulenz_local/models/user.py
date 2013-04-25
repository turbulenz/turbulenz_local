# Copyright (c) 2010-2013 Turbulenz Limited

from getpass import getuser as _get_user_name

# pylint: disable=F0401
from pylons import config
# pylint: enable=F0401

from turbulenz_local.lib.tools import create_id


class User(object):

    default_username = str(_get_user_name())
    default_age = 18
    default_country = 'GB'
    default_language = 'en'
    default_email = None

    def __init__(self, user_data, default=False):
        if isinstance(user_data, dict):
            if 'username' in user_data:
                self.username = user_data['username']
            elif 'name' in user_data:
                self.username = user_data['name']
            else:
                raise KeyError('username missing')

            self.age = user_data.get('age', self.default_age)
            self.country = user_data.get('country', self.default_country)
            self.language = user_data.get('language', self.default_language)
            self.email = user_data.get('email', self.default_email)

            if 'avatar' in user_data:
                self.avatar = user_data['avatar']
            else:
                self.avatar = self.get_default_avatar()

        else:
            self.username = user_data
            self.age = self.default_age
            self.country = self.default_country
            self.language = self.default_language
            self.email = self.default_email
            self.avatar = self.get_default_avatar()

        self.default = default

    @classmethod
    def get_default_avatar(cls):
        default_avatar_generator = config.get('default_avatar', 'gravitar')

        if default_avatar_generator == 'gravitar':
            gravitar_address = config.get('gravitar_address', 'http://www.gravatar.com/avatar/')
            gravatar_type = config.get('gravatar_type', 'identicon')
            return gravitar_address + create_id() + '?d=' + gravatar_type
        else:
            return None


    def to_dict(self):
        return {
            'username': self.username,
            'age': self.age,
            'country': self.country,
            'language': self.language,
            'avatar': self.avatar,
            'email': self.email,
            'default': self.default
        }
