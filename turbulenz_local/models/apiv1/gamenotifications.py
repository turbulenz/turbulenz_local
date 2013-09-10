# Copyright (c) 2011-2013 Turbulenz Limited

import logging
LOG = logging.getLogger(__name__)
from collections import defaultdict
from os import access, R_OK, remove as remove_file, listdir
from os.path import join as join_path, normpath as norm_path
from threading import Lock
from time import time as get_time

from simplejson import JSONEncoder, JSONDecoder

from turbulenz_local.lib.exceptions import ApiException

# pylint: disable=F0401
import yaml
from yaml import YAMLError
from pylons import config
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, create_dir

# pylint: disable=C0103
_json_decoder = JSONDecoder()
_json_encoder = JSONEncoder()
# pylint: enable=C0103

REQUIRED_NOTIFICATION_KEYS = ['key', 'title']



class GameNotificationsUnsupportedException(Exception):
    pass



class GameNotificationPathError(Exception):
    pass



class GameNotificationTaskError(Exception):
    pass



class GameNotificationSettingsError(Exception):
    pass



class GameNotificationKeys(object):

    def __init__(self, game):

        self.game = game

        self.abs_game_path = get_absolute_path(game.path)

        try:
            yaml_path = norm_path(get_absolute_path(join_path(game.path, 'gamenotifications.yaml')))
            if not access(yaml_path, R_OK):
                raise GameNotificationsUnsupportedException()

            with open(unicode(yaml_path), 'r') as f:
                notifications = {}
                for n_key in yaml.load(f):
                    notifications[n_key['key']] = n_key

                self._notifications = notifications

        except (IOError, KeyError) as e:
            LOG.error('Failed loading gamenotifications: %s', str(e))
            raise ApiException('Failed loading gamenotifications.yaml file %s' % str(e))


    def get_key(self, key):
        return self._notifications.get(key)


    def to_dict(self):
        return self._notifications


    def validate(self):
        result = []
        count = 0

        for notification in self._notifications.values():

            count += 1
            errors = []
            # collect keys that are missing from the badge or are not filled in
            for key in REQUIRED_NOTIFICATION_KEYS:

                if not notification.get(key):
                    errors.append('missing key: "%s"' % key)

            identifier = notification.get('title', notification.get('key', 'Badge #%i' % count))

            if errors:
                result.append((identifier, {'errors': errors}))

        return result



class GameNotificationKeysList(object):

    notification_key_dict = {}

    ## do some lazy loading here

    @classmethod
    def load(cls, game):
        keys = GameNotificationKeys(game)
        cls.notification_key_dict[game.slug] = keys
        return keys


    @classmethod
    def get(cls, game):
        return cls.notification_key_dict.get(game.slug) or cls.load(game)


    @classmethod
    def reset(cls):
        cls.notification_key_dict = {}



def _get_task_path(slug, recipient, notification_type, filename=None):
    try:
        path = config['notifications_db']
    except KeyError:
        raise GameNotificationsUnsupportedException('notifications_db path config variable not set')

    path = join_path(path, slug, recipient, notification_type)

    if not create_dir(path):
        raise GameNotificationPathError('User GameNotification path \"%s\" could not be created.' % path)

    if filename:
        return get_absolute_path(join_path(path, filename))
    else:
        return path



def _load_tasks(slug, recipient, notification_type):
    tasks = []
    num_tasks_per_sender = defaultdict(lambda: 0)
    task_ids = set()

    task_path = _get_task_path(slug, recipient, notification_type)
    for task_file in listdir(task_path):
        file_path = join_path(task_path, task_file)
        try:
            with open(file_path, 'rb') as f:
                json_dict = _json_decoder.decode(f.read())
                task = GameNotificationTask(**json_dict)
                task_ids.add(task.task_id)
                tasks.append(task)
                num_tasks_per_sender[task.sender] += 1
        except (IOError, OSError, TypeError) as e:
            LOG.error('Failed loading GameNotificationTask "%s": %s', file_path, str(e))

    tasks.sort(key=lambda task: task.time)

    return tasks, task_ids, num_tasks_per_sender



