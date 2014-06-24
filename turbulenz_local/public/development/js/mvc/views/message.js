// Copyright (c) 2011-2012,2014 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global PluginDetection*/
/*global window*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*exported LocalMessageView*/

function hideMessage(messageClass, cookieName, version)
{
    $(messageClass).fadeOut('slow');
    if (cookieName)
    {
        $.cookie(cookieName, version, {expires: 100, path: '/'});
    }
}

var LocalMessageView = Backbone.View.extend({

    initialize: function (options)
    {
        this.app = this.options.app;

        this.engineVersionTemplate = Templates.local_message_engine_version_template;
        this.sdkTemplate = Templates.local_message_sdk_template;
        this.hostTemplate = Templates.local_message_host_template;
        this.pluginTemplate = Templates.local_message_plugin_template;
        this.missingPluginTemplate = Templates.local_message_missing_plugin_template;

        this.engine = options.engine;
        this.sdk = options.sdk;
        /*jshint nomen: false*/
        _.bindAll(this, 'render');
        /*jshint nomen: true*/

        return this;
    },

    checkEngineVersion: function ()
    {
        var plugins = PluginDetection.getPlugins();
        if (plugins.turbulenz.supported)
        {
            try
            {
                var installedVersion = plugins.turbulenz.version;
                var newest = this.engine.newest;
                if (PluginDetection.newerVersion(newest, installedVersion) && $.cookie('skip_engine_version') !== newest)
                {
                    $('.messages').jqoteapp(this.engineVersionTemplate, { engine: this.engine });
                    $('#skip-engine-link').bind('click', function () {
                        hideMessage('.engine_version', 'skip_engine_version', newest);
                    });
                    $('.engine_version').fadeIn('slow');
                }
            }
            catch (e)
            {
                $('.message').html('<span class="error">' + e + '<\/span>');
            }
        }
    },

    checkPlugin: function ()
    {
        var plugins = PluginDetection.getPlugins();
        if (plugins.turbulenz.supported)
        {
            if (this.engine)
            {
                var newest = this.engine.newest;
                if ($.cookie('skip_engine_version') !== newest)
                {
                    $('.messages').jqoteapp(this.pluginTemplate, { engine: this.engine });
                    $('#skip-engine-link').bind('click', function () {
                        hideMessage('.plugin', 'skip_engine_version', newest);
                    });
                    $('.plugin').fadeIn('slow');
                }
            }
            else
            {
                $('.messages').jqoteapp(this.missingPluginTemplate);
                $('#skip-engine-link').bind('click', function () {
                    hideMessage('.plugin');
                });
                $('.plugin').fadeIn('slow');
            }
        }
    },

    checkSDK: function ()
    {
        var newest = this.sdk.newest;
        var current = this.sdk.current;
        if (current && PluginDetection.newerVersion(newest, current) && $.cookie('skip_sdk_version') !== newest)
        {
            $('.messages').jqoteapp(this.sdkTemplate, { sdk: this.sdk });
            $('#skip-sdk-link').bind('click', function () {
                hideMessage('.sdk', 'skip_sdk_version', newest);
            });
            $('.sdk').fadeIn('slow');
        }
    },

    checkHost: function ()
    {
        var platform = PluginDetection.getPlatform();

        if (platform === 'Windows' &&
            (window.location.href).indexOf('http://localhost:8070/') >= 0 &&
            $.cookie('skip-local-link') !== 'true')
        {
            $('.messages').jqoteapp(this.hostTemplate);
            $('#local-link').bind('click', function () {
                $('#local-link').attr('href', 'http://127.0.0.1:8070/' + document.location.hash);
            });
            $('#skip-local-link').bind('click', function () {
                hideMessage('.WinOS', 'skip-local-link', true);
            });
            $('.WinOS').fadeIn('slow');
        }
    },


    render: function () {
        this.checkEngineVersion();
        this.checkSDK();
        this.checkHost();
        this.checkPlugin();
        return this;
    }
});
