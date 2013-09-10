# Copyright (c) 2012-2013 Turbulenz Limited

import logging
LOG = logging.getLogger(__name__)

from re import compile as regex_compile
from time import time as time_now
from os.path import exists as path_exists, join as join_path

from threading import Lock

# pylint: disable=F0401
from pylons import config
import yaml
from paste.deploy.converters import asbool
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, create_dir
from turbulenz_local.lib.validation import ValidationException
from turbulenz_local.lib.tools import create_id
from turbulenz_local.lib.money import Money, get_currency

STORE_PRICING_TYPES = ['own', 'consume']

# TODO allow other currencies
DEFAULT_CURRENCY_TYPE = 'USD'
DEFAULT_CURRENCY = get_currency(DEFAULT_CURRENCY_TYPE)


class StoreError(Exception):
    def __init__(self, value, response_code=400):
        super(StoreError, self).__init__()
        self.value = value
        self.response_code = response_code

    def __str__(self):
        return self.value


class StoreUnsupported(StoreError):
    def __init__(self):
        super(StoreUnsupported, self).__init__('This game does not support a store', 404)


class StoreInvalidTransactionId(StoreError):
    def __init__(self):
        super(StoreInvalidTransactionId, self).__init__('Transaction id not found', 404)


class StoreItem(object):

    validate_key = regex_compile('^[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*$')

    def __init__(self, game, meta_data, existing_keys):
        self.errors = []
        self.warnings = []
        self.path = None

        self.game = game
        self.index = None

        if not isinstance(meta_data, dict):
            raise StoreError('YAML file item must be a dictionary')

        try:
            key = meta_data['key']
        except KeyError:
            raise StoreError('YAML file item missing key property')

        if not self.validate_key.match(key):
            self.error('invalid key format')
        self.key = key

        if key in existing_keys:
            self.error('duplicate key "%s"' % key)
        existing_keys.add(key)

        if 'title' not in meta_data or meta_data['title'] is None:
            self.error('title property missing for store item "%s"' % key)
            self.title = ''
        else:
            self.title = meta_data['title']

        if 'description' not in meta_data or meta_data['description'] is None:
            self.error('description property missing for store item "%s"' % key)
            self.description = ''
        else:
            self.description = meta_data['description']

        if 'icon' in meta_data:
            self.warning('"icon" yaml property has been deprecated please use '
                         '"icon256", "icon48" or "icon32" for store key "%s"' % key)

    def error(self, msg):
        self.errors.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)


class StoreOffering(StoreItem):

    def __init__(self, game, meta_data, offering_keys, resource_keys):
        super(StoreOffering, self).__init__(game, meta_data, offering_keys)

        prices = meta_data.get('price', meta_data.get('prices'))
        if prices is None:
            self.error('price property missing for store offering "%s"' % self.key)
            prices = {DEFAULT_CURRENCY_TYPE: 1}

        self.prices = {}
        for currency, currency_price in prices.items():
            if currency_price <= 0:
                self.error('price %s must be greater than zero for store offering "%s"' % (currency, self.key))
            try:
                self.prices[currency] = Money(get_currency(currency), currency_price)
            except TypeError:
                self.error('price %s invalid precision for store offering "%s" using default 1 %s'
                            % (currency, self.key, currency))
                self.prices[currency] = Money(get_currency(currency), 1)

        output = meta_data.get('output')
        if output is None:
            self.error('output property missing for store offering "%s"' % self.key)
            output = {}

        if not isinstance(output, dict):
            self.error('output property should be a dictionary for store offering "%s"' % self.key)
            output = {}

        self.output = {}
        for output_key, output_amount in output.items():
            if output_key not in resource_keys:
                self.error('no resource with key "%s".' % output_key)
            elif not isinstance(output_amount, int):
                self.error('output key "%s" amount must be an integer.' % output_key)
            elif output_amount <= 0:
                self.error('output key "%s" amount must be greater than zero.' % output_key)
            else:
                self.output[output_key] = output_amount

        try:
            self.available = asbool(meta_data.get('available', True))
        except ValueError:
            self.error('available property must be a boolean value.')

    def to_dict(self):
        return {'index': self.index,
                'title': self.title,
                'description': self.description,
                'images': {
                    'img32': u'',
                    'img48': u'',
                    'img256': u'',
                },
                'output': self.output,
                'prices': dict((k, v.get_minor_amount()) for k, v in self.prices.items()),
                'available': self.available}


    def get_price(self):
        return self.prices[DEFAULT_CURRENCY_TYPE]


