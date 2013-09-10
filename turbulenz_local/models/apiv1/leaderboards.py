# Copyright (c) 2011-2013 Turbulenz Limited

import logging
LOG = logging.getLogger(__name__)

from re import compile as regex_compile
from time import time as time_now
from os.path import exists as path_exists, join as join_path, splitext

from math import floor, ceil, isinf, isnan

from threading import Lock

# pylint: disable=F0401
from pylons import config
import yaml
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, create_dir
from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.models.userlist import get_user

REQUIRED_LEADERBOARD_KEYS = ['key', 'title']


class LeaderboardError(Exception):
    def __init__(self, value, response_code=400):
        super(LeaderboardError, self).__init__()
        self.value = value
        self.response_code = response_code

    def __str__(self):
        return self.value


class LeaderboardsUnsupported(LeaderboardError):
    def __init__(self):
        super(LeaderboardsUnsupported, self).__init__('This game does not support leaderboards', 404)


class UserScore(object):
    def __init__(self, username, score, score_time):
        self.user = username
        self.score = score
        self.score_time = score_time

    def copy(self):
        return UserScore(self.user, self.score, self.score_time)

    def to_dict(self):
        return {'user': self.user,
                'score': self.score,
                'time': self.score_time}


class Leaderboard(object):

    validate_key = regex_compile('^[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*$')

    def __init__(self, game, key, meta_data, index):
        self.user_scores = {}
        self.scores = []
        self.aggregate = False
        self.aggregate_score = 0
        self.lock = Lock()

        self.errors = []
        self.warnings = []
        self.path = None

        def error(msg):
            self.errors.append(msg)

        def warning(msg):
            self.warnings.append(msg)

        if not self.validate_key.match(key):
            error('invalid key format "%s"' % key)
        self.key = key
        self.index = index

        if 'title' not in meta_data or meta_data['title'] is None:
            error('title property missing for key "%s"' % key)
            self.title = ''
        else:
            self.title = meta_data['title']

        if 'aggregate' in meta_data:
            if (isinstance(meta_data['aggregate'], bool)):
                self.aggregate = meta_data['aggregate']
            else:
                warning('aggregate property must be a boolean for key "%s"' % key)
                self.aggregate = False
        else:
            self.aggregate = False

        try:
            sort_by = int(meta_data['sortBy'])
            if sort_by != -1 and sort_by != 1:
                error('sortBy must either -1 or 1 for key "%s"' % key)
        except KeyError:
            warning('sortBy property missing for key "%s"' % key)
            sort_by = 1
        except ValueError:
            error('sortBy must either -1 or 1 for key "%s"' % key)
            sort_by = 1
        self.sort_by = sort_by

        if 'icon' in meta_data:
            warning('"icon" yaml property has been deprecated please use '
                    '"icon256", "icon48" or "icon32" for leaderboard key "%s"' % key)

        try:
            icon_path = meta_data['icon256']
            if path_exists(get_absolute_path(join_path(game.path, icon_path))):
                if splitext(icon_path)[1] != '.png':
                    warning('icon256 must be in PNG format for key "%s"' % key)
            else:
                error('icon256 file does not exist for key "%s"' % key)
        except KeyError:
            warning('no icon256 (using default) for key "%s"' % key)

        self.game = game

        self.default_scores = []
        default_scores = meta_data.get('default-scores', [])
        for (i, s) in enumerate(default_scores):
            if not isinstance(s, dict):
                warning('Default score must an array of objects for key "%s"' % key)
                continue

            user = s.get('user', None)
            if user is None:
                email = s.get('email', None)
                if email is None:
                    warning('Default score must contain user or email for key "%s"' % key)
                    continue
                try:
                    user = email.split('@', 1)[0]
                    # for tests
                    if user.startswith('no-reply+'):
                        user = user[9:]
                except AttributeError:
                    warning('Default score email "%s" must be a string for key "%s"' % (email, key))
                    continue

            if 'score' in s:
                try:
                    score = float(s['score'])
                    if isinf(score) or isnan(score):
                        warning('Default score for user "%s" must be a number for key "%s"' % (user, key))
                        continue
                    user_score = UserScore(user, score, time_now() - i)
                    self.default_scores.append(user_score)
                except (ValueError, TypeError):
                    warning('Default score for user "%s" must be a number for key "%s"' % (user, key))
                    continue
            else:
                warning('Default score for user "%s" missing score for key "%s"' % (user, key))
                continue

    def to_dict(self):
        return {'key': self.key,
                'index': self.index,
                'title': self.title,
                'sortBy': self.sort_by}

    def _set_path(self):
        if not self.path:
            try:
                path = config['leaderboards_db']
            except KeyError:
                LOG.error('leaderboards_db path config variable not set')
                return

            path = join_path(path, self.game.slug)
            if not create_dir(path):
                LOG.error('Game leaderboards path \"%s\" could not be created.', path)

            self.path = join_path(path, self.key + '.yaml')


    # do not use this function to increase a score
    def _add_score(self, user_score):
        self.user_scores[user_score.user] = user_score
        self.scores.append(user_score)
        if self.aggregate:
            self.aggregate_score += user_score.score


    def _read_leaderboard(self):
        self._set_path()
        with self.lock:
            self.user_scores = {}
            self.scores = []
            self.aggregate_score = 0

            unicode_path = unicode(self.path)
            if path_exists(unicode_path):
                try:
                    try:
                        f = open(unicode_path, 'r')
                        file_leaderboard = yaml.load(f)

                        if file_leaderboard:
                            for s in file_leaderboard:
                                self._add_score(UserScore(s['user'], s['score'], s['time']))
                    finally:
                        f.close()

                except (IOError, KeyError, yaml.YAMLError) as e:
                    LOG.error('Failed loading leaderboards file "%s": %s', self.path, str(e))
                    raise LeaderboardError('Failed loading leaderboard file "%s": %s' % (self.path, str(e)))

            else:
                self.user_scores = {}
                self.scores = []

            for s in self.default_scores:
                username = s.user
                if username not in self.user_scores:
                    # copy the score so that if the scores are reset then
                    # the default is left unchanged
                    self._add_score(s.copy())

            self._sort_scores()


    def _write_leaderboard(self):
        self._sort_scores()
        try:
            self._set_path()
            with self.lock:
                try:
                    f = open(unicode(self.path), 'w')
                    yaml.dump([s.to_dict() for s in self.scores], f, default_flow_style=False)
                finally:
                    f.close()
        except IOError as e:
            LOG.error('Failed writing leaderboard file "%s": %s', self.path, str(e))
            raise LeaderboardError('Failed writing leaderboard file %s' % self.path)


    def _empty_leaderboard(self):
        self.scores = []
        self.user_scores = {}
        self.aggregate_score = 0

        self._set_path()
        unicode_path = unicode(self.path)
        if not path_exists(unicode_path):
            return

        with self.lock:
            try:
                f = open(unicode_path, 'w')
                f.close()
            except IOError as e:
                LOG.error('Failed emptying leaderboard file "%s": %s', self.path, str(e))
                raise LeaderboardError('Failed emptying leaderboard file %s' % self.path)


    def _sort_scores(self):
        # sort best score first
        self.scores.sort(key=lambda s: (-self.sort_by * s.score, s.score_time))


    def _rank_leaderboard(self, leaderboard, top_rank):
        length = len(leaderboard)
        if length == 0:
            return

        leaderboard.sort(key=lambda r: (-self.sort_by * r['score'], r['time']))

        num_top = top_rank[1]
        prev_rank = top_rank[0]
        # next rank = top rank + num equal top rank
        rank = prev_rank + num_top
        top_score = leaderboard[0]['score']
        prev_score = top_score
        for i in xrange(length):
            r = leaderboard[i]
            score = r['score']
            if score != prev_score:
                prev_score = score
                prev_rank = rank

            r['rank'] = prev_rank
            if score != top_score:
                rank += 1

    @classmethod
    def _get_row(cls, username, score):
        user = get_user(username)
        return {'user': {
                    'username': username,
                    'displayName': username,
                    'avatar': user.avatar},
                'score': score.score,
                'time': score.score_time}


    def _get_user_row(self, user):
        username = user.username
        if username in self.user_scores:
            return self._get_row(username, self.user_scores[username])
        else:
            return None


    def _get_rank(self, score):
        # the top rank of the score
        top_rank = 1
        # the num scores equal to the score
        count = 0
        for s in self.scores:
            if score == s.score:
                count += 1
            else:
                if count != 0:
                    return (top_rank, count)
                top_rank += 1
        return (top_rank, count)


    @classmethod
    def create_response(cls, top, bottom, ranking, player=None):
        response = {
            'top': top,
            'bottom': bottom,
            'ranking': ranking
        }

        if player is not None:
            response['player'] = player
        return response


    def get_top_players(self, user, num_top_players):
        self._read_leaderboard()
        scores = self.scores
        leaderboard = []

        player = None
        try:
            for i in xrange(num_top_players):
                s = scores[i]
                username = s.user
                row = self._get_row(username, s)
                if username == user.username:
                    player = row

                leaderboard.append(row)
        except IndexError:
            pass

        if player is None:
            player = self._get_user_row(user)

        if len(leaderboard) > 0:
            self._rank_leaderboard(leaderboard, self._get_rank(leaderboard[0]['score']))

        bottom = len(scores) <= num_top_players
        return self.create_response(True, bottom, leaderboard, player)


    def get_page(self, user, max_page_size, is_above, score, score_time):
        self._read_leaderboard()
        scores = self.scores
        leaderboard = []

        player = None
        query_complete = False

        if not is_above:
            scores = reversed(scores)
        for s in scores:
            if is_above:
                if self.sort_by * s.score < self.sort_by * score or (s.score == score and s.score_time >= score_time):
                    query_complete = True
            else:
                if self.sort_by * s.score > self.sort_by * score or (s.score == score and s.score_time <= score_time):
                    query_complete = True

            if query_complete and len(leaderboard) >= max_page_size:
                break

            username = s.user
            row = self._get_row(username, s)
            if username == user.username:
                player = row

            leaderboard.append(row)

        # throw away scores after the end of the page
        leaderboard = leaderboard[-max_page_size:]

        # flip the scores back in the right direction for below queries
        if not is_above:
            leaderboard = list(reversed(leaderboard))

        if player is None:
            player = self._get_user_row(user)

        if len(leaderboard) > 0:
            self._rank_leaderboard(leaderboard, self._get_rank(leaderboard[0]['score']))
            top = (self.scores[0].user == leaderboard[0]['user']['username'])
            bottom = (self.scores[-1].user == leaderboard[-1]['user']['username'])
        else:
            top = True
            bottom = True

        return self.create_response(top, bottom, leaderboard, player)


    def get_near(self, user, size):
        self._read_leaderboard()

        scores = self.scores
        if len(scores) == 0:
            return self.create_response(True, True, [])

        if not user.username in self.user_scores:
            return self.get_top_players(user, size)

        index = None

        for i, r in enumerate(scores):
            if r.user == user.username:
                index = i
                break

        # higher board is larger for even numbers
        start = index - int(floor(size * 0.5))
        end = index + int(ceil(size * 0.5))

        # slide start and end when the player is on the edge of a board
        num_scores = len(scores)
        if start < 0:
            end -= start
            start = 0
            if end > num_scores:
                end = num_scores
        elif end > num_scores:
            start -= (end - num_scores)
            end = num_scores
            if start < 0:
                start = 0

        leaderboard = []
        player = None
        for i in xrange(start, end, 1):
            s = scores[i]
            username = s.user
            row = self._get_row(username, s)
            if username == user.username:
                player = row

            leaderboard.append(row)

        if player is None:
            player = self._get_user_row(user)

        self._rank_leaderboard(leaderboard, self._get_rank(leaderboard[0]['score']))

        top = (start == 0)
        bottom = (end == num_scores)
        return self.create_response(top, bottom, leaderboard, player)


    def read_overview(self, user):
        self._read_leaderboard()
        try:
            users_score = self.user_scores[user.username]
            score = users_score.score
            rank = self._get_rank(score)[0]
            return {'key': self.key,
                    'score': score,
                    'rank': rank,
                    'time': users_score.score_time}
        except KeyError:
            return None


    def read_aggregates(self):
        self._read_leaderboard()
        if self.aggregate:
            return {
                'key': self.key,
                'aggregateScore': self.aggregate_score,
                'numUsers': len(self.scores)
            }
        return None


    def set(self, user, new_score):
        score_time = time_now()

        self._read_leaderboard()
        try:
            users_score = self.user_scores[user.username]
            old_score = users_score.score

            if (self.sort_by == 1 and old_score >= new_score) or (self.sort_by == -1 and old_score <= new_score):
                return {'bestScore': old_score}

            users_score.score = new_score
            users_score.score_time = score_time

            if self.aggregate:
                self.aggregate_score += new_score - old_score
            self._write_leaderboard()
            return {'newBest': True, 'prevBest': old_score}
        except KeyError:
            # User has no score on the leaderboard
            self._add_score(UserScore(user.username, new_score, score_time))
            self._write_leaderboard()
            return {'newBest': True}


    def remove(self):
        self._empty_leaderboard()


