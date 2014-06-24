// Copyright (c) 2011-2012,2014 Turbulenz Limited

/*global $*/
/*global JsLocalStore*/
/*global Turbulenz*/

// TODO: replace this with https://github.com/jquery/globalize.git
// this is just to keep things simple for now
function Currency() {}

Currency.create = function currencyCreateFn(alphabeticCode, numericCode, minorUnitPrecision, currencyName)
{
    var currency = new Currency();

    currency.currencyName = currencyName;
    currency.alphabeticCode = alphabeticCode;
    currency.numericCode = numericCode;
    currency.minorUnitPrecision = minorUnitPrecision;

    currency.toMinorUnit = Math.pow(10, minorUnitPrecision);
    currency.toMajorUnit = Math.pow(10, -minorUnitPrecision);

    return currency;
};

function Money() {}

Money.prototype = {
    toMajorUnit: function toMajorUnit()
    {
        return (this.minorAmount * this.currency.toMajorUnit).toFixed(this.currency.minorUnitPrecision);
    },

    multiply: function multiplyFn(amount)
    {
        return Money.create(this.currency, this.minorAmount * amount);
    },

    add: function addFn(money)
    {
        if (this.currency !== money.currency)
        {
            throw 'Can not add Money quantities of different currencies';
        }
        return Money.create(this.currency, this.minorAmount + money.minorAmount);
    }
};

Money.create = function moneyCreateFn(currency, minorAmount)
{
    var money = new Money();

    money.currency = currency;
    money.minorAmount = minorAmount;

    return money;
};

function TurbulenzStore() {}

