// Copyright (c) 2011-2013 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global PluginDetection*/
/*global Turbulenz*/
/*global TurbulenzEngine: true*/
/*global window*/
/*global console*/
/*jshint nomen: false*/
/*global $*/
/*global _*/
/*jshint nomen: true*/
/*exported LocalPlayView*/

var LocalPlayView = Backbone.View.extend({
    el: '#details',

    initialize: function ()
    {
        this.app = this.options.app;
        this.engine = this.options.engine;

        this.template = Templates.local_play_template;
        this.no_plugin_template = Templates.local_no_plugin_template;

        this.versions = null;

        /*jshint nomen: false*/
        _.bindAll(this, 'render', 'playOn');
        /*jshint nomen: true*/

        var that = this;
        this.app.bind('game:play', that.playOn);

        this.app.bind('game:stop', function () {
            that.playOff();
        });
        this.app.bind('game:versions', function (slug) {
            that.render(slug);
        });

        return this;
    },

    getVersions: function (slug, callback)
    {
        var that = this;
        var url = this.app.router.get('play-versions', {slug: slug});

        $.get(url, function (res) {

            var versions = {};
            that.versions = versions;
            $.each(res.data.versions, function (i, version) {
                versions[version.title] = version;
            });

            callback(res);
        });
    },

    render: function (slug)
    {
        var that = this;
        this.getVersions(slug, function (res) {
            $(that.el).jqotesub(that.template, res.data);
            $('#playable-versions').find('tr:odd').addClass('stripe');
        });
        return this;
    },

    tearDownPlugin: function ()
    {
        var iframe = $('#game_player_frame').contents();

        // Loader

        var jTurbulenzLoader = $('#turbulenz_game_loader_object', iframe);
        if (0 === jTurbulenzLoader.length)
        {
            jTurbulenzLoader = $('embed[name=plugin]', iframe);
        }

        if (jTurbulenzLoader.length > 0)
        {
            var TurbulenzLoader = jTurbulenzLoader[0];
            try
            {
                TurbulenzLoader.unloadEngine();
            }
            catch (e)
            {
            }
        }

        // Canvas

        var TurbulenzEngineCanvas;
        if (window.game && window.game.TurbulenzEngine)
        {
            TurbulenzEngineCanvas = window.game.TurbulenzEngine;
        }
        else
        {
            TurbulenzEngineCanvas = window.TurbulenzEngine;
        }
        if (TurbulenzEngineCanvas && TurbulenzEngineCanvas.unload)
        {
            TurbulenzEngineCanvas.unload();
            window.TurbulenzEngine = null;
            window.WebGLTurbulenzEngine = null;
        }

        window.game = null;
        window.gameSlug = null;
        Turbulenz.Data.mode = null;
    },

    playFlashGame : function (slug, version, src)
    {
        // This is set first as the game slug is needed when creating a game session
        window.gameSlug = slug; // The slice extracts both project and version info
        Turbulenz.Data.mode = 'flash';

        var flashInfo = this.versions[version].flash;
        var flashVars = (flashInfo ? flashInfo.vars : null);
        if (!flashVars)
        {
            flashVars = {};
        }
        flashVars.useragent = navigator.userAgent;
        flashVars.uid = (new Date()).getTime().toString(16);
        flashVars.sessionVersion =  flashVars.uid;
        flashVars.gameSlug = slug;

        var flashParams = (flashInfo ? flashInfo.params : null);
        if (!flashParams)
        {
            flashParams = {};
        }

        $('<script type="text/javascript">' +
                'var swfVersionStr = "11.0";' +
                'var xiSwfUrlStr = "/static/flash/playerProductInstall.swf";' +
                'var flashvars = ' + JSON.stringify(flashVars) + ';' +
                'var params = ' + JSON.stringify(flashParams) + ';' +
                'var attributes = {' +
                    'id: "turbulenz_game_engine_object"' +
                '};' +
                'swfobject.embedSWF("' + src + '",' +
                    '"turbulenz_game_flash_container",' +
                    '"100%", "100%",' +
                    'swfVersionStr, xiSwfUrlStr,' +
                    'flashvars, params, attributes);' +
                //'swfobject.createCSS("#turbulenz_game_flash_container", "display:block;text-align:left;");' +
            '</script>' +
            '<div id="turbulenz_game_flash_container"></div>').appendTo('#game_player');

        var that = this;
        $(function () {
            var game = $('#turbulenz_game_engine_object')[0];
            window.game = game;
            window.TurbulenzEngine = game;
            window.onbeforeunload = that.tearDownPlugin;
        });
    },

    playOn: function (slug, version)
    {
        var that = this,
            app = this.app,
            hash = document.location.hash;
        var src = hash.slice(1);

        $('#header').hide();
        $('#content').hide();
        $('#game_player').show();

        var plugins = PluginDetection.getPlugins();

        // If IE
        if (navigator.appName === "Microsoft Internet Explorer")
        {
            if (version.search(/\.tzjs/) > 0)
            {
                window.alert("Sorry, but tzjs files do not run in Internet Explorer on the local server.");
                return;
            }
        }

        var userAgent = navigator.userAgent;

        // If Android
        if (-1 !== userAgent.indexOf("Android"))
        {
            if (version.search(/\.tzjs/) > 0)
            {
                window.location.href = "/play/" + slug + "/" + version;
                return;
            }
        }

        // iOS looks something like:
        // "Mozilla/5.0 (iPad; CPU OS 6_1 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10B141 Safari/8536.25"

        if (-1 !== userAgent.indexOf("Safari/") &&
            -1 !== userAgent.indexOf("Mobile/"))
        {
            if (version.search(/\.tzjs/) > 0)
            {
                window.location.href = "tblz://" + window.location.host +
                    "/play/" + slug + "/" + version;
                return;
            }
        }

        //remove previous iframe
        if ($('#game_player_frame').length || window.game !== null)
        {
            this.tearDownPlugin();
            $('#game_player_frame').remove();
        }

        if (version.search(/\.swf/) > 0)
        {
            if (!this.versions)
            {
                this.getVersions(slug, function () {
                    that.playFlashGame(slug, version, src);
                });
            }
            else
            {
                this.playFlashGame(slug, version, src);
            }
        }
        else if (version.search(/\.canvas/) < 0 && !plugins.turbulenz.supported)
        {
            $('#game_player').jqoteapp(this.no_plugin_template, {engine: this.engine});
        }
        else if (version.search(/\.canvas\.js/) > 0)
        {
            // This is set first as the game slug is needed when creating a game session
            $(function () {
                window.gameSlug = slug; // The slice extracts both project and version info
                Turbulenz.Data.mode = 'canvas';

                $('<div style="overflow: hidden; height: 100%;"><canvas id="turbulenz_game_engine_canvas" moz-opaque="true" tabindex="1">' +
                  'Sorry, but your browser does not support WebGL or does not have it enabled.' +
                  'To get a WebGL-enabled browser, please see:<br\/>' +
                  '<a href="http://www.khronos.org/webgl/wiki/Getting_a_WebGL_Implementation" target="_blank">' +
                  'Getting a WebGL Implementation<\/a>' +
                  '<\/canvas><\/div>').appendTo('#game_player');

                var contextNames = ["webgl", "experimental-webgl"];
                var context = null;
                var canvasTest = document.createElement('canvas');

                document.body.appendChild(canvasTest);

                for (var i = 0; i < contextNames.length; i += 1)
                {
                    try {
                        context = canvasTest.getContext(contextNames[i]);
                    } catch (e) {}

                    if (context) {
                        break;
                    }
                }
                if (!context)
                {
                    window.alert("Sorry, but your browser does not support WebGL or does not have it enabled.");
                }

                document.body.removeChild(canvasTest);

                var canvas = $('#turbulenz_game_engine_canvas')[0];
                if (context && canvas)
                {
                    window.TurbulenzEngine = {};
                    var runGame = function runGameFn() {
                        if (canvas.getContext && window.WebGLTurbulenzEngine && TurbulenzEngine)
                        {
                            var appEntry = TurbulenzEngine.onload;
                            var appShutdown = TurbulenzEngine.onunload;
                            if (!appEntry)
                            {
                                window.alert("TurbulenzEngine.onload has not been set");
                                return;
                            }

                            TurbulenzEngine = window.WebGLTurbulenzEngine.create({
                                canvas: canvas,
                                fillParent: true
                            });

                            if (!TurbulenzEngine)
                            {
                                window.alert("Failed to init TurbulenzEngine (canvas)");
                                return;
                            }

                            TurbulenzEngine.onload = appEntry;
                            TurbulenzEngine.onunload = appShutdown;
                            appEntry();
                        }
                    };
                    var canvasScript = document.createElement('script');
                    canvasScript.type = "text/javascript";
                    canvasScript.src = src;

                    if (canvasScript.addEventListener)
                    {
                        canvasScript.addEventListener("load", runGame, false);
                    }
                    else if (canvasScript.readyState)
                    {
                        canvasScript.onreadystatechange = function () {
                            if (this.readyState === "loaded" || this.readyState === "complete")
                            {
                                runGame();
                            }
                        };
                    }
                    document.getElementById("game_player").appendChild(canvasScript);
                }

                window.game = canvas;
                window.onbeforeunload = that.tearDownPlugin;
            });
        }
        else
        {
            var iframe = $('<iframe />', {
                id: 'game_player_frame',
                src: src,
                style: 'width: 100%; height: 100%; display: block; border: none;',
                allowfullscreen: 'true',
                mozallowfullscreen: 'true',
                webkitallowfullscreen: 'true'
            });
            iframe.appendTo('#game_player');
            $(function () {
                var iframeElement = $('#game_player_frame')[0];
                var iwin = iframeElement.contentWindow ||
                           iframeElement.contentDocument.defaultView;
                iwin.gameSlug = slug;
                window.game = iwin;
                window.onbeforeunload = that.tearDownPlugin;
            });
        }

        var url = app.router.get('games-details', {slug: slug});
        $.get(url, function (res) {

            if (res.data.has_notifications)
            {
                var gn = that.app.gameNotifications;
                gn.getNotificationKeys(slug, function (keys) {
                    gn.startPolling(slug, function (notification) {

                        var time = (new Date()).toTimeString().substring(0, 8),
                            notificationType = keys[notification.key];

                        console.log(time + ' - ' + notificationType.title + ' received: ', notification.message);

                    });
                });
            }

        });
    },

    playOff: function ()
    {
        this.app.gameNotifications.stopPolling();
        Turbulenz.Services.bridge.removeAllGamesListeners();
        this.tearDownPlugin();
        window.setTimeout(function () {
            $('#game_player').empty().hide();
            $('#header').show();
            $('#content').show();
            window.game = null;
        }, 0);
    }

});
