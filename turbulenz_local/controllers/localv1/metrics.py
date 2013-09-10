# Copyright (c) 2010-2011,2013 Turbulenz Limited

import logging
import time
import os.path

from pylons import response
from pylons.controllers.util import abort

from turbulenz_local.decorators import jsonify
from turbulenz_local.controllers import BaseController
from turbulenz_local.models.metrics import MetricsSession
from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.tools import humanize_filesize as hf, load_json_asset

LOG = logging.getLogger(__name__)


class _Session(object):
    def __init__(self, timestamp):
        self.time = time.ctime(float(timestamp))
        self.timestamp = timestamp
        self.num_files = 0
        self.num_requests = 0
        self.size = 0
        self.total_size = 0
        self.h_size = None
        self.h_total_size = None

    def add_request(self, size):
        self.num_requests += 1
        self.total_size += size

    def add_file(self, size):
        self.num_files += 1
        self.size += size

    def humanize(self):
        self.h_size = hf(self.size)
        self.h_total_size = hf(self.total_size)

class _File(object):
    def __init__(self, name, request_name, size, mimetype, status):
        self.name = name
        self.size = size
        self.h_size = hf(size)
        self.num_requests = 0
        self.type = mimetype
        self.status = status

    def add_request(self):
        self.num_requests += 1


#######################################################################################################################

def get_inverse_mapping_table(game):
    # We invert the mapping table so that it is quicker to find the assets.
    inverse_mapping = { }

    # Load mapping table
    j = load_json_asset(os.path.join(game.path, game.mapping_table))
    if j:
        # pylint: disable=E1103
        urnmapping = j.get('urnmapping') or j.get('urnremapping', {})
        # pylint: enable=E1103
        for k, v in urnmapping.iteritems():
            inverse_mapping[v] = k

    return inverse_mapping

#######################################################################################################################

class MetricsController(BaseController):

    def __init__(self):
        BaseController.__init__(self)
        self._session_overviews = [ ]
        self._session_files = { }

    def _update_metrics(self, slug, game):
        metrics = MetricsSession.get_metrics(slug)
        inverse_mapping = get_inverse_mapping_table(game)

        for session in metrics:
            try:
                s = _Session(session['timestamp'])
                fileDict = {}

                for entry in session['entries']:
                    try:
                        (filename, size, mimetype, status) = \
                            (entry['file'], int(entry['size']), entry['type'], entry['status'])
                    except TypeError:
                        break

                    try:
                        asset_name = inverse_mapping[os.path.basename(filename)]
                    except KeyError:
                        asset_name = filename
                    _, ext = os.path.splitext(asset_name)
                    ext = ext[1:] if ext else 'unknown'

                    # Add the request to the session.
                    s.add_request(size)

                    # Add the request to the by_file metrics.
                    if filename not in fileDict:
                        fileDict[filename] = _File(asset_name, filename, size, mimetype, status)
                        s.add_file(size)

                s.humanize()

                timestamp = s.timestamp
                self._session_overviews.append((timestamp, s))

            except KeyError as e:
                LOG.error("Potentially corrupted file found. Can't extract metrics data: %s", str(e))

    def _get_overviews(self, game, reverse=True):
        self._session_overviews.sort(reverse=reverse)
        return [e[1] for e in self._session_overviews]

    ###################################################################################################################

    @jsonify
    def overview(self, slug):
        """
        Display the game's metrics
        """
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        self._update_metrics(slug, game)
        return {
            'ok': True,
            'data': {
                'staticFilePrefix' : 'staticmax/',
                'mappingTable': game.mapping_table,
                'slug': game.slug,
                'title': game.title,
                'sessions': [ {
                    'time': s.time,
                    'timeStamp': s.timestamp,
                    'numFiles': s.num_files,
                    'numRequests': s.num_requests,
                    'humanSize': s.h_size,
                    'humanTotalSize': s.h_total_size
                } for s in self._get_overviews(slug) ],
            }
        }

    @jsonify
    def details(self, slug, timestamp):
        game = get_game_by_slug(slug)
        if not game:
            response.status_int = 404
            return {'ok': False, 'msg': 'Game does not exist: %s' % slug}

        self._update_metrics(slug, game)
        session = MetricsSession.get_data(slug, timestamp)
        if not session:
            response.status_int = 404
            return {'ok': False, 'msg': 'Session does not exist: %s' % timestamp}

        return {'ok': True, 'data': session}

    @classmethod
    @jsonify
    def delete(cls, slug, timestamp):
        if not MetricsSession.delete(slug, timestamp):
            response.status_int = 404
            return {'ok': False, 'msg': 'Session does not exist: %s' % timestamp}

        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0'
        return {'ok': True}

    @classmethod
    def as_csv(cls, slug, timestamp):
        timestamp_format = '%Y-%m-%d_%H-%M-%S'
        try:
            filename = '%s-%s.csv' % (slug, time.strftime(timestamp_format, time.gmtime(float(timestamp))))
        except ValueError:
            abort(404, 'Invalid timestamp: %s' % timestamp)

        response.content_type = 'text/csv'
        response.content_disposition = 'attachment; filename=%s' % filename
        data = MetricsSession.get_data_as_csv(slug, timestamp)
        if not data:
            abort(404, 'Session does not exist: %s' % timestamp)

        return data

    @classmethod
    @jsonify
    def as_json(cls, slug, timestamp):
        timestamp_format = '%Y-%m-%d_%H-%M-%S'
        try:
            filename = '%s-%s.json' % (slug, time.strftime(timestamp_format, time.gmtime(float(timestamp))))
        except ValueError:
            abort(404, 'Invalid timestamp: %s' % timestamp)

        response.content_disposition = 'attachment; filename=%s' % filename
        data = MetricsSession.get_data_as_json(slug, timestamp)
        if not data:
            abort(404, 'Session does not exist: %s' % timestamp)

        return data


    @classmethod
    @jsonify
    def stop_recording(cls, slug):
        if MetricsSession.stop_recording(slug):
            return {'ok': True}
        else:
            response.status_int = 404
            return {'ok': False, 'msg': 'No active session for game: "%s"' % slug}