TurbulenzStore.prototype = {

    confirmPurchase: function confirmPurchaseFn()
    {
        var that = this;

        var calculatedBasket = this.calculateBasket();
        var transactionId;

        var basketItems = calculatedBasket.items;
        var basketGame = calculatedBasket.game;
        var basketData = {};
        var itemKey;
        var basketSize = 0;

        var gameOfferings = this.offerings[basketGame];
        if (!gameOfferings)
        {
            return;
        }

        for (itemKey in basketItems)
        {
            if (basketItems.hasOwnProperty(itemKey))
            {
                if (gameOfferings[itemKey])
                {
                    var basketItem = basketItems[itemKey];
                    basketSize += 1;
                    basketData[itemKey] = {
                        amount: basketItem.amount,
                        price: basketItem.price.minorAmount,
                        output: gameOfferings[itemKey].output
                    };
                }
            }
        }

        if (!basketSize)
        {
            return;
        }

        function checkTransactionStatus()
        {
            $.ajax({
                url: '/api/v1/store/transactions/read-status/' + transactionId,
                type: 'GET',
                success: function successFn(response /*, status */)
                {
                    if (response.data.status === 'completed')
                    {
                        that.updateBasket(basketGame, {});
                        Turbulenz.Services.bridge.emit('basket.site.update', JSON.stringify({
                                currency: that.currency,
                                total: Money.create(that.currency, 0).toMajorUnit(),
                                items: {}
                            }));
                        Turbulenz.Services.bridge.emit('purchase.confirmed');
                    }
                    else
                    {
                        setTimeout(checkTransactionStatus, 500);
                    }
                }
            });
        }

        $.ajax({
            url: '/api/v1/store/transactions/checkout',
            type: 'POST',
            data: {
                basket: JSON.stringify(basketData),
                gameSlug: basketGame
            },
            success: function successFn(response /*, status */)
            {
                transactionId = response.data.transactionId;

                $.ajax({
                    url: '/api/v1/store/transactions/pay/' + transactionId,
                    type: 'POST',
                    success: function successFn(/* response, status */)
                    {
                        setTimeout(checkTransactionStatus, 500);
                    }
                });
            }
        });
    },

    rejectPurchase: function rejectPurchaseFn()
    {
        Turbulenz.Services.bridge.emit('purchase.rejected');
    },

    getStoreMeta: function getStoreMetaFn(game, callback)
    {
        function currencyListRecieved()
        {
            var that = this;
            var offerings = this.offerings[game];
            var resources = this.resources[game];
            // getStoreMeta is only evaluated once per game and is
            // requested lazily to avoid having to request it everytime
            // a game starts
            if (offerings && resources)
            {
                if (callback)
                {
                    callback.call(that, offerings, resources);
                    return;
                }
            }

            var storeMetaObservers;
            if (callback)
            {
                storeMetaObservers = this.metaObservers[game];
                if (storeMetaObservers)
                {
                    storeMetaObservers.push(callback);
                    return;
                }
                else
                {
                    storeMetaObservers = this.metaObservers[game] = [callback];
                }
            }

            $.ajax({
                url: '/api/v1/store/items/read/' + game,
                type: 'GET',
                success: function successFn(response /*, status */)
                {
                    var offerings = response.data.items || response.data.offerings;
                    var resources = response.data.resources;

                    var offeringKey;
                    for (offeringKey in offerings)
                    {
                        if (offerings.hasOwnProperty(offeringKey))
                        {
                            var offering = offerings[offeringKey];
                            var prices = offering.prices;
                            var currencyCode;

                            for (currencyCode in prices)
                            {
                                if (prices.hasOwnProperty(currencyCode))
                                {
                                    var price = Money.create(that.currencyList[currencyCode], prices[currencyCode]);
                                    prices[currencyCode] = price;
                                }
                            }
                        }
                    }

                    that.offerings[game] = offerings;
                    that.resources[game] = resources;

                    var i;
                    var storeMetaObserversLength = storeMetaObservers.length;
                    for (i = 0; i < storeMetaObserversLength; i += 1)
                    {
                        storeMetaObservers[i].call(that, offerings, resources);
                    }
                }
            });
        }

        this.getCurrencyList(currencyListRecieved);
    },

    getStoreUserItems: function getStoreUserItemsFn(game, callback)
    {
        var that = this;
        $.ajax({
            url: '/api/v1/store/user/items/read/' + game,
            type: 'GET',
            success: function successFn(response /*, status */)
            {
                var userItems = response.data.userItems;
                that.userItems = userItems;
                if (callback)
                {
                    callback.call(that, userItems);
                }
            }
        });
    },

    calculateBasket: function calculateBasketFn(game)
    {
        var basket = this.basket;
        var basketItems = basket.items;

        game = game || basket.game;

        var offerings = this.offerings[game];
        var resources = this.resources[game];

        function isOwnOffering(offering)
        {
            var outputKey;
            var output = offering.output;
            for (outputKey in output)
            {
                if (output.hasOwnProperty(outputKey))
                {
                    if (resources[outputKey].type !== 'own')
                    {
                        return false;
                    }
                }
            }
            return true;
        }

        if (basket.game === game)
        {
            var total = Money.create(this.currency, 0);
            var calculatedBasketItems = {};
            var currencyCode = this.currency.alphabeticCode;

            var itemKey;
            for (itemKey in basketItems)
            {
                if (basketItems.hasOwnProperty(itemKey))
                {
                    var basketItem = basketItems[itemKey];
                    var offering = offerings[itemKey];
                    // dont add any items that are no longer in the store
                    // possible if developer changes store item keys

                    if (offering && offering.available)
                    {
                        var ownOffering = isOwnOffering(offering);
                        var amount = basketItem.amount;
                        if (ownOffering && amount > 1)
                        {
                            amount = 1;
                        }

                        if (amount > 999)
                        {
                            amount = 999;
                        }

                        // note that we cannot check if the item is already owned by the user here
                        // because then we would have to do an async request to find the users items.

                        var offeringPrice = offering.prices[currencyCode];

                        var lineTotal = offeringPrice.multiply(amount);
                        calculatedBasketItems[itemKey] = {
                            amount: amount,
                            price: offeringPrice,
                            lineTotal: lineTotal
                        };
                        total = total.add(lineTotal);
                    }
                }
            }

            this.updateBasket(game, calculatedBasketItems);

            return {
                items: calculatedBasketItems,
                total: total,
                game: game
            };
        }
        else
        {
            return {
                items: {},
                total: Money.create(this.currency, 0)
            };
        }

    },

    updateBasket: function updateBasketFn(game, newBasketItems)
    {
        this.basket = {
            items: newBasketItems,
            game: game
        };
        JsLocalStore.set('basket', this.basket);
    },

    getCurrencyList: function getCurrencyFn(callback)
    {
        var that = this;
        // getCurrencyList is only evaluated once and is
        // requested lazily to avoid requesting it everytime
        // the localserver starts
        if (this.currencyList)
        {
            callback.call(that);
            return;
        }

        var currencyListObservers = this.currencyListObservers;
        if (currencyListObservers)
        {
            currencyListObservers.push(callback);
            return;
        }
        else
        {
            currencyListObservers = this.currencyListObservers = [callback];
        }

        $.ajax({
            url: '/api/v1/store/currency-list',
            type: 'GET',
            success: function successFn(response /*, status */)
            {
                var currencyList = response.data;
                var alphabeticCode;
                for (alphabeticCode in currencyList)
                {
                    if (currencyList.hasOwnProperty(alphabeticCode))
                    {
                        var currency = currencyList[alphabeticCode];
                        currencyList[alphabeticCode] = Currency.create(alphabeticCode,
                            currency.numericCode,
                            currency.minorUnitPrecision,
                            currency.currencyName);
                    }
                }
                that.currencyList = currencyList;
                that.currency = currencyList[that.currencyCode];

                var i;
                var currencyListObserversLength = currencyListObservers.length;
                for (i = 0; i < currencyListObserversLength; i += 1)
                {
                    currencyListObservers[i].call(that);
                }
            }
        });
    }
};

