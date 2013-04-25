// Copyright (c) 2010-2013 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*exported LocalListView*/

var LocalListView = Backbone.View.extend({

    el: '#details',
    assetData: {},
    mappingTableUrl: '',
    staticFileUrl: '',
    hasMappingTable: '',
    inverseMapping: {},
    viewType: '',
    slug: '',
    lastSortKey : null,
    lastSortReverse : true,

    initialize: function initializeFn()
    {
        this.app = this.options.app;
        this.templates = {
            'assets': Templates.local_list_asset_template,
            'files': Templates.local_list_files_template
        };
        /*jshint nomen: false*/
        _.bindAll(this, 'render', 'initializePage', 'getMappingTable', 'showDirectory');
        /*jshint nomen: true*/
        this.app.bind('assets:list', this.render);
        this.skeyPattern = new RegExp('sort-([a-zA-Z-]+)');
        return this;
    },

    render: function renderFn(type, slug, directory)
    {
        this.viewType = type;
        var that = this;
        var url = this.app.router.get('list-overview', {slug: slug});

        $.get(url, function (data) {
            data = data.data;
            that.mappingTableUrl = 'play/' + slug + '/' + data.mappingTable;
            that.staticFileUrl = data.staticFilePrefix;
            that.slug = data.slug;
            // Select correct template for viewing type
            $(that.el).jqotesub(that.templates[that.viewType], data);

            that.showDirectory(slug, directory);
        });
        return this;
    },


    sortData: function sortData(assetDataDict, sortKey, reverse)
    {
        var getVal = function (key, sortKey)
        {
            if (key[sortKey] === true)
            {
                return 1;
            }
            else
            {
                return 0;
            }
        };

        var sort_by = function (sortKey, reverse) {
            reverse = (reverse) ? -1 : 1;

            return function (a, b) {

                if (a.isDirectory !== b.isDirectory)
                {
                    return -1;
                }

                if (sortKey === 'canView' || sortKey === 'canDisassemble')
                {
                    a = getVal(a, sortKey);
                    b = getVal(b, sortKey);
                }
                else
                {
                    a = a.isDirectory ? a.assetName : a[sortKey];
                    b = b.isDirectory ? b.assetName : b[sortKey];
                }

                if (a && a.toLowerCase)
                {
                    a = a.toLowerCase();
                }
                if (b && b.toLowerCase)
                {
                    b = b.toLowerCase();
                }

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
        return assetDataDict.sort(sort_by(sortKey, reverse));
    },

    shortenName: function shortenName(name)
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

    returnAssetList: function returnAssetList(data, directory, assetView)
    {
        var router = this.app.router;
        var that = this;
        var list = data.items;
        var listLength = data.items.length;
        var str = '';
        var viewerEnabled = this.app.viewerEnabled;

        for (var i = 0; i < listLength; i += 1)
        {
            var item = list[i];
            var name = item.assetName;
            var reqName = item.requestName;
            var slug = that.slug;
            var viewerAsset, disassemblerAsset;

            if (assetView)
            {
                viewerAsset = directory + '/' + name;
                disassemblerAsset = this.staticFileUrl + '/' + reqName;
            }
            else
            {
                viewerAsset = reqName;
                disassemblerAsset = reqName;
                if (directory)
                {
                    viewerAsset = directory + '/' + viewerAsset;
                    disassemblerAsset = directory + '/' + disassemblerAsset;
                }
            }

            var viewerUrl = router.get('viewer-app', {slug: slug, asset: viewerAsset});
            var disassemblerUrl = router.get('disassemble-app', {slug: slug, asset: disassemblerAsset});

            if (item.isDirectory)
            {
                str += "<tr><td>";
                str += "<a title=\"" + name + "\" class=\"directory\" id=\"" + name + "\">" + that.shortenName(name) + "</a>";
                str += "</td><td>";
                str += "-";
            }
            else
            {
                if (assetView)
                {
                    str += "<tr><td>";
                    str += "<span title=" + name + ">" + that.shortenName(name) + "</span>";
                    str += "</td><td>";
                    str += "<span title=" + reqName + ">" + reqName + "</span>";
                }
                else
                {
                    if (name === '-')
                    {
                        str += "<tr><td>";
                        str += "<span title=" + reqName + ">" + reqName + "</span>";
                        str += "</td><td>";
                        str += "-";
                    }
                    else
                    {
                        str += "<tr class=\"highlighted\"><td>";
                        str += "<span title=" + reqName + ">" + reqName + "</span>";
                        str += "</td><td>";
                        str += "<span title=" + name + ">" + that.shortenName(name) + "</span>";
                    }
                }
            }
            str += "</td><td>";

            if (item.canView)
            {
                if (viewerEnabled)
                {
                    str += "<a href=" + viewerUrl + ">View</a>";
                }
                else
                {
                    str += "View";
                }
            }
            else
            {
                str += "-";
            }
            str += "</td><td>";
            if (item.canDisassemble)
            {
                str += "<a href=" + disassemblerUrl + ">Disassemble</a>";
            }
            else
            {
                str += "-";
            }
            str += "</td></tr>";
        }
        return str;
    },

    displayData: function displayData(directory)
    {
        var that = this;
        var target = $('tbody');
        var assetView = (this.viewType === 'assets');
        var htmlStr = this.returnAssetList(this.assetData, directory, assetView);

        target.html(htmlStr);
        $('.details-table').find('tr:even').addClass('stripe');

        if (that.hasMappingTable === false && assetView)
        {
            $('div.details-table tbody').html('<tr><td>No mapping table. Switch to File System View please.<\/td><\/tr>');
        }
        that.initializePage();
    },

    getData: function getData(url, path, directory)
    {
        var that = this;
        $.ajax({
            url: url,
            dataType: 'json',
            async: false,
            success: function (data) {
                that.assetData = data.data;
                that.hasMappingTable = data.data.mappingTable;

                //when viewing assets as files, the asset name needs to be looked up in the mapping table, to allow sorting
                if (that.viewType === 'files' && that.inverseMapping)
                {
                    var items = that.assetData.items;
                    for (var i = 0; i < items.length; i += 1)
                    {
                        if (!items[i].isDirectory)
                        {
                            var requestName = items[i].requestName;
                            var assetName = that.inverseMapping[requestName];
                            if (!assetName)
                            {
                                assetName = '-';
                            }
                            items[i].assetName = assetName;
                        }
                    }
                }

                if (that.lastSortKey)
                {
                    that.sortData(that.assetData.items, that.lastSortKey, that.lastSortReverse);
                }
                that.displayData(directory);


                $('.sort-controller th').unbind('click').click(function sortController()  {
                    var $this = $(this);
                    var sortKey = $this.attr('class');

                    if (sortKey)
                    {
                        sortKey = sortKey.match(that.skeyPattern)[1];
                        that.lastSortKey = sortKey;
                    }

                    var $this_span = $this.find('span');
                    if ($this_span.hasClass('active'))
                    {
                        //reverse sorting
                        that.sortData(that.assetData.items, sortKey, true);
                        that.displayData(directory);
                        that.lastSortReverse = true;

                        $this_span.removeClass('active').addClass('active-reverse');
                    }
                    else
                    {
                        //apply sorting
                        that.sortData(that.assetData.items, sortKey, false);
                        that.displayData(directory);
                        that.lastSortReverse = false;

                        $(this).siblings().find('span').removeClass('active').removeClass('active-reverse');
                        $this_span.removeClass('active-reverse').addClass('active');
                    }
                });

                $('.session-header .button')
                    .unbind('mouseenter mouseleave')
                    .bind('mouseenter', function () {
                        $(this).addClass('hover-target');
                    })
                    .bind('mouseleave', function () {
                        $(this).removeClass('hover-target');
                    });
            }
        });
    },

    showDirectory: function showDirectoryFn(slug, directory)
    {
        var target = $(".session-header ul:first");

        $('#asset\\:').nextAll().remove();
        var str = '';
        var thisPath = 'asset:';

        if (directory)
        {
            var path = directory.split('/');
            for (var i = 0; i < path.length; i += 1)
            {
                if (path[i] !== '')
                {
                    thisPath += path[i] + ':';
                    str += "<li class=\"button left directoryPaths\" id=\"" + thisPath + "\"><div class=\"right\">";
                    str += "<div class=\"middle\">" + path[i] + "</div></div></li>";
                }
            }
        }
        target.append(str);

        var url;
        var router = this.app.router;
        if (this.viewType === 'files')
        {
            url = router.get('list-files', {slug: slug, path: directory});
        }
        else
        {
            url = router.get('list-assets', {slug: slug, path: directory});
        }
        this.getData(url, document.location.hash, directory);
    },

    initializePage: function initializePage()
    {
        var that = this;
        $('#list-form .directoryPaths').unbind().bind("click", function () {
            $(this).nextAll().remove();
            var hash = document.location.hash;
            var hashSplit = hash.split('/');
            var action = hashSplit[1];
            var viewType = hashSplit[2];
            var slug = hashSplit[3];

            var directory = $(this).attr('id');
            directory = directory.substring('asset:'.length).replace(/:/g, '/');
            var strLen = directory.length;
            directory = directory.slice(0, strLen - 1);

            if (directory)
            {
                document.location.hash = '/' + action + '/' + viewType + '/' + slug + '/' + directory;
            }
            else
            {
                document.location.hash = '/' + action + '/' + viewType + '/' + slug;
            }

            return false;
        });

        $('#list-form .directory').unbind().bind('click', function (/* event */) {
            var directory = $(this).attr('id');
            var hash = document.location.hash;
            document.location.hash = hash + '/' + directory;
            return false;
        });

        $('#list-form #toggle-asset-view').unbind('click').bind('click', function () {
            if (that.viewType === 'files')
            {
                that.viewType = 'assets';
                document.location.hash = '/list/assets/' + that.slug;
            }
            else
            {
                that.viewType = 'files';
                document.location.hash = '/list/files/' + that.slug;
            }
        });

        this.getMappingTable();
    },

    getMappingTable: function getMappingTable()
    {
        var that = this;
        $.ajax({
            url: that.mappingTableUrl,
            dataType: 'json',
            async: false,
            success: function (mappingData) {
                var remapping = mappingData.urnmapping || mappingData.urnremapping || {};
                var inverseMapping = that.inverseMapping;
                for (var key in remapping)
                {
                    if (remapping.hasOwnProperty(key))
                    {
                        inverseMapping[remapping[key]] = key;
                    }
                }
            }
        });
    }
});
