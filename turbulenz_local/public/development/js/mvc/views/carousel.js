// Copyright (c) 2011-2012 Turbulenz Limited

/*global Backbone*/
/*global Templates*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*global window*/
/*exported CarouselView*/

var CarouselView = Backbone.View.extend({

    // Views always have a DOM element, even if it is invisible in the
    // page. This area view will be bound to an existing element, so, I
    // will use a jQuery selector to select the element. If I had not
    // done selected an existing element -- or defined a 'tagName',
    // backbone.js would have created a <div /> element that is simply
    // not yet associated with the document.
    el: '#content',

    events: {

    },

    initialize: function initializeFn()
    {
        this.app = this.options.app;
        this.template = Templates.local_application_template;
        this.game_panel_template = Templates.local_game_panel_template;
        this.game_progress_panel_template = Templates.local_progress_panel_template;
        this.action_buttons_template = Templates.local_action_buttons_template;
        /*jshint nomen: false*/
        _.bindAll(this, 'render', 'expand', 'makeCarousel', 'moveToFocus', 'collapse', 'getActionButtons', 'setActionspacerListeners',
                        'onLogin', 'onLoginKeyUp', 'onUsernameChange');
        /*jshint nomen: true*/
        this.app.bind('carousel:make', this.makeCarousel);
        this.app.bind('carousel:collapse', this.collapse);
        this.app.bind('slug:change', this.setActionButtons);
        this.app.bind('carousel:refresh', this.render);

        this.username = $.cookie('local');
        if (!this.username)
        {
            var that = this;
            $.ajax({
                url: '/local/v1/user/get',
                async: false,
                type: 'GET',
                success: function successFn(jsonData) {
                    that.username = jsonData.data.username;
                    var localLoginDiv = $('#local-login');
                    if (localLoginDiv)
                    {
                        var localLoginText = localLoginDiv.find('.local-login-text');
                        localLoginText.text('Currently logged in as ' + that.username);
                    }
                }
            });
        }

        this.carouselGlobals =
        {
            indexPattern: new RegExp('index([0-9]+)'),
            itemsInView: 5
        };
        this.router = this.app.router;

        return this;
    },


    render: function renderFn()
    {
        $(this.el).jqotesub(this.template);
        var $login = $('#local-login');

        if (this.username)
        {
            $login.find('.local-login-text').text('Currently logged in as ' + this.username);
        }

        $login.find('.local-login-button').on('click', this.onLogin);
        $login.find('.local-login-input').on('keyup', this.onLoginKeyUp);

        var thisView = this;
        var url = this.router.get('games-list');
        $.ajax({
            url: url,
            async: false,
            type: 'GET',
            success: function successFn(data) {
                var games = data.data;
                var carousel = $('#carousel');

                function getDate(modifiedString)
                {
                    if (modifiedString === 'Never')
                    {
                        return null;
                    }
                    try
                    {
                        var timeDateSplit = modifiedString.split(' | ');
                        var time = timeDateSplit[0];
                        var date = timeDateSplit[1];
                        var dateSplit = date.split('/');
                        var timeSplit = time.split(':');
                        return new Date(dateSplit[2], dateSplit[1], dateSplit[0], timeSplit[0], timeSplit[1], 0, 0);
                    }
                    catch (e)
                    {
                        return null;
                    }
                }

                var gamesList = [];

                for (var a in games)
                {
                    if (games.hasOwnProperty(a))
                    {
                        gamesList.push(games[a]);
                    }
                }

                gamesList.sort(function (a, b) {
                    return getDate(b.modified) - getDate(a.modified);
                });

                var gamesListLength = gamesList.length;
                var gamesListIndex;

                for (gamesListIndex = 0; gamesListIndex < gamesListLength; gamesListIndex += 1)
                {
                    carousel.jqoteapp(thisView.game_panel_template, {'game': gamesList[gamesListIndex],
                                                                     'loop_index': gamesListIndex});
                }

                thisView.app.trigger('carousel:make');
            }
        });
        return this;
    },

    onLogin: function onLoginFn()
    {
        var $login = $('#local-login');
        var localLoginInput = $login.find('.local-login-input');

        var newUsername = localLoginInput.val().toLowerCase();
        var that = this;
        $.ajax({
            url: '/local/v1/user/login',
            data: {
                'username': newUsername
            },
            async: false,
            type: 'POST',
            success: function successFn(/* data */) {
                $login.find('.local-login-text').text('Currently logged in as ' + newUsername);
                that.username = newUsername;
            },
            error: function errorFn(jqxhr, status /*, errorThrown */)
            {
                if (status === 'error' && jqxhr.status === 400)
                {
                    var msg = JSON.parse(jqxhr.responseText).msg;
                    window.alert(msg);
                    localLoginInput.val('');
                }
            }
        });
    },

    onLoginKeyUp: function onLoginKeyUp(event)
    {
        if (event.keyCode === 13) // 13 = enter
        {
            this.onLogin();
        }
    },

    // expand an action once an action button is clicked
    setActionspacerListeners: function setActionspacerListenersFn()
    {
        $('#actionspacer a').unbind('click').bind('click', function () {
            document.location.hash = $(this).attr('href');
            return false;
        });
    },


    setActionButtons: function setActionButtonsFn(slug)
    {
        $('#actionspacer').jqotesub(this.action_buttons_template, slug);
        $('#actionspacer').show();
        // append event handlers to action buttons
        this.setActionspacerListeners();
    },

    // clipping rectangle class. Facilitates manipulation of css-rect attributes
    clipRect: function clipRectFn(rect)
    {
        var clip = rect.match(/\d+/g);

        return {
            top: parseInt(clip[0], 10),
            right: parseInt(clip[1], 10),
            bottom: parseInt(clip[2], 10),
            left: parseInt(clip[3], 10),
            toString: function toStringFn() {
                return 'rect(' + this.top + 'px ' + this.right + 'px ' + this.bottom + 'px ' + this.left + 'px)';
            }
        };
    },


    getClip: function getClipFn(elem)
    {
        var $elem = $(elem);
        var ret = $elem.css('clip');
        if (!ret)
        {
            // IE refuses to return 'clip'
            // This tries to reconstructs what it should return
            var currentStyle = $elem[0].currentStyle;
            if (currentStyle)
            {
                ret = 'rect(' + currentStyle.clipTop + ' ' +
                                currentStyle.clipRight + ' ' +
                                currentStyle.clipBottom + ' ' +
                                currentStyle.clipLeft + ')';
            }
        }
        return ret;
    },

    format_deploy_check_response: function format_deploy_check_responseFn(msg)
    {
        var result = '';
        for (var key1 in msg)
        {
            if (msg[key1] !== undefined)
            {
                result += 'Issues in ' + key1 + ':\n';
                var items = msg[key1];
                for (var item in items)
                {
                    if (items[item] !== undefined)
                    {
                        item = items[item];
                        result += '  - ' + item[0] + ':\n';
                        var issues = item[1];
                        for (var key2 in issues)
                        {
                            if (issues[key2] !== undefined && issues[key2].length > 0)
                            {
                                var issueType = issues[key2];
                                result += '    - ' + key2 + ':\n';
                                for (var issue in issueType)
                                {
                                    if (issueType[issue] !== undefined)
                                    {
                                        result += '      - ' + issueType[issue] + '\n';
                                    }
                                }
                            }
                        }
                        result += '\n';
                    }
                }
                result += '\n';
            }
        }

        return result;
    },

    //calculates percentage of completed fields and enables deploy button
    populateProgress: function populateProgressFn(slug, index /*, canDeploy */)
    {
        var that = this;
        var compSteps = $('.' + slug + '.step-list>li.complete').length;
        var allSteps = $('.' + slug + '.step-list>li').length;
        var percentage = (compSteps / allSteps) * 100;

        $('.' + slug + '.progress-percentage>span').html(Math.floor(percentage));

        $('#deploy_button_id' + index).click(function () {

            $.ajax({
                type: 'get',
                url: that.router.get('deploy-check', {slug: slug}),
                success: function successFn(data) {

                    if (!data.ok)
                    {
                        var text = that.format_deploy_check_response(data.msg);
                        text += 'If you want to continue, these attributes will be set to default values.';
                        if (!window.confirm(text))
                        {
                            return false;
                        }
                    }

                    that.app.trigger('deploy:set');
                    that.app.trigger('deploy:initialise', slug);
//                    $('#deploy_login_dialog_id').dialog('open');
                    return true;
                },

                error: function errorFn(XMLHttpRequest) {
                    var response = JSON.parse(XMLHttpRequest.responseText);
                    if (XMLHttpRequest.status === 400)
                    {
                        window.alert(that.format_deploy_check_response(response.msg));
                    }
                    else
                    {
                        window.alert(response.msg);
                    }
                    return false;
                }
            });
        });

        $('a#deploy_button_id' + index).hover(
            function () {
                $(this).addClass("hover");
            },
            function () {
                $(this).removeClass("hover");
            }
        );
    },


    // Expand a game-panel. 'target' needs to point at the surrounding <li> tag.
    expand: function expandFn(target)
    {
        var list = '#carousel';
        var thisView = this;

        $(target).addClass('selected');
        var slug = $(target).attr('id');

        $(target).width(960);
        $(list)[0].expanded = true;
        //get game index on the carousel
        var game = $(target).attr('class').match(this.carouselGlobals.indexPattern)[1];

        var url = this.router.get('edit-overview', {slug: slug});

        $.get(url, function (data) {
            $('li#' + slug).removeClass('index').addClass('index' + game).addClass('selected');
            $('ul#carousel>li#slug').jqotesub(thisView.game_panel_template, {'game': slug,
                                                                      'loop_index': game});
            $(target).find('.progress-panel').show();

            $(target + '>div.progress-panel').jqotesub(thisView.game_progress_panel_template, {'game': data,
                                                                                               'loop_index': game});
            $('.step-list>li').css({'float': 'none'});
            var canDeploy = data.data.deployable;
            thisView.populateProgress(slug, game, canDeploy);
        });

        this.moveToFocus(list, game);
        // move this game's actions into the action area
        if ($('#actionspacer>li').length === 0)
        {
            thisView.setActionButtons(slug);
        }
        return false;
    },


    // removes the temporary game from the list
    removeTemporaryGame: function removeTemporaryGameFn()
    {
        var that = this;
        // get the currently expanded game.
        var $temp = $('#carousel>li.Temporary');
        // if it is temporary it should be deleted when the user collapses it
        if ($temp.length > 0)
        {
            $temp.remove();
            // no confirmation necessary here
            that.app.editView.deleteGame(false, $temp.attr('id'), true);
            return false;
        }
        return true;
    },


    // check the current state of the carousel and display or hide the scroll
    // buttons
    displayButtons: function displayButtonsFn(list)
    {
        var $list = $(list);
        var $list0 = $list[0];
        var index = parseInt($list0.index, 10);
        var numItems = parseInt($list0.numItems, 10);
        var itemsInView = parseInt($list0.itemsInView, 10);
        var maxIndex;

        if ($list0.expanded)
        {
            maxIndex = numItems - 1;
        }
        else if (numItems > itemsInView)
        {
            maxIndex = numItems - itemsInView;
        }
        else
        {
            maxIndex = 0;
        }

        var viewport = $list.parent('.viewport');
        if (index < maxIndex)
        {
            viewport.siblings('.carousel-btn.next').show();
        }
        else
        {
            viewport.siblings('.carousel-btn.next').hide();
        }

        if (index > 0)
        {
            viewport.siblings('.carousel-btn.prev').show();
        }
        else
        {
            viewport.siblings('.carousel-btn.prev').hide();
        }

        return false;
    },

    // expanding/collapsing the game on clicking its picture
    setGameboxListeners: function setGameboxListenersFn(list)
    {
        $(list).find('.game-box').unbind('click').bind('click', function () {
            var target = $(this).parent('li');

            if (target.hasClass('selected'))
            {
                document.location.hash = '';
            }
            else
            {
                document.location.hash = $(this).parent().attr('id');
            }
            return false;
        });
    },

    makeCarousel: function makeCarouselFn()
    {
        var list = '#carousel';
        var that = this;
        if ($(list).length !== 0)
        {
            // calculate dimensions etc
            var $list = $(list);
            var viewport = $list.parent('.viewport');
            var viewWidth = viewport.width();
            var itemsInView = this.carouselGlobals.itemsInView;
            var numItems = $list.find('>li').length;
            var itemWidth = viewWidth / itemsInView;
            // set the list to be as wide as its contents
            $list.find('>li').width(itemWidth);
            // store globally needed values in the list-DOM
            var $list0 = $list[0];
            $list0.numItems = numItems;
            $list0.itemsInView = itemsInView;
            $list0.itemWidth = itemWidth;
            $list0.index = 0;   // the leftmost, visible game
            $list0.expanded = false;

            // attach new click-listeners to the scroll buttons ...
            viewport.siblings('.carousel-btn.next').unbind().click(function () {
                that.scrollRight(list);
            });
            viewport.siblings('.carousel-btn.prev').unbind().click(function () {
                that.scrollLeft(list);
            });
            // ... and display them if necessary
            this.displayButtons(list);
            // attach click-listeners to list items
            this.setGameboxListeners(list);
        }
        return false;
    },

    moveToFocus: function moveToFocusFn(list, index)
    {
        var $list = $(list);
        var $list0 = $list[0];
        var numItems = $list0.numItems;

        index = parseInt(index, 10);
        if (index < 0)
        {
            index = 0;
        }
        else if (numItems && index >= numItems)
        {
            index = (numItems - 1);
        }

        // update the list's index'
        $list0.index = index;

        var firstItem = $(list).find('li.index' + index);
        var i, item;
        if (!firstItem.hasClass('selected'))
        {
            var lastItem = (index + this.carouselGlobals.itemsInView);

            for (i = 0; i < numItems; i += 1)
            {
                item = $list.find('li.index' + i);
                if (i >= index && i < lastItem)
                {
                    item.show();
                }
                else
                {
                    item.hide();
                }
            }
        }
        else
        {
            for (i = 0; i < numItems; i += 1)
            {
                item = $list.find('li.index' + i);
                if (i === index)
                {
                    item.show();
                }
                else
                {
                    item.hide();
                }
            }
        }

        this.displayButtons(list);
        return false;
    },

    // Collapse all game-panels.
    collapse: function collapseFn()
    {
        var list = '#carousel';
        var $list = $(list);
        // Make sure the carousel even exists. It's possible to open pages that do not contain the carousel.
        if ($list.length !== 0)
        {
            this.removeTemporaryGame();
            // empty details and action areas
            $('#details').empty();
            $('#actionspacer').empty().hide();
            $('.progress-panel').hide();

            // fold up list-item
            $('#games .game-panel')
                .stop().width($list[0].itemWidth)
                .find('.selected').removeClass('selected');     // clear selected game buttons

            var $list0 = $list[0];
            $list0.expanded = false;

            var numItems = $list0.numItems;
            var numItemsInView = $list0.itemsInView;
            var index =  $list0.index;

            if (numItems < numItemsInView)
            {
                this.moveToFocus(list, 0);
            }
            else if (index > (numItems - numItemsInView))
            {
                this.moveToFocus(list, (numItems - numItemsInView));
            }
            else
            {
                this.moveToFocus(list, index);
            }

            document.location.hash = '';
        }
        return false;
    },


    executeScrolling: function executeScrollingFn(list, newIndex)
    {
        var thisView = this;
        if ($(list)[0].expanded)
        {
            if (newIndex >= 0 && newIndex < $(list)[0].numItems)
            {
                var slug = $('li.index' + newIndex).attr('id');
                var selectedButton = $('#actionspacer>li>a.selected');
                if (selectedButton.length > 0)
                {
                    var url = selectedButton.attr('href');
                    var urlSplit = url.split('/');
                    var action;
                    if (selectedButton.attr('id') === 'list-button')
                    {
                        action = urlSplit[1] + '/' + urlSplit[2];
                    }
                    else
                    {
                        action = urlSplit[1];
                    }
                    document.location.hash = '/' + action + '/' + slug;
                }
                else
                {
                    document.location.hash = slug;
                }
                return false;
            }
        }
        else
        {
            thisView.moveToFocus(list, newIndex);
        }

        thisView.displayButtons(list);
        return false;
    },

    scrollRight: function scrollRightFn(list)
    {
        var newIndex = parseInt($(list)[0].index, 10) + 1;
        this.executeScrolling(list, newIndex);
        return false;
    },

    scrollLeft: function scrollLeftFn(list)
    {
        var newIndex = parseInt($(list)[0].index, 10) - 1;
        this.executeScrolling(list, newIndex);
        return false;
    },

    addGame: function addGameFn()
    {
        var that = this;

        if ($('#carousel .Temporary').length === 0)
        {
            $.ajax({
                type: 'get',
                url: this.router.get('games-new'),
                success: function successFn(/* data */) {
                    that.render();
                    that.app.trigger('carousel:make');
                    document.location.hash = '/edit/' + $('#carousel .Temporary').attr('id');
                },
                error: function errorFn() {
                    window.alert('Game could not be created.');
                }
            });
        }
        return false;
    }
});