class GameNotificationTask(object):

    """
    GameNotificationTask represents a notification as it sits in the waiting-queue before being sent (polled)

    Here on the devserver it sits in a text-file in the userdata folder
    """

    INSTANT = 'instant'
    DELAYED = 'delayed'

    LIMIT = {
        INSTANT: 1,
        DELAYED: 8
    }

    def __init__(self, slug, task_id, key, sender, recipient, msg, time):
        self.task_id = task_id
        self.slug = slug
        self.key = key
        self.sender = sender
        self.recipient = recipient
        self.msg = msg
        self.time = time


    @property
    def notification_type(self):
        if self.time:
            return self.DELAYED

        return self.INSTANT


    def save(self):
        try:
            with open(self.get_path(), 'wb') as f:
                f.write(_json_encoder.encode(self.__dict__))
        except IOError, e:
            e = 'Failed writing GameNotificationTask: %s' % str(e)
            LOG.error(e)
            raise GameNotificationTaskError(e)


    def to_notification(self):
        return {
            'key': self.key,
            'sender': self.sender,
            'msg': self.msg,
            'sent': self.time or get_time()
        }


    def get_path(self):

        filename = str(self.task_id) + '.txt'
        return _get_task_path(self.slug, self.recipient, self.notification_type, filename)


    def remove(self):
        remove_file(self.get_path())



class GameNotificationTaskList(object):

    def __init__(self, slug, recipient):
        object.__init__(self)

        self._slug = slug
        self._recipient = recipient
        self._lock = Lock()

        instant = GameNotificationTask.INSTANT
        delayed = GameNotificationTask.DELAYED

        instant_tasks, instant_task_ids, num_instant_tasks_per_sender = \
            _load_tasks(slug, recipient, GameNotificationTask.INSTANT)

        delayed_tasks, delayed_task_ids, num_delayed_tasks_per_sender = \
            _load_tasks(slug, recipient, GameNotificationTask.DELAYED)

        self._tasks = {
            instant: instant_tasks,
            delayed: delayed_tasks
        }

        self._task_ids = {
            instant: instant_task_ids,
            delayed: delayed_task_ids
        }

        self._num_tasks_per_sender = {
            instant: num_instant_tasks_per_sender,
            delayed: num_delayed_tasks_per_sender
        }


    def add_task(self, task):
        notification_type = task.notification_type
        sender = task.sender


        if self._num_tasks_per_sender[notification_type][sender] >= task.LIMIT[notification_type]:
            return False

        with self._lock:
            ## save task to disk
            task.save()

            ## and add it to the list. This looks stupid but is much more efficient than appending and re-sorting.
            sendtime = task.time
            index = 0
            tasks = self._tasks[notification_type]

            for index, old_task in enumerate(tasks):
                if old_task.time > sendtime:
                    break

            tasks.insert(index, task)
            self._task_ids[notification_type].add(task.task_id)
            self._num_tasks_per_sender[notification_type][sender] += 1

            return True


    def poll_latest(self):
        current_time = get_time()
        tasks = []
        tasks_to_delete = []
        for tasks_by_type in self._tasks.itervalues():
            for task in tasks_by_type:

                if current_time < task.time:
                    break

                tasks.append(task.to_notification())
                tasks_to_delete.append(task)


        for task in tasks_to_delete:
            self.remove_task(task)

        return tasks


    def cancel_notification_by_id(self, task_id):

        for tasks_by_type in self._tasks.itervalues():
            for task in tasks_by_type:

                if task.task_id == task_id:
                    self.remove_task(task)
                    break


    def cancel_notification_by_key(self, key):

        for tasks_by_type in self._tasks.itervalues():
            tasks_to_remove = [task for task in tasks_by_type if task.key == key]

        for task in tasks_to_remove:
            self.remove_task(task)


    def cancel_all_notifications(self):
        for task_type, tasks_by_type in self._tasks.iteritems():
            for task in tasks_by_type:
                task.remove()

            self._tasks[task_type] = []
            self._task_ids[task_type].clear()
            self._num_tasks_per_sender[task_type].clear()


    def cancel_all_pending_notifications(self):
        current_time = get_time()

        tasks_to_delete = []

        for tasks_by_type in self._tasks.itervalues():
            for task in tasks_by_type:

                if current_time < task.time:
                    tasks_to_delete.append(task)
                else:
                    break

        for task in tasks_to_delete:
            self.remove_task(task)


    def has_task(self, task_id):
        for task_ids in self._task_ids.itervalues():
            if task_id in task_ids:
                return True
        return False


    def remove_task(self, task):
        notification_type = task.notification_type

        self._tasks[notification_type].remove(task)
        self._task_ids[notification_type].remove(task.task_id)
        self._num_tasks_per_sender[notification_type][task.sender] -= 1

        task.remove()



