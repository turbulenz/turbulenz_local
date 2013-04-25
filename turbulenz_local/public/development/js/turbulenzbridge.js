// Copyright (c) 2012 Turbulenz Limited
/*jshint nomen: false*/
/*global EventEmitter*/
/*global Turbulenz*/
/*global TurbulenzBridge*/
/*global $*/
/*exported turbulenzFlashBridgeGetData*/
/*exported turbulenzFlashBridgeEmit*/
/*exported turbulenzFlashBridgeOn*/

function TurbulenzBridge() {}
TurbulenzBridge.prototype = {
    addStatusMessageListeners: function addStatusMessageListenersFn()
    {
        var that = this;
        var bridge = Turbulenz.Services.bridge;

        var parentElement = 'body';        // change this to put the busy-box somewhere else

        var defaultMessageText = 'Loading...';

        var messageBox = $('<div id="osd_message_outer_wrapper" style="position: absolute; display: none; width: 100%; top: -30px; z-index: 9999; text-align: center;">\n' +
                           '    <span class="message-container-outer">\n' +
                           '        <span id="osd_message_content" class="message-container">\n' +
                           '            <span id="osd_message" class="message-span"></span>\n' +
                           '        </span>\n' +
                           '    </span>\n' +
                           '</div>');

        $('body').append(messageBox);
        var $message = $('#osd_message');

        var hideDelayID = null;
        var showDelayID = null;
        var urlCheckID = null;
        var showCounter = 0;

        var currentStatus = null;
        var hideStatusTimeout = null;

        function hideMessageBox()
        {
            showCounter -= 1;
            if (showCounter === 0)
            {
                if (showDelayID !== null)
                {
                    clearTimeout(showDelayID);
                    showDelayID = null;
                }
                else if (hideDelayID === null)
                {
                    // delay the animation a little so the page doesn't look too hectic
                    hideDelayID = setTimeout(function () {
                        hideDelayID = null;

                        if (urlCheckID !== null)
                        {
                            clearTimeout(urlCheckID);
                            urlCheckID = null;
                        }

                        messageBox.animate({'top': '-30px'}, 50, function () {
                            messageBox.hide();
                        });

                    }, 250);
                }
            }
            else if (showCounter < 0)
            {
                // Just in case...
                showCounter = 0;
            }
        }

        // When calling this function manually (for example to indicate an expected ajax-request)
        // set 'manual' to true so that the reference counter doesn't think it's another ajax-request
        // that it has to wait for before removing the message-box
        function showMessageBox(message, force)
        {
            if (!force)
            {
                showCounter += 1;
            }

            if (showCounter === 1 || force)
            {
                if (hideDelayID !== null)
                {
                    clearTimeout(hideDelayID);
                    hideDelayID = null;

                    if (urlCheckID !== null)
                    {
                        clearTimeout(urlCheckID);
                        urlCheckID = null;
                    }
                }
                else if (showDelayID === null)
                {
                    showDelayID = setTimeout(function () {
                        showDelayID = null;

                        $message.text(message ? message: defaultMessageText);
                        messageBox.appendTo(parentElement).show().css({'top': '0px'});

                        var url = window.location.hash;
                        (function showMessageBoxUrlCheck() {
                            if (window.location.hash !== url)
                            {
                                hideMessageBox();
                            }
                            else
                            {
                                urlCheckID = setTimeout(showMessageBoxUrlCheck, 250);
                            }
                        }());

                    }, 100);
                }
            }
        }

        function startLoading(force)
        {
            showMessageBox('Loading...', force);
        }

        function startSaving(force)
        {
            showMessageBox('Saving...', force);
        }

        var hideStatus = function hideStatusFn()
        {
            messageBox.animate({'top': '-30px'}, 50, function () {
                messageBox.hide();
            });
        };

        function gameStatusUpdate(gameSessionId, status)
        {
            if (currentStatus !== status)
            {
                currentStatus = status;
                if (!status)
                {
                    return;
                }

                messageBox.hide();
                $message.text(status);
                messageBox.appendTo(parentElement).show().css({'top': '0px'});
                if (hideStatusTimeout)
                {
                    clearTimeout(hideStatusTimeout);
                }
                hideStatusTimeout = setTimeout(hideStatus, 3000);
            }
        }

        // Ajax events
        $(document).bind('ajaxStart', function () {
            startLoading();
        });

        $(document).bind('ajaxStop', function () {
            hideMessageBox();
        });

        function onConfirmPurchase()
        {
            messageBox.appendTo(parentElement).show().css({'top': '0px'});
            $message.html('Confirm payment? <a id="confirmYes">Yes</a>, <a id="confirmNo">No</a>');

            if (hideStatusTimeout)
            {
                clearTimeout(hideStatusTimeout);
            }

            $('#confirmYes').click(function ()
                {
                    that.app.store.confirmPurchase();
                    hideStatus();
                });
            $('#confirmNo').click(function ()
                {
                    that.app.store.rejectPurchase();
                    hideStatus();
                });
        }

        bridge.addListener('status.loading.start', startLoading);
        bridge.addListener('status.loading.stop', hideMessageBox);
        bridge.addListener('status.saving.start', startSaving);
        bridge.addListener('status.saving.stop', hideMessageBox);

        bridge.addListener('game.session.status', gameStatusUpdate);

        bridge.addListener('purchase.show.confirm', onConfirmPurchase);
    }
};