class StoreResource(StoreItem):

    def __init__(self, game, meta_data, resource_keys):
        super(StoreResource, self).__init__(game, meta_data, resource_keys)

        self.type = meta_data.get('type')
        if self.type not in STORE_PRICING_TYPES:
            self.error('type property must be one of %s for store resource "%s"' % (str(STORE_PRICING_TYPES), self.key))
            self.type = 'own'

    def to_dict(self):
        return {'index': self.index,
                'title': self.title,
                'description': self.description,
                'images': {
                    'img32': u'',
                    'img48': u'',
                    'img256': u'',
                },
                'type': self.type}


class StoreUserGameItems(object):

    def __init__(self, user, game, game_store_items):
        self.user = user
        self.game = game
        self.game_store_items = game_store_items
        self.user_items = {}

        try:
            path = config['storeitems_db']
        except KeyError:
            LOG.error('storeitems_db path config variable not set')
            return

        # Create store items folder and user folder on the game path
        path = join_path(path, self.game.slug)
        if not create_dir(path):
            raise StoreError('User store items path \"%s\" could not be created.' % path)
        self.path = get_absolute_path(path)
        self.lock = Lock()
        self._read()


    def _read(self):
        with self.lock:
            unicode_path = unicode('%s/%s.yaml' % (self.path, self.user.username))
            if path_exists(unicode_path):
                try:
                    with open(unicode_path, 'r') as f:
                        file_store_items = yaml.load(f)

                        self.user_items = {}
                        if file_store_items:
                            for item in file_store_items:
                                item_amount = file_store_items[item]['amount']
                                self.user_items[str(item)] = {
                                    'amount': item_amount
                                }
                except (IOError, KeyError, yaml.YAMLError) as e:
                    LOG.error('Failed loading store items file "%s": %s', self.path, str(e))
                    raise StoreError('Failed loading store items file "%s": %s' % (self.path, str(e)))

            else:
                self.user_items = {}


    def _write(self):
        with self.lock:
            try:
                with open(unicode('%s/%s.yaml' % (self.path, self.user.username)), 'w') as f:
                    yaml.dump(self.user_items, f, default_flow_style=False)
            except IOError as e:
                LOG.error('Failed writing store items file "%s": %s', self.path, str(e))
                raise StoreError('Failed writing store items file %s' % self.path)


    def get_items(self):
        return dict((key, self.get_item(key)) for key in self.user_items.keys())


    def get_item(self, key):
        try:
            if self.game_store_items.get_resource(key).type == 'own' and self.user_items[key]['amount'] > 1:
                return {'amount': 1}
        except StoreError:
            pass
        return self.user_items[key]


    def remove_items(self):
        self.user_items = {}
        self._write()


    def transfer_items(self, transaction):
        for item_key, item in transaction.items.items():
            for resource_key, output_amount in self.game_store_items.get_offering(item_key).output.items():
                amount = item['amount'] * output_amount

                user_item = self.user_items.get(resource_key)
                if user_item:
                    user_item['amount'] += amount
                else:
                    self.user_items[str(resource_key)] = {
                        'amount': amount
                    }
        self._write()


    def consume_items(self, consume_transaction):
        item_key = consume_transaction.key
        try:
            user_item_amount = self.user_items[item_key]['amount']
            if user_item_amount < consume_transaction.consume_amount:
                # current values must match in order to apply the transaction
                return False
        except KeyError:
            return False

        new = user_item_amount - consume_transaction.consume_amount
        if new == 0:
            del self.user_items[item_key]
        else:
            self.user_items[item_key]['amount'] = new

        self._write()
        return True


    def reset_all_transactions(self):
        self.user_items = {}


class StoreUserList(object):

    def __init__(self, game, game_store_items):
        self.users = {}
        self.game = game
        self.game_store_items = game_store_items


    def get(self, user):
        try:
            return self.users[user.username]
        except KeyError:
            store_user = StoreUserGameItems(user, self.game, self.game_store_items)
            self.users[user.username] = store_user
            return store_user


