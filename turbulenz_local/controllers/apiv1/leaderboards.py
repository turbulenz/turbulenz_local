# Copyright (c) 2011-2013 Turbulenz Limited

from math import isinf, isnan

# pylint: disable=F0401
from pylons import request, response
# pylint: enable=F0401

from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.lib.exceptions import BadRequest
from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.decorators import secure_post, jsonify, postonly

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.apiv1.leaderboards import LeaderboardsList, LeaderboardError
from turbulenz_local.models.userlist import get_current_user


class LeaderboardsController(BaseController):
    """ LeaderboardsController consists of all the Leaderboards methods
    """

    leaderboards_service = ServiceStatus.check_status_decorator('leaderboards')

    max_top_size = 32
    max_near_size = 32
    max_page_size = 64

    @classmethod
    @leaderboards_service
    @jsonify
    def read_meta(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug'}

        try:
            leaderboards = LeaderboardsList.load(game)

            return {'ok': True, 'data': leaderboards.read_meta()}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @postonly
    @leaderboards_service
    @jsonify
    def reset_meta(cls):
        LeaderboardsList.reset()
        return {'ok': True}


    @classmethod
    @leaderboards_service
    @jsonify
    def read_overview(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug'}

        try:
            leaderboards = LeaderboardsList.get(game)
            return {'ok': True, 'data': leaderboards.read_overview(get_current_user())}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @leaderboards_service
    @jsonify
    def read_aggregates(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug'}

        try:
            leaderboards = LeaderboardsList.get(game)
            return {'ok': True, 'data': leaderboards.read_aggregates()}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @leaderboards_service
    @jsonify
    def read_expanded(cls, slug, key):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug'}

        params = request.GET
        method_type = params.get('type', 'top')

        def get_size(default_size, max_size):
            try:
                size = int(params.get('size', default_size))
                if size <= 0 or size > max_size:
                    raise BadRequest('size must be a positive integer smaller than %d' % max_size)
            except ValueError:
                raise BadRequest('size must be a positive integer smaller than %d' % max_size)
            return size

        try:
            leaderboards = LeaderboardsList.get(game)

            is_above = (method_type == 'above')
            if method_type == 'below' or is_above:
                try:
                    score = float(params.get('score'))
                    score_time = float(params.get('time', 0))
                    if isinf(score) or isnan(score) or isinf(score_time) or isnan(score_time):
                        response.status_int = 400
                        return { 'ok': False, 'msg': 'Score or time are incorrectly formated' }
                except (TypeError, ValueError):
                    response.status_int = 400
                    return {'ok': False, 'msg': 'Score or time parameter missing'}

                return {'ok': True, 'data': leaderboards.get_page(key,
                                                                  get_current_user(),
                                                                  get_size(5, cls.max_page_size),
                                                                  is_above,
                                                                  score,
                                                                  score_time)}
            if method_type == 'near':
                return {'ok': True, 'data': leaderboards.get_near(key,
                                                                  get_current_user(),
                                                                  get_size(9, cls.max_near_size))}
            else:  # method_type == 'top'
                return {'ok': True, 'data': leaderboards.get_top_players(key,
                                                                         get_current_user(),
                                                                         get_size(9, cls.max_top_size))}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @leaderboards_service
    @secure_post
    def set(cls, key, params=None):
        session = cls._get_gamesession(params)

        try:
            leaderboards = LeaderboardsList.get(session.game)

            score = float(params['score'])
            if isinf(score):
                response.status_int = 400
                return {'ok': False, 'msg': '"score" must be a finite number'}
            if score < 0:
                response.status_int = 400
                return {'ok': False, 'msg': '"score" cannot be a negative number'}

            return {'ok': True, 'data': leaderboards.set(key, session.user, score)}

        except (TypeError, ValueError):
            response.status_int = 400
            return {'ok': False, 'data': 'Score is missing or incorrectly formated'}
        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @leaderboards_service
    @jsonify
    def remove_all(cls, slug):
        # This is for testing only and is not present on the Hub or Gamesite
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with that slug exists'}
        try:
            leaderboards = LeaderboardsList.get(game)
            leaderboards.remove_all()

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except LeaderboardError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}

        return {'ok': True}
