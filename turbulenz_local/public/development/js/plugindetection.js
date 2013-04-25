// Copyright (c) 2011-2012 Turbulenz Limited

/* Code adapted from Andrei Stefan's work */
/* http://www.sliceratwork.com/detect-installed-browser-plugins-using-javascript */
/*global navigator*/
/*global ActiveXObject*/
/*global window*/
/*global $*/

var PluginDetection = {};

PluginDetection.plugins = {
    'turbulenz': {
        'mimeType': ['application/vnd.turbulenz'],
        'activeXControls': ['turbulenz_host.TurbulenzEngineHostControl']
    }
};


PluginDetection.platformStrings = [
    {
        subString: "Win",
        identity: "Windows"
    },
    {
        subString: "Mac",
        identity: "Mac"
    },
    {
        subString: "Linux",
        identity: "Linux"
    }
];


PluginDetection.getPlugins = function getPluginsFn()
{
    if (this.installedPlugins)
    {
        return this.installedPlugins;
    }

    this.installedPlugins = {};

    var regexVersion = /Version:(([0-9]+)\.){2,3}([0-9]+)/g;

    function parseVersion(description)
    {
        if (!description)
        {
            return null;
        }

        var versionMatch = description.match(regexVersion);
        if (!versionMatch || versionMatch.length === 0)
        {
            return null;
        }
        var versionString = versionMatch[0];

        return versionString.substr(8, versionString.length - 8);
    }

    function pluginHtml(params)
    {
        if (window.ActiveXObject)
        {
            return '<object id="' + params.id + '" width="' + params.width + '" height="' + params.height + '">' +
                       '<param name="type" value="application/vnd.turbulenz">' +
                   '</object>';
        }

        // browser supports Netscape Plugin API
        return '<object id="' + params.id + '" width="' + params.width + '" height="' + params.height + '" ' +
                       'type="application/vnd.turbulenz"></object>';
    }

    function getPluginVersion()
    {
        // attempts to insert the plugin and fetch its version string
        // returns the version of the installed plugin
        // returns null if the plugin is not installed

        $('body').append(pluginHtml({
            'id': 'test_tz_version',
            'width': 0,
            'height': 0
        }));

        var tz = $('#test_tz_version');
        var version = tz[0].version;
        if (version)
        {
            tz.remove();
            return version;
        }
        return null;
    }

    function checkPlugin(plugin) {
        var i, length, version;

        navigator.plugins.refresh();

        // for standard compliant browsers
        var mimeTypes = navigator.mimeTypes;
        if (mimeTypes) {
            length = plugin.mimeType.length;
            for (i = 0; i < length; i += 1) {
                var plugin_minetype = mimeTypes[plugin.mimeType[i]];

                if (plugin_minetype)
                {
                    var properties = plugin_minetype.enabledPlugin;
                    if (properties) {

                        try
                        {
                            version = parseVersion(properties.description);
                        }
                        catch (mimeTypeVersionError) {}

                        version = version || getPluginVersion();
                        return {'supported': true,
                                'version': properties.version || getPluginVersion()};
                    }
                    else
                    {
                        return {'supported': false};
                    }
                }
            }
        }

        // for IE
        var activeX = plugin.activeXControls;

        if (activeX) {
            if (typeof ActiveXObject !== 'undefined') {
                length = activeX.length;
                for (i = 0; i < length; i += 1) {
                    try
                    {
                        var object = new ActiveXObject(activeX[i]);

                        version = null;
                        try
                        {
                            version = parseVersion(object.description);
                        }
                        catch (versionError) {}

                        return {'supported': true,
                                'version': version};
                    }
                    catch (pluginError) {}
                }
            }
        }

        return {'supported': false};
    }

    var plugins = this.plugins;
    var p;
    for (p in plugins)
    {
        if (plugins.hasOwnProperty(p))
        {
            this.installedPlugins[p] = checkPlugin(plugins[p]);
        }
    }

    return this.installedPlugins;
};


PluginDetection.getPlatform = function getPlatformFn() {
    // Get the current platform as a string
    if (this.platform)
    {
        return this.platform;
    }

    var navPlatform = navigator.platform;
    var platformStrings = this.platformStrings;
    var platformStringsLength = platformStrings.length;

    for (var i = 0; i < platformStringsLength; i += 1) {
        if (navPlatform.indexOf(platformStrings[i].subString) !== -1)
        {
            this.platform = platformStrings[i].identity;
            return this.platform;
        }
    }

    this.platform =  "Unknown";
    return this.platform;
};


PluginDetection.newerVersion = function newerVersionFn(version, installedVersion)
{
    // compare version string (eg: "1.2.0") with installed plugin version
    // returns true if version is newer
    // returns false is version is older or the same
    var a = version.split(/\./);
    var b = installedVersion.split(/\./);

    var maxLength = Math.max(a.length, b.length);
    for (var i = 0; i < maxLength; i += 1)
    {
        var ai = a[i];
        var bi = b[i];
        if (ai)
        {
            ai = parseInt(ai, 10);
        }
        else
        {
            ai = 0;
        }

        if (bi)
        {
            bi = parseInt(bi, 10);
        }
        else
        {
            bi = 0;
        }

        if (ai > bi)
        {
            return true;
        }
        else if (ai < bi)
        {
            return false;
        }
    }
    return false;
};
