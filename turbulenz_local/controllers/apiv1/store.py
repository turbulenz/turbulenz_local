# Copyright (c) 2012-2013 Turbulenz Limited

from simplejson import JSONDecoder, JSONDecodeError

# pylint: disable=F0401
from pylons import request, response
# pylint: enable=F0401

from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.lib.servicestatus import ServiceStatus
from turbulenz_local.lib.money import get_currency_meta
from turbulenz_local.decorators import jsonify, postonly, secure_post

from turbulenz_local.controllers import BaseController

from turbulenz_local.models.gamesessionlist import GameSessionList
from turbulenz_local.models.apiv1.store import StoreList, StoreError, StoreUnsupported, \
                                                   Transaction, ConsumeTransaction, UserTransactionsList

from turbulenz_local.models.gamelist import get_game_by_slug
from turbulenz_local.models.userlist import get_current_user

# pylint: disable=C0103
_json_decoder = JSONDecoder(encoding='utf-8')
# pylint: enable=C0103


class StoreController(BaseController):
    """ StoreController consists of all the store methods
    """

    store_service = ServiceStatus.check_status_decorator('store')
    game_session_list = GameSessionList.get_instance()

    @classmethod
    @store_service
    @jsonify
    def get_currency_meta(cls):
        return {'ok': True, 'data': get_currency_meta()}

    @classmethod
    @store_service
    @jsonify
    def read_meta(cls, slug):
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with slug %s' % slug}

        try:
            store = StoreList.get(game)
            return {'ok': True, 'data': {'items': store.read_meta(), 'resources': store.read_resources()}}

        except StoreUnsupported:
            return {'ok': True, 'data': {'items': {}, 'resources': {}}}
        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @store_service
    @jsonify
    def read_user_items(cls, slug):
        user = get_current_user()
        game = get_game_by_slug(slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with slug %s' % slug}

        try:
            store = StoreList.get(game)
            store_user = store.get_store_user(user)
            return {'ok': True, 'data': {'userItems': store_user.get_items()}}

        except StoreUnsupported:
            return {'ok': True, 'data': {'userItems': {}}}
        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @store_service
    @secure_post
    def consume_user_items(cls, params=None):
        session = cls._get_gamesession(params)

        try:
            def get_param(param):
                value = params[param]
                if value is None:
                    raise KeyError(param)
                return value

            consume_item = get_param('key')
            consume_amount = get_param('consume')
            token = get_param('token')
            gamesession_id = get_param('gameSessionId')
        except KeyError as e:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing parameter %s' % str(e)}

        try:
            game = session.game
            user = session.user

            store = StoreList.get(game)

            transactions = UserTransactionsList.get(user)

            # check if the transaction has already been attempted
            consume_transaction = transactions.get_consume_transaction(gamesession_id, token)

            new_consume_transaction = ConsumeTransaction(user, game, consume_item,
                                                         consume_amount, gamesession_id, token)
            if consume_transaction is None:
                consume_transaction = new_consume_transaction
            elif not consume_transaction.check_match(new_consume_transaction):
                response.status_int = 400
                return {'ok': False, 'msg': 'Reused session token'}

            if not consume_transaction.consumed:
                consume_transaction.consume()

            store_user = store.get_store_user(user)
            return {'ok': True, 'data': {'consumed': consume_transaction.consumed,
                                         'userItems': store_user.get_items()}}

        except StoreUnsupported:
            return {'ok': True, 'data': {'compareAndSet': False, 'userItems': {}}}
        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}

    @classmethod
    @store_service
    @postonly
    @jsonify
    def remove_all(cls, slug):
        user = get_current_user()
        game = get_game_by_slug(slug)

        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with slug %s' % slug}

        try:
            store = StoreList.get(game)
            store.get_store_user(user).remove_items()
            return {'ok': True}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @store_service
    @postonly
    @jsonify
    def checkout_transaction(cls):
        user = get_current_user()

        try:
            game_slug = request.POST['gameSlug']
            transaction_items_json = request.POST['basket']
        except KeyError as e:
            response.status_int = 400
            return {'ok': False, 'msg': 'Missing parameter %s' % str(e)}

        try:
            transaction_items = _json_decoder.decode(transaction_items_json)
        except JSONDecodeError as e:
            response.status_int = 400
            return {'ok': False, 'msg': 'Basket parameter JSON error: %s' % str(e)}

        if not isinstance(transaction_items, dict):
            response.status_int = 400
            return {'ok': False, 'msg': 'Basket parameter JSON must be a dictionary'}

        game = get_game_by_slug(game_slug)
        if game is None:
            response.status_int = 404
            return {'ok': False, 'msg': 'No game with slug %s' % game_slug}

        try:
            transaction = Transaction(user, game, transaction_items)
            return {'ok': True, 'data': {'transactionId': transaction.id}}
        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @store_service
    @postonly
    @jsonify
    def pay_transaction(cls, transaction_id):
        user = get_current_user()

        try:
            user_transactions = UserTransactionsList.get(user)
            transaction = user_transactions.get_transaction(transaction_id)
            transaction.pay()

            return {'ok': True, 'data': transaction.status()}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}


    @classmethod
    @store_service
    @jsonify
    def read_transaction_status(cls, transaction_id):
        user = get_current_user()

        try:
            user_transactions = UserTransactionsList.get(user)
            transaction = user_transactions.get_transaction(transaction_id)

            return {'ok': True, 'data': transaction.status()}

        except ValidationException as e:
            response.status_int = 400
            return {'ok': False, 'msg': str(e)}
        except StoreError as e:
            response.status_int = e.response_code
            return {'ok': False, 'msg': str(e)}
