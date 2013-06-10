# Copyright (c) 2010-2013 Turbulenz Limited

from getpass import getuser as _get_user_name
from re import compile as re_compile, sub as re_sub

# pylint: disable=F0401
from pylons import config
# pylint: enable=F0401

from turbulenz_local.lib.tools import create_id


class User(object):

    username_regex_pattern = '^[A-Za-z0-9]+[A-Za-z0-9-]*$'
    username_pattern = re_compile(username_regex_pattern)

    # remove any characters that do not match the regex
    try:
        default_username = re_sub('[^A-Za-z0-9-]', '', str(_get_user_name()))
        if len(default_username) == 0 or default_username[0] == '-':
            default_username = 'default'
    except UnicodeEncodeError:
        default_username = 'default'

    default_age = 18
    default_country = 'GB'
    default_language = 'en'
    default_email = None
    default_guest = False

    def __init__(self, user_data, default=False):
        if isinstance(user_data, dict):
            try:
                if 'username' in user_data:
                    self.username = str(user_data['username']).lower()
                elif 'name' in user_data:
                    self.username = str(user_data['name']).lower()
                else:
                    raise KeyError('username missing')

                if not self.username_pattern.match(self.username):
                    raise ValueError('Username "%s" is invalid. '
                        'Usernames can only contain alphanumeric and hyphen characters.' % self.username)
            except UnicodeEncodeError:
                raise ValueError('Username "%s" is invalid. '
                        'Usernames can only contain alphanumeric and hyphen characters.' % self.username)

            self.age = user_data.get('age', self.default_age)
            self.country = user_data.get('country', self.default_country)
            self.language = user_data.get('language', self.default_language)
            self.email = user_data.get('email', self.default_email)
            self.guest = user_data.get('guest', self.default_guest)

            if 'avatar' in user_data:
                self.avatar = user_data['avatar']
            else:
                self.avatar = self.get_default_avatar()

        else:
            try:
                if not self.username_pattern.match(user_data):
                    raise ValueError('Username "%s" is invalid. '
                        'Usernames can only contain alphanumeric and hyphen characters.' % user_data)
                self.username = str(user_data).lower()

            except UnicodeEncodeError:
                raise ValueError('Username "%s" is invalid. '
                        'Usernames can only contain alphanumeric and hyphen characters.' % self.username)

            self.age = self.default_age
            self.country = self.default_country
            self.language = self.default_language
            self.email = self.default_email
            self.guest = self.default_guest
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
            'default': self.default,
            'guest': self.guest
        }
