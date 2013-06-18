# Copyright (c) 2013 Turbulenz Limited

from time import time
from simplejson import JSONDecoder, JSONDecodeError

# pylint: disable=F0401
from pylons import request, response
# pylint: enable=F0401

from turbulenz_local.controllers import BaseController
from turbulenz_local.decorators import jsonify, postonly

from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.lib.exceptions import BadRequest, NotFound
from turbulenz_local.lib.tools import create_id

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.userlist import get_current_user
from turbulenz_local.models.apiv1.gamenotifications import GameNotificationTask, reset_game_notification_settings, \
                                                           GameNotificationTaskError, GameNotificationPathError, \
                                                           GameNotificationsUnsupportedException, \
                                                           GameNotificationTaskListManager, \
                                                           GameNotificationSettingsError, \
                                                           get_game_notification_settings, GameNotificationKeysList

# pylint: disable=C0103
_json_decoder = JSONDecoder(encoding='utf-8')
# pylint: enable=C0103



def _get_user_name():
    return get_current_user().username

def _get_game(slug):

    game = get_game_by_slug(slug)
    if not game:
        raise NotFound('No game with slug %s' % slug)

    return game



class GamenotificationsController(BaseController):


    @classmethod
    @jsonify
    def read_usersettings(cls, slug):

        try:
            return {
                'ok': True,
                'data': get_game_notification_settings()
            }
        except (GameNotificationSettingsError, GameNotificationPathError):
            try:
                reset_game_notification_settings()

                response.status_int = 404
                return {'ok': False, 'msg': 'Error. Resetting yaml-file .. done.'}

            except (GameNotificationSettingsError, GameNotificationPathError):
                response.status_int = 404
                return {'ok': False, 'msg': 'Error. Please delete notificationsettings.yaml.'}


    @classmethod
    @jsonify
    def update_usersettings(cls, slug):
        return {'ok': True}


    @classmethod
    @jsonify
    def read_notification_keys(cls, slug):
        game = _get_game(slug)

        try:
            return {
                'ok': True,
                'data': {
                    'keys': GameNotificationKeysList.get(game).to_dict()
                }
            }

        except GameNotificationsUnsupportedException:
            return {'ok': True, 'data': {'items': {}, 'resources': {}}}
        except ValidationException as e:
            raise BadRequest(str(e))


    @classmethod
    def _get_task_data(cls, slug):

        game = _get_game(slug)

        user = _get_user_name()

        try:
            data = _json_decoder.decode(request.POST['data'])
        except KeyError:
            raise BadRequest('Missing parameter "data"')
        except JSONDecodeError as e:
            raise BadRequest('Data-parameter JSON error: %s' % str(e))

        if not isinstance(data, dict):
            raise BadRequest('Data-parameter is not a dict')

        # pylint: disable=E1103
        get_data = data.get
        # pylint: enable=E1103

        key = get_data('key')
        if not key:
            raise BadRequest('No notification-key given')
        ## check that the key actually exists on the game
        if key not in GameNotificationKeysList.get(game).to_dict():
            raise BadRequest('Unknown key "' + key + '" given.')

        msg = get_data('msg')
        if not msg:
            raise BadRequest('No message given')

        if not msg.get('text'):
            raise BadRequest('No text-attribute in msg')

        try:
            delay = int(get_data('time') or 0)
        except ValueError:
            raise BadRequest('Incorrect format for time')

        ## filter out empty strings and if there's just nothing there, use the current user as default recipient
        recipient = get_data('recipient', '').strip() or user

        return create_id(), key, user, recipient, msg, game, delay


    @classmethod
    def _add(cls, slug, task_id, key, sender, recipient, msg, send_time, game):

        try:

            task = GameNotificationTask(slug, task_id, key, sender, recipient, msg, send_time)

            if GameNotificationTaskListManager.add_task(game, task):
                return {
                    'ok': True,
                    'id': task_id
                }

            response.status_int = 429
            return {
                'ok': False,
                'msg': 'limit exceeded.'
            }

        except (GameNotificationTaskError, GameNotificationPathError) as e:
            raise BadRequest('NotificationTask could not be saved: %s' % str(e))


    @classmethod
    @postonly
    @jsonify
    def send_instant_notification(cls, slug):

        task_id, key, user, recipient, msg, game, _ = cls._get_task_data(slug)

        return cls._add(slug, task_id, key, user, recipient, msg, None, game)


    @classmethod
    @postonly
    @jsonify
    def send_delayed_notification(cls, slug):

        task_id, key, user, _, msg, game, delay = cls._get_task_data(slug)

        return cls._add(slug, task_id, key, user, user, msg, time() + delay, game)


    @classmethod
    @jsonify
    def poll_notifications(cls, slug):

        user = _get_user_name()

        game = _get_game(slug)

        return {
            'ok': True,
            'data': GameNotificationTaskListManager.poll_latest(game, user)
        }



    @classmethod
    @postonly
    @jsonify
    def cancel_notification_by_id(cls, slug):

        game = _get_game(slug)

        _id = request.POST.get('id')
        if not _id:
            raise BadRequest('No task-id given')

        GameNotificationTaskListManager.cancel_notification_by_id(game, _id)

        return { 'ok': True }



    @classmethod
    @postonly
    @jsonify
    def cancel_notification_by_key(cls, slug):

        game = _get_game(slug)

        user = _get_user_name()

        key = request.POST.get('key')
        if not key:
            raise BadRequest('No task-key given')

        GameNotificationTaskListManager.cancel_notification_by_key(game, user, key)

        return {'ok': True}


    @classmethod
    @postonly
    @jsonify
    def cancel_all_notifications(cls, slug):

        game = _get_game(slug)

        GameNotificationTaskListManager.cancel_all_notifications(game, _get_user_name())

        return {'ok': True}


    @classmethod
    @postonly
    @jsonify
    def init_manager(cls, slug):

        game = _get_game(slug)

        GameNotificationTaskListManager.cancel_all_notifications(game, _get_user_name())

        return {'ok': True}