class GameStoreItems(object):

    def __init__(self, game):
        self.offerings = {}
        self.resources = {}
        self.issues = []

        total_yaml_errors = 0
        def add_infos(key, item):
            num_errors = len(item.errors)
            if num_errors > 0 or len(item.warnings) > 0:
                self.issues.append((key, {
                    'errors': item.errors,
                    'warnings': item.warnings
                }))
            return num_errors

        yaml_path = unicode(get_absolute_path(join_path(game.path, 'storeitems.yaml')))
        if path_exists(yaml_path):
            try:
                with open(yaml_path, 'r') as f:
                    items_meta = yaml.load(f)

                    resource_keys = set()
                    offering_keys = set()
                    if isinstance(items_meta, list):
                        for index, m in enumerate(items_meta):
                            resource = StoreResource(game, m, resource_keys)
                            resource.index = index

                            total_yaml_errors += add_infos(resource.key, resource)
                            self.resources[resource.key] = resource

                        index = 0
                        items_meta_end = len(items_meta) - 1
                        for m in items_meta:
                            try:
                                m['output'] = {m['key']: 1}
                            except KeyError:
                                raise StoreError('Store item YAML item missing key')

                            offering = StoreOffering(game, m, offering_keys, resource_keys)
                            # put unavailable items at the end
                            if offering.available:
                                offering.index = index
                                index += 1
                            else:
                                offering.index = items_meta_end
                                items_meta_end -= 1

                            total_yaml_errors += add_infos(offering.key, offering)
                            self.offerings[offering.key] = offering

                    elif isinstance(items_meta, dict):
                        resource_meta = items_meta.get('resources')
                        if not isinstance(resource_meta, list):
                            raise StoreError('Store items YAML file must contain "resources"')

                        for index, m in enumerate(resource_meta):
                            resource = StoreResource(game, m, resource_keys)
                            resource.index = index

                            total_yaml_errors += add_infos(resource.key, resource)
                            self.resources[resource.key] = resource

                        offerings_meta = items_meta.get('offerings')
                        if not isinstance(offerings_meta, list):
                            raise StoreError('Store items YAML file must contain "offerings"')

                        index = 0
                        items_meta_end = len(offerings_meta) - 1
                        for m in offerings_meta:
                            offering = StoreOffering(game, m, offering_keys, resource_keys)
                            # put unavailable items at the end
                            if offering.available:
                                offering.index = index
                                index += 1
                            else:
                                offering.index = items_meta_end
                                items_meta_end -= 1


                            total_yaml_errors += add_infos(offering.key, offering)
                            self.offerings[offering.key] = offering

                    else:
                        raise StoreError('Store items YAML file must be a dictionary or list')
            except (IOError, yaml.YAMLError) as e:
                LOG.error('Failed loading store items: %s', str(e))
                raise StoreError('Failed loading storeitems.yaml file: %s' % str(e))
        else:
            raise StoreUnsupported()

        if total_yaml_errors > 0:
            raise ValidationException(self.issues)

        self.store_users = StoreUserList(game, self)


    def get_offering(self, key):
        try:
            return self.offerings[key]
        except KeyError:
            raise StoreError('No store offering with key %s' % key, 400)


    def get_resource(self, key):
        try:
            return self.resources[key]
        except KeyError:
            raise StoreError('No store resource with key %s' % key, 400)


    def get_store_user(self, user):
        return self.store_users.get(user)


    def read_meta(self):
        return dict((offering.key, offering.to_dict()) for offering in self.offerings.values())


    def read_resources(self):
        return dict((resource.key, resource.to_dict()) for resource in self.resources.values())