class GameLeaderboards(object):

    def __init__(self, game):
        self.leaderboards = {}
        self.ordered_leaderboards = []
        self.leaderboard_path = None

        self.issues = []

        yaml_path = unicode(get_absolute_path(join_path(game.path, 'leaderboards.yaml')))
        total_yaml_errors = 0
        if path_exists(yaml_path):
            try:
                f = open(yaml_path, 'r')
                try:
                    file_meta = yaml.load(f)

                    for (i, m) in enumerate(file_meta):
                        key = m['key']
                        leaderboard = Leaderboard(game, key, m, i)

                        num_errors = len(leaderboard.errors)
                        if num_errors > 0:
                            total_yaml_errors += num_errors
                            self.issues.append((key, {
                                'errors': leaderboard.errors,
                                'warnings': leaderboard.warnings
                            }))
                        elif len(leaderboard.warnings) > 0:
                            self.issues.append((key, {
                                'errors': leaderboard.errors,
                                'warnings': leaderboard.warnings
                            }))

                        self.leaderboards[key] = leaderboard
                        self.ordered_leaderboards.append(leaderboard)
                finally:
                    f.close()
            except (IOError, yaml.YAMLError) as e:
                LOG.error('Failed loading leaderboards: %s', str(e))
                raise LeaderboardError('Failed loading leaderboards.yaml file: %s' % str(e))
        else:
            raise LeaderboardsUnsupported()

        if total_yaml_errors > 0:
            raise ValidationException(self.issues)


    def _get_leaderboard(self, key):
        try:
            return self.leaderboards[key]
        except KeyError:
            raise LeaderboardError('No leaderboard with key %s' % key, 404)


    def read_meta(self):
        return [l.to_dict() for l in self.ordered_leaderboards]


    def read_overview(self, user):
        result = []
        for l in self.ordered_leaderboards:
            overview = l.read_overview(user)
            if overview:
                result.append(overview)
        return result

    def read_aggregates(self):
        return [l.read_aggregates() for l in self.ordered_leaderboards if l.aggregate]

    def get_top_players(self, key, user, num_top_players):
        return self._get_leaderboard(key).get_top_players(user, num_top_players)


    def get_page(self, key, user, num_top_players, is_above, score, score_time):
        return self._get_leaderboard(key).get_page(user, num_top_players, is_above, score, score_time)


    def get_near(self, key, user, num_near):
        return self._get_leaderboard(key).get_near(user, num_near)


    def set(self, key, user, score):
        return self._get_leaderboard(key).set(user, score)


    def remove_all(self):
        for key in self.leaderboards:
            self.leaderboards[key].remove()


class LeaderboardsList(object):
    game_leaderboards = {}

    @classmethod
    def load(cls, game):
        game_leaderboard = GameLeaderboards(game)
        cls.game_leaderboards[game.slug] = game_leaderboard
        return game_leaderboard


    @classmethod
    def get(cls, game):
        try:
            return cls.game_leaderboards[game.slug]
        except KeyError:
            return cls.load(game)

    # for testing only
    @classmethod
    def reset(cls):
        cls.game_leaderboards = {}
