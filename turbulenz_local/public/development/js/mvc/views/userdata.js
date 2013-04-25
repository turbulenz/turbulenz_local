// Copyright (c) 2011-2012 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global window*/
/*global alert*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*exported LocalUserdataView*/

var LocalUserdataView = Backbone.View.extend({
    el: '#details',
    userData : [],
    users : [],
    lastSortKey : null,
    lastSortReverse : true,
    urls: {},
    slug: '',

    initialize: function initializeFn()
    {
        this.app = this.options.app;
        this.template = Templates.local_userdata_template;
        /*jshint nomen: false*/
        _.bindAll(this, 'render');
        /*jshint nomen: true*/

        this.app.bind('game:userdata', this.render);

        this.skeyPattern = new RegExp('sort-([a-zA-Z-]+)');

        return this;
    },

    render: function renderFn(slug, directory)
    {
        var router = this.app.router;
        var url = router.get('userdata-overview', {slug: slug});
        var that = this;

        $.get(url, function (data) {
            var contents = data.data;
            $(that.el).jqotesub(that.template, contents);

            if (contents.userdata)
            {
                that.slug = contents.slug;
                $('#users\\:').nextAll().remove();
                if (directory)
                {
                    var userDataUrl = router.get('userdata-keys', {slug: that.slug, username: directory});
                    that.getData(userDataUrl, directory);
                }
                else
                {
                    that.getData(url, '');
                }
            }

            $('#userdata-form .directoryPaths').unbind('click').bind('click', function () {
                $(this).nextAll().remove();
                var hash = document.location.hash;
                var hashSplit = hash.split('/');
                var action = hashSplit[1];
                var slug = hashSplit[2];
                var directory = $(this).attr('id');
                directory = directory.substring('users:'.length).replace(/:/g, '/');
                var strLen = directory.length;
                directory = directory.slice(0, strLen - 1);
                if (directory)
                {
                    document.location.hash = '/' + action + '/' + slug + '/' + directory;
                }
                else
                {
                    document.location.hash = '/' + action + '/' + slug;
                }
                return false;
            });

            $('#userdata-form .text-file').unbind('click').bind('click', function () {
                var url = $(this).attr('href');
                window.open(url, "_parent");
                return false;
            });
        });

        return this;
    },


    shortenName : function shortenName(name)
    {
        if (name.length > 30)
        {
            return "..." + name.substring(name.length - 30);
        }
        else
        {
            return name;
        }
    },


    sortData : function sortData(userDataDict, sortKey, reverse)
    {
        var sort_by = function (sortKey, reverse) {
            reverse = (reverse) ? -1 : 1;

            return function (a, b) {
                a = a[sortKey];
                b = b[sortKey];
                if (a < b)
                {
                    return reverse * -1;
                }
                if (a > b)
                {
                    return reverse * 1;
                }
                return 0;
            };
        };

        return userDataDict.sort(sort_by(sortKey, reverse));
    },

    getSizeStr : function getSizeStr(size)
    {
        var mega = (1024 * 1024);
        var kilo = 1024;

        if (size >= mega)
        {
            var megas = (size / mega) - 0.05;
            return megas.toFixed(1) + "MB";
        }
        else if (size >= kilo)
        {
            var kilos = (size / kilo) - 0.05;
            return kilos.toFixed(1) + "KB";
        }
        else
        {
            return size + "B";
        }
    },


    returnAssetList : function returnAssetList(data, directory)
    {
        var router = this.app.router;
        var that = this;
        var i, str = '';

        //create header breadcrumbs
        if (directory)
        {
            var headerStr = '';
            var path = directory.split('/');
            var headerTarget = $(".session-header ul:first");
            $('#users\\:').nextAll().remove();

            var thisPath = 'users:';
            for (i = 0; i < path.length; i += 1)
            {
                //store full path up to i-th directory in the 'id'
                thisPath += path[i] + ':';
                headerStr += "<li class=\"button left directoryPaths\" id=\"" + thisPath + "\"><div class=\"right\">";
                //display current i-th directory
                headerStr += "<div class=\"middle\">" + path[i] + "</div></div></li>";
            }
            headerTarget.append(headerStr);
        }

        for (i = 0; i < data.length; i += 1)
        {
            var item = data[i];
            var key = item.assetName;
            var link = router.get('userdata-as-text', {slug: that.slug,
                                                        username: directory,
                                                        key: key});
            str += '<tr><td>';
            str += '<a href="' + link + '" class=\"text-file\">' + that.shortenName(key) + '</a>';
            str += '</td><td>' + that.getSizeStr(item.size) + '</td><td>';

            if (item.isJson)
            {
                var disassemblerLink = router.get('disassemble-app', {slug: that.slug,
                                                                       asset: directory + '/' + key});
                str += '<a href="' + disassemblerLink + '?userdata=1">Disassemble</a>';
            }
            else
            {
                str += "-";
            }
            str += "</td></tr>";
        }
        return str;
    },


    returnUserList : function returnUserList(data /*, directory */)
    {
        var that = this;
        var list = data;
        var listLength = list.length;
        var i, str = '';

        for (i = 0; i < listLength; i += 1)
        {
            var key = list[i];
            var shortKey = that.shortenName(key);
            str += "<tr><td>";
            str += "<a title=\"" + key + "\" class=\"directory\" id=\"" + key + "\">" + shortKey + "</a>";
            str += "</td><td>-</td><td>-</td></tr>";
        }
        return str;
    },


    displayData : function displayData(directory)
    {
        var target = $('tbody');
        var htmlStr;

        if (directory)
        {
            htmlStr = this.returnAssetList(this.userData, directory);
        }
        else
        {
            htmlStr = this.returnUserList(this.users);
        }
        target.html(htmlStr);

        $('.details-table').find('tr:even').addClass('stripe');

        $('#userdata-form .directory').unbind('click').bind('click', function (/* event */) {
            var directory = $(this).attr('id');
            document.location.hash = document.location.hash + '/' + directory;
            return false;
        });
    },

    getData : function getData(url, username)
    {
        var that = this;
        $.ajax({
            url: url,
            dataType: 'json',
            async: false,
            success: function (res) {
                var userdata;
                if (username)
                {
                    userdata = [];
                    var userdataDict = res.data;
                    for (var k in userdataDict)
                    {
                        if (userdataDict.hasOwnProperty(k))
                        {
                            userdata.push(userdataDict[k]);
                        }
                    }
                    that.userData = userdata;
                }
                else
                {
                    userdata = res.data.users;
                    that.users = userdata;
                }

                if (that.lastSortKey)
                {
                    that.sortData(userdata, that.lastSortKey, that.lastSortReverse);
                }
                that.displayData(username);

                $('.sort-controller th').unbind('click');
                $('.button').unbind('hover');

                // add listeners to the headers
                $('.sort-controller th').click(function ()  {
                    var sortKey = $(this).attr('class');
                    if (sortKey)
                    {
                        sortKey = sortKey.match(that.skeyPattern)[1];
                        that.lastSortKey = sortKey;
                    }

                    var $span = $(this).find('span');
                    if ($span.hasClass('active'))
                    {
                        //reverse sorting
                        that.sortData(userdata, sortKey, true);
                        that.displayData(username);
                        that.lastSortReverse = true;
                        $span.removeClass('active').addClass('active-reverse');
                    }
                    else
                    {
                        //apply sorting
                        that.sortData(userdata, sortKey, false);
                        that.displayData(username);
                        that.lastSortReverse = false;
                        $(this).siblings().find('span').removeClass('active').removeClass('active-reverse');
                        $span.removeClass('active-reverse').addClass('active');
                    }
                });

                $('.button').hover(
                    function () {
                        $(this).addClass('hover-target');
                    },
                    function () {
                        $(this).removeClass('hover-target');
                    }
                );
            },
            error: function (XMLHttpRequest /*, textStatus, errorThrown */)
            {
                if (XMLHttpRequest.status !== 200)
                {
                    var theResponse = XMLHttpRequest.responseText;
                    alert(theResponse);
                }
            }
        });
    }
});