TurbulenzStore.create = function turbulenzStoreCreateFn(app)
{
    var turbulenzStore = new TurbulenzStore();
    turbulenzStore.app = app;

    // TODO: add game slug to basket (clear basket when adding items from a different game)
    turbulenzStore.basket = JsLocalStore.get('basket') || {items: {}};

    // TODO: get this from user
    turbulenzStore.currencyCode = 'USD';
    turbulenzStore.defaultCurrencyCode = 'USD';

    // this is retrieved on the first store meta request
    turbulenzStore.currencyList = null;
    turbulenzStore.currency = null;
    turbulenzStore.currencyListObservers = null;

    turbulenzStore.offerings = {};
    turbulenzStore.resources = {};
    turbulenzStore.metaObservers = {};

    var bridge = Turbulenz.Services.bridge;

    function onGameFetchStoreMeta()
    {
        var that = this;
        var game = this.app.playingGameSlug;
        this.getStoreMeta(game, function (offerings, resources)
            {
                var gameOfferings = {};
                var offeringKey;
                for (offeringKey in offerings)
                {
                    if (offerings.hasOwnProperty(offeringKey))
                    {
                        var offering = offerings[offeringKey];
                        var p;
                        var gameOffering = gameOfferings[offeringKey] = {};
                        // copy all of the offering's properties
                        for (p in offering)
                        {
                            // we cant pass the prices objects through the bridge
                            if (offering.hasOwnProperty(p) && p !== 'prices')
                            {
                                gameOffering[p] = offering[p];
                            }
                        }
                        // so we convert the money objects to major unit strings
                        gameOffering.price = offering.prices[that.currency.alphabeticCode].toMajorUnit();
                    }
                }

                Turbulenz.Services.bridge.emit('store.meta.v2', JSON.stringify({
                        currency: that.currency,
                        // add items for backwards compatibility
                        items: gameOfferings,
                        offerings: gameOfferings,
                        resources: resources
                    }));
            });
    }

    bridge.addListener('fetch.store.meta', onGameFetchStoreMeta, turbulenzStore);

    // this function must call bridge.emit('basket.site.update') synchronously (after its first call)
    function onGameBasketUpdate(newBasketItems)
    {
        var that = this;
        var game = this.app.playingGameSlug;
        this.getStoreMeta(game, function ()
            {
                if (newBasketItems)
                {
                    this.updateBasket(game, JSON.parse(newBasketItems));
                }
                var calculatedBasket = this.calculateBasket(game);
                var calculatedBasketItems = calculatedBasket.items;
                var gameBasketItems = {};
                var itemKey;
                for (itemKey in calculatedBasketItems)
                {
                    if (calculatedBasketItems.hasOwnProperty(itemKey))
                    {
                        var calculatedBasketItem = calculatedBasketItems[itemKey];
                        // we cant pass objects through the bridge
                        // so we convert the money objects to major unit strings
                        gameBasketItems[itemKey] = {
                            amount: calculatedBasketItem.amount,
                            price: calculatedBasketItem.price.toMajorUnit(),
                            lineTotal: calculatedBasketItem.lineTotal.toMajorUnit()
                        };
                    }
                }
                Turbulenz.Services.bridge.emit('basket.site.update', JSON.stringify({
                        currency: that.currency,
                        total: calculatedBasket.total.toMajorUnit(),
                        items: gameBasketItems
                    }));
            });
    }
    bridge.addListener('basket.game.update', onGameBasketUpdate, turbulenzStore);

    function onGameBasketUpdateV2(jsonParams)
    {
        var that = this;
        var game = this.app.playingGameSlug;
        this.getStoreMeta(game, function ()
            {
                var token = null;
                if (jsonParams)
                {
                    var params = JSON.parse(jsonParams);
                    this.updateBasket(game, params.basketItems);
                    token = params.token;
                }
                var calculatedBasket = this.calculateBasket(game);
                var calculatedBasketItems = calculatedBasket.items;
                var gameBasketItems = {};
                var itemKey;
                for (itemKey in calculatedBasketItems)
                {
                    if (calculatedBasketItems.hasOwnProperty(itemKey))
                    {
                        var calculatedBasketItem = calculatedBasketItems[itemKey];
                        // we cant pass objects through the bridge
                        // so we convert the money objects to major unit strings
                        gameBasketItems[itemKey] = {
                            amount: calculatedBasketItem.amount,
                            price: calculatedBasketItem.price.toMajorUnit(),
                            lineTotal: calculatedBasketItem.lineTotal.toMajorUnit()
                        };
                    }
                }
                Turbulenz.Services.bridge.emit('basket.site.update', JSON.stringify({
                        currency: that.currency,
                        total: calculatedBasket.total.toMajorUnit(),
                        items: gameBasketItems,
                        token: token
                    }));
            });
    }
    bridge.addListener('basket.game.update.v2', onGameBasketUpdateV2, turbulenzStore);

    // for testing only (DO NOT COPY TO GAMESITE!)
    // make a purchase without requiring the confirmation dialog
    bridge.addListener('basket.test.confirm', turbulenzStore.confirmPurchase, turbulenzStore);

    return turbulenzStore;
};
