# Copyright (c) 2010-2011,2013 Turbulenz Limited

import csv
import errno
import logging

from os import listdir, makedirs, remove, rename
from os.path import exists, isdir, join, splitext
from StringIO import StringIO
from shutil import rmtree
from time import time

import simplejson as json

from pylons import config

LOG = logging.getLogger(__name__)

class MetricsSession(object):

    keys = ['file', 'ext', 'size', 'type', 'time', 'status']

    _slug_sessions = {}
    _last_timestamp = 0

    def __init__(self, slug):

        self.entries = [ ]
        self.slug = slug

        # make sure we have a unique timestamp
        timestamp = '%.8f' % time()
        if MetricsSession._last_timestamp == timestamp:
            timestamp += '1'
        MetricsSession._last_timestamp = timestamp
        self.timestamp = timestamp

        # work out the filename to be used
        self.file_name = MetricsSession.get_file_name(slug, timestamp)

        LOG.info('New metrics session started timestamp %s', timestamp)

    def __del__(self):
        self.finish()

    def append(self, file_name, file_size, file_type, file_status):
        _, file_ext = splitext(file_name)

        entry = {
            "file": file_name,
            "ext": file_ext,
            "size": int(file_size),
            "type": file_type,
            "time": time(),
            "status": file_status
        }

        self.entries.append(entry)

    def get_file_path(self):
        return self.file_name

    def finish(self):

        # make sure path exists
        folder_name = MetricsSession.get_folder_name(self.slug)

        if not exists(folder_name):
            # Due to race conditions we still need the try/except
            try:
                makedirs(folder_name)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    LOG.error(str(e))
                    raise

        LOG.info('Metrics session saving to %s', self.file_name)

        session = { 'entries': self.entries }

        try:
            f = open(self.file_name, mode='w')
            json.dump(session, f, indent=4)
            f.close()
        except IOError, e:
            LOG.error(str(e))

    @classmethod
    def get_folder_name(cls, slug):
        return join(config['metrics.base_path'], slug)

    @classmethod
    def get_file_name(cls, slug, timestamp):
        return join(cls.get_folder_name(slug), '%s.json' % timestamp)

    @classmethod
    def get_csv_file_name(cls, slug, timestamp):
        return join(cls.get_folder_name(slug), '%s.csv' % timestamp)

    @classmethod
    def get_data(cls, slug, timestamp):
        file_name = cls.get_file_name(slug, timestamp)
        try:
            f = open(file_name, mode='r')
            session_data = json.load(f)
            f.close()
        except (IOError, json.JSONDecodeError):
            session_data = ''
        return session_data

    @classmethod
    def get_data_as_csv(cls, slug, timestamp):
        csv_buffer = StringIO()
        file_name = cls.get_file_name(slug, timestamp)

        keys = MetricsSession.keys
        try:
            with open(file_name, 'r') as f:
                session_data = json.load(f)
                rows = session_data['entries']
        except IOError:
            return None
        else:
            writer = csv.DictWriter(csv_buffer, keys)
            writer.writerow(dict(zip(keys, keys)))
            for row in rows:
                writer.writerow(row)

            csv_data = csv_buffer.getvalue()
            csv_buffer.close()

            return csv_data

    @classmethod
    def get_data_as_json(cls, slug, timestamp):
        file_name = cls.get_file_name(slug, timestamp)
        try:
            f = open(file_name, 'r')
            session_data = f.read()
            f.close()
        except IOError:
            return None
        else:
            return session_data

    @classmethod
    def delete(cls, slug, timestamp):
        if timestamp:
            file_name = cls.get_file_name(slug, timestamp)
            try:
                remove(file_name)
            except OSError:
                return False
        else:
            rmtree(cls.get_folder_name(slug), True)
        return True

    @classmethod
    def rename(cls, old_slug, new_slug):
        old_folder = cls.get_folder_name(old_slug)
        new_folder =  cls.get_folder_name(new_slug)

        # delete the new folder is necessary, otherwise the
        # old one will just end up inside of it
        try:
            rmtree(new_folder)
        except OSError:
            pass
        try:
            rename(old_folder, new_folder)
        except OSError:
            pass

    @classmethod
    def stop_recording(cls, slug):
        try:
            del cls._slug_sessions[slug]
        except KeyError:
            return False
        else:
            return True

    @classmethod
    def has_metrics(cls, slug):
        if slug in cls._slug_sessions:
            return True

        folder_name = cls.get_folder_name(slug)
        if isdir(folder_name):
            for f in listdir(folder_name):
                if f.endswith('.json'):
                    return True
        return False

    @classmethod
    def get_metrics(cls, slug):
        cls.stop_recording(slug)

        folder_name = cls.get_folder_name(slug)
        if isdir(folder_name):
            timestamps = [f[:-5] for f in listdir(folder_name) if f.endswith('.json')]
            timestamps.sort()
            return [{'timestamp': t, 'entries': cls.get_data(slug, t)['entries']} for t in timestamps]
        else:
            return [ ]

    @classmethod
    def get_sessions(cls, slug):
        try:
            slug_sessions = cls._slug_sessions[slug]
        except KeyError:
            slug_sessions = {}
            cls._slug_sessions[slug] = slug_sessions
        return slug_sessions