TurbulenzBridge.create = function turbulenzBridgeCreateFn(app)
{
    if (Turbulenz.Services.bridge)
    {
        throw "Only one TurbulenzBridge object can be created";
    }

    var tzBridge = new TurbulenzBridge();

    tzBridge.app = app;
    var siteEventEmitter = new EventEmitter();
    var gameEventEmitter = new EventEmitter();
    tzBridge.siteEventEmitter = siteEventEmitter;
    tzBridge.gameEventEmitter = gameEventEmitter;

    // Add EventEmitter to the Turbulenz namespace
    Turbulenz.Classes.EventEmitter = EventEmitter;

    function addListenerFn() {
        siteEventEmitter.addListener.apply(siteEventEmitter, arguments);
    }

    Turbulenz.Services.bridge = {
        emit: function emitFn()
        {
            siteEventEmitter.emit.apply(siteEventEmitter, arguments);
            gameEventEmitter.emit.apply(gameEventEmitter, arguments);
        },

        gameListenerOn: function gameListenerOnFn()
        {
            gameEventEmitter.addListener.apply(gameEventEmitter, arguments);
        },

        gameListenerOff: function gameListenerOffFn()
        {
            gameEventEmitter.removeListener.apply(gameEventEmitter, arguments);
        },

        addListener: addListenerFn,
        setListener: addListenerFn,

        removeAllListeners: function removeAllListenersFn(type)
        {
            siteEventEmitter.removeAllListeners(type);
            gameEventEmitter.removeAllListeners(type);
        },

        removeAllGamesListeners: function removeAllGamesListenersFn(type)
        {
            gameEventEmitter.removeAllListeners(type);
        }
    };

    tzBridge.addStatusMessageListeners();

    return tzBridge;
};

// These global functions will be called by our Flash API
function turbulenzFlashBridgeGetData()
{
    return Turbulenz.Data;
}

function turbulenzFlashBridgeEmit()
{
    //console.log(arguments[0], arguments[1]);
    var bridge = Turbulenz.Services.bridge;
    bridge.emit.apply(bridge, arguments);
}

function turbulenzFlashBridgeOn(eventName)
{
    //console.log(eventName);
    var functionName = 'turbulenz_event_' + eventName;
    var bridge = Turbulenz.Services.bridge;
    bridge.addListener(eventName, function () {
        var game = document.getElementById('turbulenz_game_engine_object');
        if (game)
        {
            var callback = game[functionName];
            if (callback)
            {
                callback.apply(game, arguments);
            }
        }
    });
}
