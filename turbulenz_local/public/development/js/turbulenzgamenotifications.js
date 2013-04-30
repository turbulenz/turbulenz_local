// Copyright (c) 2011-2013 Turbulenz Limited

/*global Turbulenz*/
/*global $*/

function TurbulenzGameNotifications() {}

TurbulenzGameNotifications.prototype = {

    pollingCallback: function () {},

    pollingInterval: null,

    defaultInterval: 5,

    sendInstantNotification: function (params) {

        var token = params.token;

        $.ajax({
            url: '/api/v1/game-notifications/send-instant/' + params.session.gameSlug,
            type: 'POST',
            data: {
                data: JSON.stringify({
                    recipient: params.recipient,
                    key: params.key,
                    msg: params.msg
                })
            },
            success: function (data) {

                Turbulenz.Services.bridge.emit('notifications.ingame.sent', {
                    token: token,
                    id: data.id
                });

            },
            error: function (jqXHR) {

                var error = jqXHR.responseText ? JSON.parse(jqXHR.responseText).msg : jqXHR.statusText;

                Turbulenz.Services.bridge.emit('notifications.ingame.sent', {
                    token: token,
                    status: jqXHR.status,
                    error: error
                });

            }
        });

    },

    sendDelayedNotification: function (params) {

        var token = params.token;

        $.ajax({
            url: '/api/v1/game-notifications/send-delayed/' + params.session.gameSlug,
            type: 'POST',
            data: {
                data: JSON.stringify({
                    key: params.key,
                    time: params.delay,
                    msg: params.msg
                })
            },
            success: function (data) {

                Turbulenz.Services.bridge.emit('notifications.ingame.sent', {
                    token: token,
                    id: data.id
                });

            },
            error: function (jqXHR) {

                var error = jqXHR.responseText ? JSON.parse(jqXHR.responseText).msg : jqXHR.statusText;

                Turbulenz.Services.bridge.emit('notifications.ingame.sent', {
                    token: token,
                    status: jqXHR.status,
                    error: error
                });

            }
        });

    },

    cancelNotificationByID: function (params) {

        $.ajax({
            url: '/api/v1/game-notifications/cancel-by-id/' + params.session.gameSlug,
            type: 'POST',
            data: {
                id: params.id
            }
        });

    },

    cancelNotificationsByKey: function (params) {

        $.ajax({
            url: '/api/v1/game-notifications/cancel-by-key/' + params.session.gameSlug,
            type: 'POST',
            data: {
                key: params.key
            }
        });

    },

    cancelAllNotifications: function (params) {

        $.ajax({
            url: '/api/v1/game-notifications/cancel-all/' + params.session.gameSlug,
            type: 'POST'
        });

    },

    doPolling: function (slug) {

        $.ajax({
            url: '/api/v1/game-notifications/poll/' + slug,
            type: 'GET',
            success: function (data) {
                data = data.data || [];
                var bridgeEmit = Turbulenz.Services.bridge.emit;
                for (var i = 0, l = data.length; i < l; i += 1)
                {
                    bridgeEmit('notifications.ingame.receive', data[i]);
                }
            }
        });
    },

    isPolling: function () {
        return !!this.pollingInterval;
    },

    startPolling: function (slug, pollingCallback, interval) {
        this.pollingCallback = pollingCallback;

        this.stopPolling();

        this.intervalTime = (interval || this.defaultInterval) * 1000;

        var that = this;
        this.pollingInterval = setInterval(function () {
            that.doPolling.call(that, slug);
        }, this.intervalTime);
    },

    stopPolling: function () {
        clearInterval(this.pollingInterval);
        this.pollingInterval = null;
    },

    getNotificationKeys: function (slug, callback) {
        $.get('/api/v1/game-notifications/keys/read/' + slug, function (result) {
            callback(result.data ? result.data.keys : {});
        });
    },

    onInitManager: function (params) {
        $.post('/api/v1/game-notifications/init-manager/' + params.session.gameSlug);
    }
};

TurbulenzGameNotifications.create = function turbulenzGameNotificationsCreateFn(app) {

    var notifications = new TurbulenzGameNotifications();
    notifications.app = app;

    var bridge = Turbulenz.Services.bridge;

    bridge.addListener('notifications.ingame.sendInstant', function onSendNotificationFn(params) {

        notifications.sendInstantNotification(JSON.parse(params));

    }, notifications);

    bridge.addListener('notifications.ingame.sendDelayed', function onSendNotificationFn(params) {

        notifications.sendDelayedNotification(JSON.parse(params));

    }, notifications);

    bridge.addListener('notifications.ingame.cancelByID', function onCancelNotificationByIDFn(params) {

        notifications.cancelNotificationByID(JSON.parse(params));

    }, notifications);

    bridge.addListener('notifications.ingame.cancelByKey', function onCancelNotificationsByKeyFn(params) {

        notifications.cancelNotificationsByKey(JSON.parse(params));

    }, notifications);

    bridge.addListener('notifications.ingame.cancelAll', function onCancelAllNotificationsFn(params) {

        notifications.cancelAllNotifications(JSON.parse(params));

    }, notifications);

    bridge.addListener('notifications.ingame.initNotificationManager', function onCancelAllNotificationsFn(params) {

        notifications.onInitManager(JSON.parse(params));

    }, notifications);

    return notifications;

};

