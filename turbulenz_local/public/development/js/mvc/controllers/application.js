// Copyright (c) 2011-2013 Turbulenz Limited

/*global Backbone*/
/*global TurbulenzStore*/
/*global TurbulenzGameNotifications*/
/*global TurbulenzBridge*/
/*global LocalMessageView*/
/*global LocalPlayView*/
/*global CarouselView*/
/*global LocalMetricsView*/
/*global LocalListView*/
/*global LocalUserdataView*/
/*global LocalDeployView*/
/*global LocalEditView*/
/*jshint nomen: false*/
/*global _*/
/*global $*/
/*jshint nomen: true*/
/*exported LocalApplicationController*/

var LocalApplicationController = Backbone.Controller.extend({

    routes: {
        ''                              : 'home',
        'add-game'                      : 'create',
        ':slug/?'                       : 'game',
        '/play/:slug/?'                 : 'play_versions',
        '/play/:slug/:version'          : 'play',
        '/edit/:slug/?'                 : 'edit',
        '/metrics/:slug/?'              : 'metrics',
        '/list/:type/:slug/?'           : 'list',
        '/list/:type/:slug/*directory'  : 'list',
        '/userdata/:slug'               : 'userdata',
        '/userdata/:slug/*directory'    : 'userdata'
    },

    initialize: function initializeFn(options) {
        this.pluginInfo = options.pluginInfo;
        this.sdkUrl = options.sdkUrl;
        this.router = options.router;
        this.viewerEnabled = options.viewer_enabled;
        /*jshint nomen: false*/
        _.bindAll(this, 'home', 'game', 'play');
        /*jshint nomen: false*/

        this.messageView = new LocalMessageView({
            engine: this.pluginInfo,
            sdk: this.sdkUrl
        });

        this.playView = new LocalPlayView({
            app: this,
            engine: this.pluginInfo
        });
        this.carousel = new CarouselView({app: this});
        this.metrics = new LocalMetricsView({app: this});
        this.list = new LocalListView({app: this});
        this.userdata = new LocalUserdataView({app: this});
        this.deploy = new LocalDeployView({app: this});
        this.editView = new LocalEditView({app: this});

        this.messageView.render();
        this.deploy.render();

        this.turbulenzBridge = TurbulenzBridge.create(this);
        this.store = TurbulenzStore.create(this);
        this.gameNotifications = TurbulenzGameNotifications.create(this);

        this.playingGameSlug = null;
        var that = this;
        this.bind('game:play', function (slug /*, version */)
            {
                that.playingGameSlug = slug;
            });

        this.bind('game:stop', function ()
            {
                that.playingGameSlug = null;
            });

        return this;
    },

    route: function routeFn(route, name, callback) {
        if (!Backbone.history)
        {
            Backbone.history = new Backbone.History();
        }

        /*jshint nomen: false*/
        if (!_.isRegExp(route))
        {
            route = this._routeToRegExp(route);
        }

        Backbone.history.route(route, _.bind(function (fragment) {
            if (!this.preLeave())
            {
                return;
            }
            this.currentView = null;
            var args = this._extractParameters(route, fragment);
            callback.apply(this, args);
            this.trigger.apply(this, ['route:' + name].concat(args));
        }, this));
        /*jshint nomen: true*/
    },

    home: function homeFn() {
        this.trigger('carousel:refresh');
        this.trigger('carousel:collapse');
        this.trigger('game:stop');
    },

    create: function createFn() {
        this.carousel.addGame('add-game');
    },

    game: function gameFn(slug, quick) {
        this.trigger('game:stop');

        if (!quick)
        {
            this.trigger('carousel:refresh');
        }

        if ($('#carousel').find('#' + slug).length === 0)
        {
            //game does not exist
            this.trigger('carousel:collapse');
        }
        else
        {
            $('#actionspacer').empty();
            this.carousel.expand('#' + slug);
            $('#details').empty();
        }
    },

    preLeave: function preLeavefn(/* args */) {
        if (this.currentView && this.currentView.preLeave && !this.currentView.preLeave())
        {
            if (window.location.hash !== this.currentHash)
            {
                window.location.hash = this.currentHash;
            }
            return false;
        }
        return true;
    },

    prepareAction: function prepareActionFn(slug, action) {
        var $game = $('#' + slug);

        //no game selected for the action and not creating a new game
        if (!$game.hasClass('selected') && !$game.hasClass('Temporary'))
        {
            this.trigger('carousel:collapse');
        }

        //if carousel empty
        if ($('#carousel').length === 0)
        {
            this.trigger('carousel:refresh');
        }

        var actBtn = $('#' + action + '-button');
        if (!actBtn.hasClass('selected'))
        {
            actBtn
                .addClass('selected')
                .parent().siblings().children().removeClass('selected');
        }

        this.currentView = null;
    },

    setCurrentView: function (view) {
        this.currentView = view;
        this.currentHash = window.location.hash;
    },

    play_versions: function (slug) {
        this.game(slug, true);
        this.prepareAction(slug, 'play');
        this.trigger('game:versions', slug);
    },

    play: function playFn(slug, version) {
        this.trigger('game:play', slug, version);
        this.currentView = undefined;
    },

    edit: function editFn(slug) {
        this.game(slug, true);
        this.prepareAction(slug, 'edit');
        this.trigger('game:edit', slug);
    },

    metrics: function metricsFn(slug) {
        this.game(slug, true);
        this.prepareAction(slug, 'metrics');
        this.trigger('game:metrics', slug);
    },

    list: function listFn(type, slug, directory) {
        this.game(slug, true);
        this.prepareAction(slug, 'list');
        this.trigger('assets:list', type, slug, directory);
    },

    userdata: function userdataFn(slug, directory) {
        this.game(slug, true);
        this.prepareAction(slug, 'userdata');
        this.trigger('game:userdata', slug, directory);
    }
});