class GameNotificationTaskListManager(object):

    gnt_lists = defaultdict(lambda: {})

    @classmethod
    def load(cls, game, recipient):
        tasks = GameNotificationTaskList(game.slug, recipient)
        cls.gnt_lists[game.slug][recipient] = tasks
        return tasks


    @classmethod
    def get(cls, game, recipient):
        try:
            return cls.gnt_lists[game.slug][recipient]
        except KeyError:
            return cls.load(game, recipient)


    @classmethod
    def reset(cls):
        cls.gnt_lists = {}


    @classmethod
    def add_task(cls, game, task):

        tasklist = cls.get(game, task.recipient)
        return tasklist.add_task(task)


    @classmethod
    def poll_latest(cls, game, recipient):
        tasklist = cls.get(game, recipient)
        return tasklist.poll_latest()


    @classmethod
    def cancel_notification_by_id(cls, game, task_id):

        slug = game.slug
        if slug in cls.gnt_lists:
            for task_list in cls.gnt_lists[slug].itervalues():
                if task_list.has_task(task_id):
                    task_list.cancel_notification_by_id(task_id)
                    return True

        return False


    @classmethod
    def cancel_notification_by_key(cls, game, recipient, key):
        cls.get(game, recipient).cancel_notification_by_key(key)


    @classmethod
    def cancel_all_notifications(cls, game, recipient):
        cls.get(game, recipient).cancel_all_notifications()


    @classmethod
    def cancel_all_pending_notifications(cls, game, recipient):
        cls.get(game, recipient).cancel_all_pending_notifications()



def _get_settings_path():
    return norm_path(_get_task_path('', '', '', 'notificationsettings.yaml'))



def reset_game_notification_settings():

    try:

        yaml_path = _get_settings_path()
        with open(unicode(yaml_path), 'wb') as f:
            data = {
                'email_setting': 1,
                'site_setting': 1
            }
            yaml.safe_dump(data, f, default_flow_style=False)

    except IOError as e:
        s = 'Failed resetting gamenotifications.yaml file %s' % str(e)
        LOG.error(s)
        raise GameNotificationSettingsError(s)



def get_game_notification_settings():

    yaml_path = _get_settings_path()

    if not access(yaml_path, R_OK):
        reset_game_notification_settings()

    try:

        with open(unicode(yaml_path), 'rb') as f:
            data = yaml.load(f)
            return {
                'email_setting': int(data['email_setting']),
                'site_setting': int(data['site_setting'])
            }

    except (IOError, KeyError, TypeError, ValueError, YAMLError) as e:
        s = 'Failed loading notificationsettings.yaml file: %s' % str(e)
        LOG.error(s)
        raise GameNotificationSettingsError(s)
