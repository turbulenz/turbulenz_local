# Copyright (c) 2010-2013 Turbulenz Limited
"""Routes configuration

The more specific and detailed routes should be defined first so they
may take precedent over the more generic routes. For more information
refer to the routes manual at http://routes.groovie.org/docs/
"""

# pylint: disable=F0401
from pylons import config
from routes import Mapper
# pylint: enable=F0401


# pylint: disable=R0915
def make_map():
    """Create, configure and return the routes Mapper"""
    router = Mapper(directory=config['pylons.paths']['controllers'])
    router.minimization = False

    # main APPLICATIONS

    router.connect('local-app', '/', controller='localv1', action='app')
    router.connect('disassemble-app', '/disassemble/{slug}/{asset:.+}', controller='disassembler', action='app')
    router.connect('viewer-app', '/view/{slug}/{asset:.+}', controller='viewer', action='app')

    # application API for local only!
    with router.submapper(controller='localv1/games', path_prefix='/local/v1/games') as m:
        m.connect('games-list', '/list', action='list')
        m.connect('games-new', '/new', action='new')
        m.connect('games-details', '/details/{slug}', action='details')
        m.connect('games-sessions', '/sessions', action='sessions')

    with router.submapper(controller='localv1/edit', path_prefix='/local/v1/edit/{slug}') as m:
        m.connect('edit-overview', '', action='overview')
        m.connect('edit-load', '/load', action='load')
        m.connect('edit-save', '/save', action='save')
        m.connect('edit-delete', '/delete', action='delete')
        m.connect('edit-create-slug', '/create-slug', action='create_slug')
        m.connect('edit-directory-options', '/directory-options', action='directory_options')

    with router.submapper(controller='localv1/play', path_prefix='/local/v1/play/{slug}') as m:
        m.connect('play-versions', '', action='versions')

    with router.submapper(controller='localv1/list', path_prefix='/local/v1/list/{slug}') as m:
        m.connect('list-overview', '', action='overview')
        m.connect('list-assets', '/assets/{path:.*}',  action='assets')
        m.connect('list-files', '/files/{path:.*}', action='files')

    with router.submapper(controller='localv1/metrics', path_prefix='/local/v1/metrics/{slug}') as m:
        m.connect('metrics-overview', '', action='overview')
        m.connect('metrics-stop-recording', '/stop-recording', action='stop_recording')
        m.connect('metrics-as-csv', '/session/{timestamp}.csv', action='as_csv')
        m.connect('metrics-as-json', '/session/{timestamp}.json', action='as_json')
        m.connect('metrics-delete', '/session/{timestamp}/delete', action='delete')
        m.connect('metrics-details', '/session/{timestamp}', action='details')

    with router.submapper(controller="localv1/userdata", path_prefix='/local/v1/userdata/{slug}') as m:
        m.connect('userdata-overview', '', action='overview')
        m.connect('userdata-keys', '/{username}', action='userkeys')
        m.connect('userdata-as-text', '/{username}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9\-]+)*}', action='as_text')

    with router.submapper(controller="localv1/deploy", path_prefix='/local/v1/deploy') as m:
        m.connect('deploy-login', '/login', action='login')
        m.connect('deploy-try-login', '/try-login', action='try_login')
        m.connect('deploy-start', '/start', action='start')
        m.connect('deploy-progress', '/progress', action='progress')
        m.connect('deploy-postupload-progress', '/postupload_progress', action='postupload_progress')
        m.connect('deploy-cancel', '/cancel', action='cancel')
        m.connect('deploy-check', '/check/{slug:[A-Za-z0-9\-]+}', action='check')

    with router.submapper(controller="localv1/user", path_prefix='/local/v1/user') as m:
        m.connect('login-user', '/login', action='login')
        m.connect('get-user', '/get', action='get_user')

    # global game API for local, hub and the gaming site
    with router.submapper(controller="apiv1/userdata", path_prefix='/api/v1/user-data') as m:
        m.connect('/{action:read|set|remove|exists}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9\-]+)*}')

        m.connect('/remove-all', action='remove_all')
        m.connect('/read', action='read_keys')

        # for backwards compatibility
        m.connect('/get/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9\-]+)*}', action='read')
        m.connect('/get-keys', action='read_keys')

    with router.submapper(controller="apiv1/gameprofile", path_prefix='/api/v1/game-profile') as m:
        m.connect('/{action:read|set|remove}')
        # Local API for testing only
        m.connect('/remove-all/{slug:[A-Za-z0-9\-]+}', action='remove_all')

    with router.submapper(controller="apiv1/leaderboards", path_prefix='/api/v1/leaderboards') as m:
        # Leaderboards Public API
        m.connect('/read/{slug:[A-Za-z0-9\-]+}', action='read_meta')

        m.connect('/scores/read/{slug:[A-Za-z0-9\-]+}', action='read_overview')
        m.connect('/scores/read/{slug:[A-Za-z0-9\-]+}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*}',
                  action='read_expanded')

        m.connect('/aggregates/read/{slug:[A-Za-z0-9\-]+}',
                  action='read_aggregates')

        # Leaderboards Developer API
        m.connect('/scores/set/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*}', action='set')

        # Local API for testing only
        m.connect('/scores/remove-all/{slug:[A-Za-z0-9\-]+}', action='remove_all')
        m.connect('/reset-meta-data', action='reset_meta')

    with router.submapper(controller='apiv1/games', path_prefix='/api/v1/games') as m:
        m.connect('games-create-session', '/create-session/{slug}', action='create_session')
        m.connect('games-create-session', '/create-session/{slug}/{mode:[a-z\-]+}', action='create_session')
        m.connect('games-destroy-session', '/destroy-session', action='destroy_session')

    with router.submapper(controller="apiv1/badges", path_prefix='/api/v1/badges') as m:
        # Badges Public API
        m.connect('/read/{slug:[A-Za-z0-9\-]+}', action='badges_list')

        # Badges/Progress Developer API
        m.connect('/progress/add/{slug:[A-Za-z0-9\-]+}', action='badges_user_add')
        # userbadges/list: list all badges for the logged in user
        m.connect('/progress/read/{slug:[A-Za-z0-9\-]+}', action='badges_user_list')
        # Local API for testing only
        #m.connect('/progress/remove-all/{slug:[A-Za-z0-9\-]+}', action='remove_all')

    with router.submapper(controller="apiv1/datashare", path_prefix='/api/v1/data-share') as m:
        m.connect('/create/{slug:[A-Za-z0-9\-]+}', action='create')
        m.connect('/find/{slug:[A-Za-z0-9\-]+}', action='find')
        m.connect('/join/{slug:[A-Za-z0-9\-]+}/{datashare_id:[A-Za-z0-9]+}', action='join')
        m.connect('/leave/{slug:[A-Za-z0-9\-]+}/{datashare_id:[A-Za-z0-9]+}', action='leave')
        m.connect('/set-properties/{slug:[A-Za-z0-9\-]+}/{datashare_id:[A-Za-z0-9]+}', action='set_properties')
        # Secure API (requires gameSessionId)
        m.connect('/read/{datashare_id:[A-Za-z0-9]+}', action='read')
        m.connect('/read/{datashare_id:[A-Za-z0-9]+}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*}', action='read_key')
        m.connect('/set/{datashare_id:[A-Za-z0-9]+}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*}', action='set_key')
        m.connect('/compare-and-set/{datashare_id:[A-Za-z0-9]+}/{key:[A-Za-z0-9]+([\-\.][A-Za-z0-9]+)*}',
            action='compare_and_set_key')

        # Local API for testing only
        m.connect('/remove-all/{slug:[A-Za-z0-9\-]+}', action='remove_all')

    with router.submapper(controller="apiv1/profiles", path_prefix='/api/v1/profiles') as m:
        # Profiles
        m.connect("/user", action="user")
        #m.connect("/game/{slug:[A-Za-z0-9\-]+}", action="game")

    with router.submapper(controller='apiv1/gamenotifications', path_prefix='/api/v1/game-notifications') as m:
        m.connect('/usersettings/read/{slug:[A-Za-z0-9\-]+}', action='read_usersettings')
        m.connect('/usersettings/update/{slug:[A-Za-z0-9\-]+}', action='update_usersettings')

        m.connect('/keys/read/{slug:[A-Za-z0-9\-]+}', action='read_notification_keys')

        m.connect('/send-instant/{slug:[A-Za-z0-9\-]+}', action='send_instant_notification')
        m.connect('/send-delayed/{slug:[A-Za-z0-9\-]+}', action='send_delayed_notification')
        m.connect('/poll/{slug:[A-Za-z0-9\-]+}', action='poll_notifications')

        m.connect('/cancel-by-id/{slug:[A-Za-z0-9\-]+}', action='cancel_notification_by_id')
        m.connect('/cancel-by-key/{slug:[A-Za-z0-9\-]+}', action='cancel_notification_by_key')
        m.connect('/cancel-all/{slug:[A-Za-z0-9\-]+}', action='cancel_all_notifications')

        m.connect('/init-manager/{slug:[A-Za-z0-9\-]+}', action='init_manager')

    with router.submapper(controller="apiv1/multiplayer", path_prefix='/api/v1/multiplayer') as m:
        # Multiplayer public API
        with m.submapper(path_prefix='/session') as ms:
            ms.connect("/create/{slug:[A-Za-z0-9\-]+}", action="create")
            ms.connect("/join", action="join")
            ms.connect("/join-any/{slug:[A-Za-z0-9\-]+}", action="join_any")
            ms.connect("/leave", action="leave")
            ms.connect("/make-public", action="make_public")
            ms.connect("/list", action="list_all")
            ms.connect("/list/{slug:[A-Za-z0-9\-]+}", action="list")
            ms.connect("/read", action="read")

        # Multiplayer servers API
        with m.submapper(path_prefix='/server') as ms:
            ms.connect("/register", action="register")
            ms.connect("/heartbeat", action="heartbeat")
            ms.connect("/unregister", action="unregister")
            ms.connect("/leave", action="client_leave")
            ms.connect("/delete", action="delete_session")

    with router.submapper(controller="apiv1/custommetrics", path_prefix='/api/v1/custommetrics') as m:
        # Custom Metrics
        m.connect("/add-event/{slug:[A-Za-z0-9\-]+}", action="add_event")
        m.connect("/add-event-batch/{slug:[A-Za-z0-9\-]+}", action="add_event_batch")

    with router.submapper(controller="apiv1/store", path_prefix='/api/v1/store') as m:
        # Store Public API
        m.connect('/currency-list', action='get_currency_meta')
        m.connect('/items/read/{slug:[A-Za-z0-9\-]+}', action='read_meta')
        m.connect('/user/items/read/{slug:[A-Za-z0-9\-]+}', action='read_user_items')
        m.connect('/user/items/consume', action='consume_user_items')

        m.connect('/transactions/checkout', action='checkout_transaction')
        m.connect('/transactions/pay/{transaction_id:[A-Za-z0-9\-]+}', action='pay_transaction')
        m.connect('/transactions/read-status/{transaction_id:[A-Za-z0-9\-]+}', action='read_transaction_status')

        # Local API for testing only
        m.connect('/user/items/remove-all/{slug:[A-Za-z0-9\-]+}', action='remove_all')

    with router.submapper(controller="apiv1/servicestatus", path_prefix='/api/v1/service-status') as m:
        # Service status
        m.connect("/read", action="read_list")
        m.connect("/set/{service_name:[A-Za-z0-9\-]+}", action="set")
        m.connect("/poll-interval/set", action="set_poll_interval")

        m.connect("/game/read/{slug:[A-Za-z0-9\-]+}", action="read")


    return router


# pylint: enable=R0915