class ConsumeTransaction(object):

    def __init__(self, user, game, resource_key,
                 consume_amount, gamesession_id, token):

        self.user = user
        self.game = game
        self.id = create_id()
        self.key = resource_key
        self.gamesession_id = gamesession_id
        self.token = token
        self.consumed = False

        # validation step
        try:
            consume_amount = int(consume_amount)
        except ValueError:
            raise StoreError('Item "%s" consume amount parameters must be an integer' % resource_key)

        self.consume_amount = consume_amount

        if consume_amount <= 0:
            raise StoreError('Item "%s" consume amount parameter must be non-negative' % resource_key)

        game_store_items = StoreList.get(game)
        try:
            resource_meta = game_store_items.get_resource(resource_key)
            if resource_meta.type != 'consume':
                raise StoreError('Item "%s" is not a consumable' % resource_key)
        except KeyError:
            raise StoreError('No item with key "%s"' % resource_key)

    def check_match(self, other):
        return (self.user.username == other.user.username and
                self.game.slug == other.game.slug and
                self.key == other.key and
                self.gamesession_id == other.gamesession_id and
                self.token == other.token and
                self.consume_amount == other.consume_amount)

    def consume(self):
        game_store_items = StoreList.get(self.game)
        store_user = game_store_items.get_store_user(self.user)
        self.consumed = store_user.consume_items(self)
        UserTransactionsList.get(self.user).add_consume_transaction(self.gamesession_id, self.token, self)


class Transaction(object):

    def __init__(self, user, game, transaction_items):
        self.user = user
        self.game = game
        self.id = create_id()
        self.items = transaction_items

        total = 0

        game_store_items = StoreList.get(game)

        for item_key, item in transaction_items.items():
            try:
                # convert string amounts to integers
                basket_amount = int(item['amount'])
                basket_price = int(item['price'])
            except (ValueError, KeyError, TypeError):
                raise StoreError('Item "%s" amount and price must be integers' % item_key)

            if basket_amount == 0:
                continue
            elif basket_amount < 0:
                raise StoreError('Item "%s" amount must be non-negative' % item_key)

            game_offering = game_store_items.get_offering(item_key)

            minor_price = game_offering.get_price().get_minor_amount()

            if basket_price != minor_price:
                raise StoreError('Item "%s" price does not match' % item_key)

            self.items[item_key] = {
                'price': basket_price,
                'amount': basket_amount
            }

            total += minor_price * basket_amount

        self.total = total

        self.completed = False
        self.completed_time = None

        UserTransactionsList.get(user).add_transaction(self.id, self)


    def pay(self):
        if self.completed:
            return
        game_store_items = StoreList.get(self.game)
        store_user = game_store_items.get_store_user(self.user)
        store_user.transfer_items(self)

        self.completed_time = time_now()
        self.completed = True


    def status(self):
        if self.completed:
            return {'status': 'completed'}
        else:
            return {'status': 'checkout'}


class TransactionsList(object):

    def __init__(self, user):
        self.transactions = {}
        self.consume_transactions = {}
        self.user = user


    def add_transaction(self, transaction_id, transaction):
        self.transactions[transaction_id] = transaction


    def add_consume_transaction(self, gamesession_id, token, consume_transaction):
        if gamesession_id in self.consume_transactions:
            self.consume_transactions[gamesession_id][token] = consume_transaction
        else:
            self.consume_transactions[gamesession_id] = {
                token: consume_transaction
            }


    def get_transaction(self, transaction_id):
        try:
            return self.transactions[transaction_id]
        except KeyError:
            raise StoreInvalidTransactionId()


    def get_consume_transaction(self, gamesession_id, token):
        try:
            return self.consume_transactions[gamesession_id][token]
        except (KeyError, TypeError):
            return None


# A dictionary of username to transaction list objects
class UserTransactionsList(object):
    user_transactions = {}

    @classmethod
    def load(cls, user):
        user_transactions_list = TransactionsList(user.username)
        cls.user_transactions[user.username] = user_transactions_list
        return user_transactions_list


    @classmethod
    def get(cls, user):
        try:
            return cls.user_transactions[user.username]
        except KeyError:
            return cls.load(user)


# A dictionary of game slug to store items objects
class StoreList(object):
    game_stores = {}

    @classmethod
    def load(cls, game):
        game_store = GameStoreItems(game)
        cls.game_stores[game.slug] = game_store
        return game_store


    @classmethod
    def get(cls, game):
        try:
            return cls.game_stores[game.slug]
        except KeyError:
            return cls.load(game)

    @classmethod
    def reset(cls):
        cls.game_stores = {}
