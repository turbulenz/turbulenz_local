// Copyright (c) 2010-2012 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*global ResourceCategory*/
/*global SummaryBar*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*exported LocalMetricsView*/

var LocalMetricsView = Backbone.View.extend({

    el: '#details',

    mimetypeData : {},
    inverseMapping : {},
    sessionData : {},
    staticFileUrl : '',
    slug : '',

    initialize: function ()
    {
        this.app = this.options.app;
        this.template = Templates.local_metrics_template;

        this.files_header_template = Templates.local_metrics_files_header_template;
        this.files_details_template = Templates.local_metrics_files_details_template;

        this.assets_header_template = Templates.local_metrics_assets_header_template;
        this.assets_details_template = Templates.local_metrics_assets_details_template;

        this.mimetypes_header_template = Templates.local_metrics_mimetypes_header_template;
        this.mimetypes_details_template = Templates.local_metrics_mimetypes_details_template;
        /*jshint nomen: false*/
        _.bindAll(this, 'render', 'initializePage', 'getDetails');
        /*jshint nomen: true*/
        this.app.bind('game:metrics', this.render);

        this.skeyPattern = new RegExp('sort-([a-zA-Z-]+)');

        return this;
    },

    render: function (slug)
    {
        var url = this.app.router.get('metrics-overview', {slug: slug});
        var that = this;
        this.slug = slug;

        $.get(url, function (data) {
            data = data.data;

            if (data.sessions.length > 1000) {
                data.sessions = data.sessions.slice(0, 1000);
                data.warning = '+1000 metrics-sessions found. Please delete some sessions from localdata/metrics/' + slug + ' folder.';
            }
            $(that.el).jqotesub(that.template, data);
            var mappingTableUrl = 'play/' + slug + '/' + data.mappingTable;
            that.initializePage(mappingTableUrl);

            $('#metrics-form>ul>li.session:first>.session-header>.session-title').click();
        });
        return this;
    },


    sortData : function sortData(sessionDataDict, sortKey, reverse)
    {
        var sort_by = function (sortKey, reverse) {

            reverse = (reverse) ? -1 : 1;
            return function (a, b) {

                a = a[sortKey] === undefined ? a.data[sortKey] : a[sortKey];
                b = b[sortKey] === undefined ? b.data[sortKey] : b[sortKey];

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
        return sessionDataDict.sort(sort_by(sortKey, reverse));
    },

    isEmpty:  function isEmpty(obj)
    {
        for (var prop in obj) {
            if (obj.hasOwnProperty(prop))
            {
                return false;
            }
        }
        return true;
    },

    getSizeStr : function getSizeStr(size)
    {
        var sizeStr;
        if (size > 1024)
        {
            sizeStr = ((size - size % 1024) / 1024).toString() + 'KB';
        }
        else
        {
            sizeStr = size.toString() + 'B';
        }
        return sizeStr;
    },

    groupData : function groupData(data)
    {
        var sortedData = this.sortData(data, 'assetName', false);
        var groupedData = [];
        groupedData[0] = {data: sortedData[0]};
        groupedData[0].numRequest = 1;
        var lastStoredIndex = 0;

        for (var i = 1; i < sortedData.length; i += 1)
        {
            if (sortedData[i].assetName === groupedData[lastStoredIndex].data.assetName)
            {
                groupedData[lastStoredIndex].numRequest += 1;
            }
            else
            {
                lastStoredIndex += 1;
                groupedData[lastStoredIndex] = {data: sortedData[i]};
                groupedData[lastStoredIndex].numRequest = 1;
            }
        }
        return groupedData;
    },

    groupByType : function groupByType(data)
    {
        var sortedData = this.sortData(data, 'type', false);
        var groupedData = [];
        var lastStoredEntry = {data: sortedData[0]};
        groupedData[0] = lastStoredEntry;
        lastStoredEntry.numFiles = 1;
        lastStoredEntry.totalSize = sortedData[0].size;
        lastStoredEntry.numRequest = 1;
        var lastStoredIndex = 0;

        for (var i = 1; i < sortedData.length; i += 1)
        {
            var sortedDataDict = sortedData[i];
            if (sortedDataDict.type === lastStoredEntry.data.type)
            {
                lastStoredEntry.numFiles += 1;
                lastStoredEntry.numRequest += 1;
                lastStoredEntry.totalSize += sortedDataDict.size;
            }
            else
            {
                lastStoredIndex += 1;
                lastStoredEntry = {data: sortedDataDict};
                groupedData[lastStoredIndex] = lastStoredEntry;
                lastStoredEntry.numFiles = 1;
                lastStoredEntry.numRequest = 1;
                lastStoredEntry.totalSize = sortedDataDict.size;
            }
        }

        for (i = 0; i < groupedData.length; i += 1)
        {
            groupedData[i].totalSizeStr = this.getSizeStr(groupedData[i].totalSize);
        }
        return groupedData;
    },

    getDetails : function getDetails(controller, timestamp, dataCallback)
    {
        var sessionData = this.sessionData;
        var that = this;
        var slug = this.slug;
        var url = this.app.router.get('metrics-details', {slug: slug, timestamp: timestamp});

        $.getJSON(url, {}, function (session) {
            var data = session.data.entries;
            for (var i = 0; i < data.length; i += 1)
            {
                var dataEntry = data[i];
                //convert size string received into number
                dataEntry.size = parseInt(dataEntry.size, 10);
                dataEntry.sizeStr = that.getSizeStr(dataEntry.size);

                var key = dataEntry.file.replace('staticmax/', '');
                dataEntry.assetName = that.inverseMapping[key] || dataEntry.file;
            }
            sessionData[timestamp] = that.groupData(data);
            that.mimetypeData[timestamp] = that.groupByType(data);

            dataCallback.call(that, controller, true, false, timestamp);
        });
    },


    resourceCategories : {
        ".html" : new ResourceCategory('html',  'HTML',        '#800080'),
        ".css":   new ResourceCategory('css',   'Stylesheets', '#ffff00'),
        ".js":    new ResourceCategory('js',    'Scripts',     '#800000'),
        ".tzjs":  new ResourceCategory('tzjs',  'Application', '#ff0000'),
        ".json":  new ResourceCategory('json',  'JSON',        '#808080'),
        ".cgfx":  new ResourceCategory('cgfx',  'Shaders',     '#00ff00'),
        ".tar":   new ResourceCategory('tar',   'Archives',    '#808000'),
        ".dae":   new ResourceCategory('dae',   'COLLADA',     '#c0c0c0'),
        ".png":   new ResourceCategory('png',   'PNG',         '#008000'),
        ".jpg":   new ResourceCategory('jpg',   'JPEG',        '#00ffff'),
        ".tga":   new ResourceCategory('tga',   'TGA',         '#008080'),
        ".dds":   new ResourceCategory('dds',   'DDS',         '#0000ff'),
        ".ktx":   new ResourceCategory('ktx',   'KTX',         '#0000ff'),
        ".ogg":   new ResourceCategory('ogg',   'OGG',         '#000080'),
        ".wav":   new ResourceCategory('wav',   'WAV',         '#ff00ff'),
        other: new ResourceCategory('other', 'Other',       '#ffffff'),
        unknown: new ResourceCategory("unknown", "Unknown", "rgb(0,0,0)")
    },

    createAssetSummary : function createAssetSummary(assetDict, timestamp)
    {
        var that = this;
        var computeSummaryValues = function (items)
        {
            var total = 0;
            var categoryValues = {};

            var itemsLength = items.length;
            for (var i = 0; i < itemsLength; i += 1)
            {
                var item = items[i];
                var value = item.value;
                if (typeof value === "undefined")
                {
                    continue;
                }
                if (!(item.name in categoryValues))
                {
                    if (!(item.name in that.resourceCategories))
                    {
                        item.name = 'other';
                        if (!('other' in categoryValues))
                        {
                            categoryValues.other = 0;
                        }
                    }
                    else
                    {
                        categoryValues[item.name] = 0;
                    }
                }
                categoryValues[item.name] += value;
                total += value;
            }

            return {categoryValues: categoryValues, total: total};
        };

        var formatValue = function (value)
        {
            return Number.bytesToString(value);
        };

        var testItems = [];
        for (var i = 0; i < assetDict.length; i += 1)
        {
            testItems[i] = {name: assetDict[i].data.ext, value: assetDict[i].totalSize};
        }

        var summaryBar = new SummaryBar(this.resourceCategories);
        summaryBar.element.id = "resources-summary";

        var summaryContainerElement = document.getElementById("summary-container-" + timestamp);
        summaryContainerElement.appendChild(summaryBar.element);

        summaryBar.update(testItems, computeSummaryValues, formatValue);
    },

    displayData : function displayData(controller, keepActive, reverse, timestamp)
    {
        var skeyPattern = this.skeyPattern;
        var target =  $(controller).parent().parent().find('div.details-table');
        var sortKey = $(controller).attr('class').match(skeyPattern)[1];
        var mimetypeDataDict = this.mimetypeData[timestamp];
        var sessionDataDict = this.sessionData[timestamp];
        var that = this;
        var slug = this.slug;

        if ($(controller).hasClass('active') && !keepActive)
        {
            $(controller).removeClass('active');
            target.empty();
        }
        else
        {
            $(controller).siblings().removeClass('active');
            $(controller).addClass('active');

            var sortedSessionDataDict = this.sortData(sessionDataDict, sortKey, reverse);
            var sortedMimetypeDataDict = this.sortData(mimetypeDataDict, sortKey, reverse);

            var idSelector = timestamp.replace('.', '\\.');
            //render the metrics session templates
            if ($(controller).hasClass('files-header'))
            {
                target.jqotesub(that.files_header_template);
                $('#' + idSelector + ' ~ .details-table').children('table').children('tbody').jqoteapp(that.files_details_template,
                                                   {'sessionDataDict': sortedSessionDataDict,
                                                     'slug': slug,
                                                     'timestamp': timestamp});
            }
            else if ($(controller).hasClass('assets-header'))
            {
                target.jqotesub(that.assets_header_template, timestamp);
                $('#' + idSelector + ' ~ .details-table').children('table').children('tbody').jqoteapp(that.assets_details_template,
                                                                                                        sortedMimetypeDataDict);
            }
            else if ($(controller).hasClass('mimetypes-header'))
            {
                target.jqotesub(that.mimetypes_header_template);
                $('#' + idSelector + ' ~ .details-table').children('table').children('tbody').jqoteapp(that.mimetypes_details_template,
                                                                                                        sortedMimetypeDataDict);
            }

            target.find('tr:even').addClass('stripe');

            var table = $(controller).parent().parent().find(".sort-controller");
            // give the header the little arrow icon
            if (reverse)
            {
                table.find('span').filter(function () {
                    return $(this).parent().attr('class').match(skeyPattern)[1] === sortKey;
                }).addClass('active-reverse');
            }
            else
            {
                table.find('span').filter(function () {
                    return $(this).parent().attr('class').match(skeyPattern)[1] === sortKey;
                }).addClass('active');
            }

            // add new listeners to the headers
            table.find('th').click(function ()  {
                var classes = $(controller).attr('class').split(' ');
                var numClasses = classes.length;

                //remove header classes that are not sort keys
                for (var i = 0; i < numClasses; i += 1)
                {
                    if (classes[i].indexOf('sort-') === 0)
                    {
                        $(controller).removeClass(classes[i]);
                    }
                }
                $(controller).addClass($(this).attr('class').match(skeyPattern)[0]);

                //sort and display data (based on the clicked header = controller)
                if ($(this).find('span').hasClass('active'))
                {
                    that.displayData(controller, true, true, timestamp);
                }
                else
                {
                    that.displayData(controller, true, false, timestamp);
                }

                //for assets tab, get summaries
                if ($(controller).hasClass('assets-header'))
                {
                    that.createAssetSummary(sortedMimetypeDataDict, timestamp);
                }
            });
        }
    },

    initializePage : function initializePage(mappingTableUrl)
    {
        var sessionData = this.sessionData;
        var that = this;

        $.get(mappingTableUrl,
            function (mappingData)
            {
                var inverseMapping = that.inverseMapping;
                if (that.isEmpty(inverseMapping) && mappingData)
                {
                    var remapping = mappingData.urnmapping || mappingData.urnremapping || {};
                    for (var key in remapping)
                    {
                        if (remapping.hasOwnProperty(key))
                        {
                            inverseMapping[that.staticFileUrl + remapping[key]] = key;
                        }
                    }
                }
            }
        );

        // hide-show functionality
        $('.session-title').unbind('click').bind('click', function () {
            var target = $(this).parents('.session');

            if ($(this).hasClass('active'))
            {
                target.removeClass('active');
                target.find('.active').removeClass('active');
                target.find('.details-table').empty();
            }
            else
            {
                target.addClass('active');
                $(this).addClass('active');
            }
            return false;
        });

        $('.files-header').unbind('click').bind('click', function () {
            var tstamp = $(this).parent().attr('id');
            if (sessionData[tstamp])
            {
                that.displayData(this, false, false, tstamp);
            }
            else
            {
                that.getDetails(this, tstamp, that.displayData);
            }
            return false;
        });

        function displayMimeTypeData(controller, keepActive, reverse, timestamp)
        {
            that.displayData(controller, keepActive, reverse, timestamp);

            if ($(controller).hasClass('active'))
            {
                that.createAssetSummary(that.mimetypeData[timestamp], timestamp);
            }
        }

        $('.assets-header').unbind('click').bind('click', function () {
            var tstamp = $(this).parent().attr('id');
            var mimetypeDataDict = that.mimetypeData[tstamp];

            if (mimetypeDataDict)
            {
                displayMimeTypeData(this, false, false, tstamp);
            }
            else
            {
                that.getDetails(this, tstamp, displayMimeTypeData);
            }
            return false;
        });

        $('.mimetypes-header').unbind('click').bind('click', function () {
            var tstamp = $(this).parent().attr('id');
            var mimeTypeData = that.mimetypeData[tstamp];
            if (mimeTypeData)
            {
                that.displayData(this, false, false, tstamp);
            }
            else
            {
                that.getDetails(this, tstamp, that.displayData);
            }
            return false;
        });

        $('.button.delete').unbind('click').bind('click', function () {
            var sessionRoot = $(this).parent().parent().parent();
            var url = $(this).find('a').attr('href');
            $.get(url, function (/* data */) {
                sessionRoot.remove();
                if ($('.session').length === 0) {
                    $('.empty').show();
                    $('#delete-all, .cap').hide();
                }
            });
            return false;
        });

        $('.button').hover(
            function () {
                $(this).addClass('hover-target');
            },
            function () {
                $(this).removeClass('hover-target');
            }
        );

        $('#delete-all').unbind('click').bind('click', function () {
            $('.session').each(function () {
                var url = $(this).find('.delete a').attr('href');
                var sessionRoot = $(this);
                $.get(url, function (/* data */) {
                    sessionRoot.remove();
                    if ($('.session').length === 0) {
                        $('.empty').show();
                        $('#delete-all, .cap').hide();
                    }
                });
            });
            return false;
        });
    }
});
