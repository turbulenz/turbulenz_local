# Copyright (c) 2011-2013 Turbulenz Limited

from logging import getLogger
from yaml.scanner import ScannerError

# pylint: disable=F0401
from pylons import response
# pylint: enable=F0401

from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import jsonify, secure_post

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.apiv1.badges import Badges, BadgesUnsupportedException
from turbulenz_local.models.userlist import get_current_user

from turbulenz_local.lib.exceptions import ApiException

LOG = getLogger(__name__)


class BadgesController(BaseController):
    """ BadgesController consists of all the badges methods
    """

    badges_service = ServiceStatus.check_status_decorator('badges')

    #list badges for a given user (the username is taken from the environment if it's not passed as a parameter)
    @classmethod
    @jsonify
    def badges_user_list(cls, slug=None):
        try:
            game = get_game_by_slug(slug)
            if game is None:
                raise ApiException('No game with that slug')
            # get the user from the environment
            # get a user model (simulation)
            user = get_current_user()
            # try to get a user_id from the context

            badges_obj = Badges.get_singleton(game)
            badges = badges_obj.badges
            badges_total_dict = dict((b['key'], b.get('total')) for b in badges)

            userbadges = badges_obj.find_userbadges_by_user(user.username)

            for key, userbadge in userbadges.iteritems():
                del userbadge['username']
                try:
                    total = badges_total_dict[key]
                except KeyError:
                    # the badge has been deleted or its key renamed so we just skip it
                    continue

                userbadge['total'] = total
                userbadge['achieved'] = (userbadge['current'] >= total)

            response.status_int = 200
            return {'ok': True, 'data': userbadges.values()}

        except BadgesUnsupportedException:
            return {'ok': False, 'data': []}
        except ApiException as message:
            response.status_int = 404
            return {'ok': False, 'msg': str(message)}

    @classmethod
    @badges_service
    @jsonify
    def badges_list(cls, slug):
        try:
            game = get_game_by_slug(slug)
            if game is None:
                raise ApiException('No game with that slug')

            badges = Badges.get_singleton(game).badges

            # Patch any unset total values in the response (to be consistent with the hub and game site)
            for badge in badges:
                if 'total' not in badge:
                    badge['total'] = None
                if 'predescription' not in badge:
                    badge['predescription'] = None

            return {'ok': True, 'data': badges}

        except BadgesUnsupportedException:
            return {'ok': False, 'data': []}
        except ApiException as message:
            response.status_int = 404
            return {'ok': False, 'msg': str(message)}
        except ScannerError as message:
            response.status_int = 404
            return {'ok': False, 'msg': 'Could not parse YAML file. %s' % (message)}

    @classmethod
    @badges_service
    @secure_post
    # add a badge to a user (gets passed
    # a badge and a current level over POST,
    # the username is taken from the environment)
    def badges_user_add(cls, slug, params=None):
        try:
            session = cls._get_gamesession(params)
            game = session.game
            if game is None:
                raise ApiException('No game with that slug')

            badge_key = params['badge_key']
            if not badge_key:
                raise ApiException('Must specify a badge_key to add.')

            # we have a badge_key now try to see if that badge exists
            badges_obj = Badges.get_singleton(game)
            badge = badges_obj.get_badge(badge_key)
            if not badge:
                raise ApiException('Badge name %s was not found.' % badge_key)
            if not ('image' in badge) or not badge['image']:
                badge['image'] = '/static/img/badge-46x46.png'

            # Use the badge['key'] property because badge_key is unicode
            ub = {'username': session.user.username,
                  'badge_key': badge['key']}

            badge_total = badge.get('total')
            total = badge_total or 1.0

            current = 0
            if 'current' in params:
                try:
                    current = float(int(params['current']))
                except (ValueError, TypeError):
                    response.status_int = 400
                    return {'ok': False, 'msg': '\'current\' must be a integer'}
            if not current:
                current = total
            ub['current'] = current

            userbadge = badges_obj.get_userbadge(session.user.username, badge_key)
            Badges.get_singleton(game).upsert_badge(ub)

            if current >= total and (not userbadge or userbadge.get('current', 0) < total):
                achieved = True
            else:
                achieved = False

            response.status_int = 200
            return {'ok': True, 'data': {
                'current': current,
                'total': badge_total,
                'badge_key': badge_key,
                'achieved': achieved
            }}

        except BadgesUnsupportedException:
            response.status_int = 404
            return {'ok': False, 'msg': 'Badges are unsupported for this game'}
        except ApiException as message:
            response.status_int = 404
            return {'ok': False, 'msg': str(message)}
