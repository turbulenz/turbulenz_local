#!/usr/bin/env python
# Copyright (c) 2011-2013 Turbulenz Limited

import logging
import locale
import mimetypes

from os.path import exists as path_exists, dirname as path_dirname, basename as path_basename, abspath as path_abspath
from optparse import OptionParser, TitledHelpFormatter
from urllib3 import connection_from_url
from urllib3.exceptions import HTTPError, SSLError
from simplejson import loads as json_loads
from threading import Thread
from time import sleep, time
from re import compile as re_compile
from sys import stdin, stdout
from getpass import getpass, GetPassWarning
from math import modf

from turbulenz_local.models.game import Game, GameError
from turbulenz_local.lib.deploy import Deployment


__version__ = '1.0.3'


HUB_COOKIE_NAME = 'hub'
HUB_URL = 'https://hub.turbulenz.com/'

# pylint: disable=C0301
USERNAME_PATTERN = re_compile('^[a-z0-9]+[a-z0-9-]*$') # usernames
PROJECT_SLUG_PATTERN = re_compile('^[a-zA-Z0-9\-]*$') # game and versions
PROJECT_VERSION_PATTERN = re_compile('^[a-zA-Z0-9\-\.]*$') # game and versions
# pylint: enable=C0301


def log(message, new_line=True):
    message = message.encode(stdout.encoding or 'UTF-8', 'ignore')
    print ' >> %s' % message,
    if new_line:
        print

def error(message):
    log('[ERROR]   - %s' % message)

def warning(message):
    log('[WARNING] - %s' % message)


def _add_missing_mime_types():
    mimetypes.add_type('application/vnd.turbulenz', '.tzjs')
    mimetypes.add_type('application/json', '.json')
    mimetypes.add_type('image/dds', '.dds')
    mimetypes.add_type('image/tga', '.tga')
    mimetypes.add_type('image/ktx', '.ktx')
    mimetypes.add_type('image/x-icon', '.ico')
    mimetypes.add_type('text/cgfx', '.cgfx')
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('application/ogg', '.ogg')
    mimetypes.add_type('image/png', '.png')
    mimetypes.add_type('text/x-yaml', '.yaml')


def _create_parser():
    parser = OptionParser(description='Deploy game from Local to the Hub',
                          formatter=TitledHelpFormatter())

    parser.add_option("--version", action="store_true", dest="output_version", default=False,
                      help="output version number")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="verbose output")
    parser.add_option("-s", "--silent", action="store_true", dest="silent", default=False, help="silent running")

    parser.add_option("-i", "--input", action="store", dest="input", help="manifest file for the game to be deployed")

    parser.add_option("-u", "--user", action="store", dest="user", help="login username")
    parser.add_option("-p", "--password", action="store", dest="password",
                      help="login password (will be requested if not provided)")

    parser.add_option("--project", action="store", dest="project", help="project to deploy to")
    parser.add_option("--projectversion", action="store", dest="projectversion", help="project version to deploy to")
    parser.add_option("--projectversiontitle", action="store", dest="projectversiontitle",
                      help="project version title, for existing project versions this will overwrite the existing " \
                           "title if supplied. For new versions this defaults to the project version")

    parser.add_option("-c", "--cache", action="store", dest="cache", help="folder to be used for caching")

    parser.add_option("--hub", action="store", dest="hub", default=HUB_URL,
                      help="Hub url (defaults to https://hub.turbulenz.com/)")

    parser.add_option("--ultra", action="store_true", dest="ultra", default=False,
                      help="use maximum compression. Will take MUCH longer. May reduce file size by an extra 10%-20%.")

    return parser


def _check_options():

    parser = _create_parser()
    (options, _args) = parser.parse_args()

    if options.output_version:
        print __version__
        exit(0)

    if options.silent:
        logging.basicConfig(level=logging.CRITICAL)
    elif options.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    manifest_file = options.input
    if not manifest_file:
        error('No manifest file specified!')
        #parser.print_help()
        exit(-1)

    if not path_exists(manifest_file):
        error('Expecting an existing manifest file, "%s" does not exist!' % manifest_file)
        #parser.print_help()
        exit(-1)

    cache_folder = options.cache
    if not cache_folder:
        error('Expecting a cache folder!')
        parser.print_help()
        exit(-1)

    if not path_exists(cache_folder):
        error('Expecting an existing cache folder, "%s" does not exist!' % cache_folder)
        exit(-1)

    username = options.user
    if not username:
        error('Login information required!')
        parser.print_help()
        exit(-1)

    if not options.password:
        try:
            options.password = getpass()
        except GetPassWarning:
            error('Echo free password entry unsupported. Please provide a --password argument')
            parser.print_help()
            return -1

    if not USERNAME_PATTERN.match(username):
        error('Incorrect "username" format!')
        exit(-1)

    project = options.project
    if not project:
        error('Hub project required!')
        parser.print_help()
        exit(-1)

    if not PROJECT_SLUG_PATTERN.match(project):
        error('Incorrect "project" format!')
        exit(-1)

    projectversion = options.projectversion
    if not projectversion:
        error('Hub project version required!')
        parser.print_help()
        exit(-1)

    if not PROJECT_VERSION_PATTERN.match(projectversion):
        error('Incorrect "projectversion" format!')
        exit(-1)


    if options.projectversiontitle is not None:
        options.projectversiontitle = options.projectversiontitle.decode('UTF-8')
        if len(options.projectversiontitle) > 48:
            error('"projectversiontitle" too long (max length 48 characters)!')
            exit(-1)


    if options.hub is None:
        options.hub = 'http://127.0.0.1:8080'

    return options


def login(connection, options):
    username = options.user
    password = options.password

    if not options.silent:
        log('Login as "%s".' % username)

    credentials = {'login': username,
                   'password': password,
                   'source': '/tool'}

    try:
        r = connection.request('POST',
                               '/dynamic/login',
                               fields=credentials,
                               retries=1,
                               redirect=False)
    except (HTTPError, SSLError):
        error('Connection to Hub failed!')
        exit(-1)

    if r.status != 200:
        if r.status == 301:
            redirect_location = r.headers.get('location', '')
            end_domain = redirect_location.find('/dynamic/login')
            error('Login is being redirected to "%s". Please verify the Hub URL.' % redirect_location[:end_domain])
        else:
            error('Wrong user login information!')
        exit(-1)

    cookie = r.headers.get('set-cookie', None)
    login_info = json_loads(r.data)

    # pylint: disable=E1103
    if not cookie or HUB_COOKIE_NAME not in cookie or login_info.get('source') != credentials['source']:
        error('Hub login failed!')
        exit(-1)
    # pylint: enable=E1103

    return cookie


def logout(connection, cookie):
    try:
        connection.request('POST',
                           '/dynamic/logout',
                           headers={'Cookie': cookie},
                           redirect=False)
    except (HTTPError, SSLError) as e:
        error(str(e))


def _check_project(connection, options, cookie):
    project = options.project
    projectversion = options.projectversion
    projectversion_title = options.projectversiontitle

    try:
        r = connection.request('POST',
                               '/dynamic/upload/projects',
                               headers={'Cookie': cookie},
                               redirect=False)
    except (HTTPError, SSLError) as e:
        error(e)
        exit(-1)

    if r.status != 200:
        error('Wrong Hub answer!')
        exit(-1)

    # pylint: disable=E1103
    projects = json_loads(r.data).get('projects', [])
    # pylint: enable=E1103

    upload_access = False
    new_version = True
    for project_info in projects:
        if project_info['slug'] == project:
            upload_access = True
            for version_info in project_info['versions']:
                if version_info['version'] == projectversion:
                    new_version = False
                    # Use the supplied project version title or the existing one as a fallback
                    existingversion_title = version_info['title']
                    projectversion_title = projectversion_title or existingversion_title
                    break

    # If projectversion_title is still unset this is a new version with no supplied title, default to the version
    projectversion_title = projectversion_title or projectversion

    if not upload_access:
        error('Project "%s" does not exist or you are not authorized to upload new versions!' % project)
        exit(-1)

    if not options.silent:
        if new_version:
            log('Uploading to new version "%s" on project "%s".' % (projectversion, project))
        else:
            log('Uploading to existing version "%s" on project "%s".' % (projectversion, project))
            if projectversion_title != existingversion_title:
                log('Changing project version title from "%s" to "%s".' % (existingversion_title,
                                                                           projectversion_title))

    return (project, projectversion, projectversion_title)


def _get_cookie_value(cookie):
    for cookie_pair in cookie.split(';'):
        if HUB_COOKIE_NAME in cookie_pair:
            return cookie_pair

    error('Wrong cookie: %s' % cookie)
    exit(-1)


def _fmt_value(value):
    return locale.format('%lu', value, grouping=True)


def _fmt_time(seconds):
    hours = 0
    minutes = 0
    milliseconds, seconds = modf(seconds)
    milliseconds = int(milliseconds * 1000)
    if seconds > 3600:
        hours = int(seconds / 3600)
        seconds -= (hours * 3600)
    if seconds > 60:
        minutes = int(seconds / 60)
        seconds -= (minutes * 60)
    return '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, milliseconds)


def _check_game(game):
    def log_issues(issues):
        for key, items in issues.iteritems():
            log('Issues in %s:' % key)
            for item in items:
                log('- %s:' % item[0])
                for value in item[1].get('errors', []):
                    error(value)
                for value in item[1].get('warnings', []):
                    warning(value)

    complete, issues = game.check_completeness()
    if not complete:
        log_issues(issues)
        exit(-1)

    issues, critical = game.validate_yaml()
    if issues:
        log_issues(issues)
        if critical:
            exit(-1)

        log('If you still want to deploy, the missing values will be replaced by default ones.')
        log('Deploy? (Y/N) ', False)
        if stdin.readline().strip()[0] not in 'yY':
            exit(-1)

def _progress(deploy_info, silent, verbose):
    if silent:
        sleep_step = 1.0
    elif verbose:
        log('Scanning and compressing:')
        sleep_step = 0.2
    else:
        log('Scanning and compressing files...')
        sleep_step = 0.4

    old_num_bytes = 0
    old_uploaded_bytes = 0

    while True:
        sleep(sleep_step)

        if deploy_info.error:
            error(deploy_info.error)
            return -1

        if not silent:
            current_num_bytes = deploy_info.num_bytes
            current_uploaded_bytes = deploy_info.uploaded_bytes

            if old_num_bytes != current_num_bytes or old_uploaded_bytes != current_uploaded_bytes:
                if verbose:
                    total_files = deploy_info.total_files
                    if current_uploaded_bytes == 0:
                        log('    %u/%u (%s bytes)' % (deploy_info.num_files,
                                                      total_files,
                                                      _fmt_value(current_num_bytes)))
                    else:
                        if old_uploaded_bytes == 0:
                            if old_num_bytes < current_num_bytes:
                                log('    %u/%u (%s bytes)' % (deploy_info.num_files,
                                                              total_files,
                                                              _fmt_value(current_num_bytes)))
                            log('Uploading modified files:')
                        log('    %u/%u (%s/%s)' % (deploy_info.uploaded_files,
                                                   deploy_info.num_files,
                                                   _fmt_value(current_uploaded_bytes),
                                                   _fmt_value(current_num_bytes)))
                else:
                    if current_uploaded_bytes != 0 and old_uploaded_bytes == 0:
                        log('Uploading modified files...')

                if deploy_info.num_files > 1000:
                    sleep_step = 1.0

                old_num_bytes = current_num_bytes
                old_uploaded_bytes = current_uploaded_bytes

        if deploy_info.done:
            if not silent:
                if verbose:
                    log('Done uploading.')
                else:
                    log('Done uploading: %u files (%s bytes)' % (deploy_info.num_files,
                                                                 _fmt_value(current_num_bytes)))
            break
    return 0

def _postupload_progress(deploy_info, connection, cookie, silent, verbose):
    if silent:
        sleep_step = 1.0
    elif verbose:
        log('Post processing:')
        sleep_step = 0.2
    else:
        log('Post processing files...')
        sleep_step = 0.4

    if not deploy_info.hub_session:
        error('No deploy session found.')
        return -1

    old_progress = 0

    while True:
        sleep(sleep_step)

        if deploy_info.error:
            error(deploy_info.error)
            return -1

        try:
            r = connection.request('POST',
                                   '/dynamic/upload/progress/%s' % deploy_info.hub_session,
                                   headers={'Cookie': cookie},
                                   redirect=False)
        except (HTTPError, SSLError) as e:
            error(e)
            error('Post-upload progress check failed.')
            return -1

        if r.status != 200:
            error('Wrong Hub answer.')
            return -1

        r_data = json_loads(r.data)
        # pylint: disable=E1103
        current_progress = int(r_data.get('progress', -1))
        error_msg = str(r_data.get('error', ''))
        # pylint: enable=E1103

        if error_msg:
            error('Post-upload processing failed: %s' % error_msg)
            return -1
        if -1 == current_progress:
            error('Invalid post-upload progress.')
            return -1

        if verbose and not silent:
            if old_progress != current_progress:
                log('Progress: %u%%' % current_progress)
            old_progress = current_progress

        if 100 <= current_progress:
            if not silent:
                log('Post processing completed.')
            return 0

def main():
    # pylint: disable=E1103

    options = _check_options()

    locale.setlocale(locale.LC_ALL, '')

    verbose = options.verbose

    if verbose:
        logging.disable(logging.INFO)
    else:
        logging.disable(logging.WARNING)

    _add_missing_mime_types()

    try:
        game = Game(game_list=None,
                    game_path=path_abspath(path_dirname(options.input)),
                    slug=None,
                    games_root=options.cache,
                    deploy_enable=True,
                    manifest_name=path_basename(options.input))

        _check_game(game)

        silent = options.silent
        if not silent:
            log('Deploying "%s" to "%s".' % (game.slug, options.hub))

        connection = connection_from_url(options.hub, maxsize=8, timeout=8.0)

        cookie = login(connection, options)

        (project, projectversion, projectversion_title) = _check_project(connection, options, cookie)

        result = 0

        deploy_info = None
        deploy_thread = None

        try:
            deploy_info = Deployment(game,
                                     connection,
                                     project,
                                     projectversion,
                                     projectversion_title,
                                     _get_cookie_value(cookie),
                                     options.cache)

            deploy_thread = Thread(target=deploy_info.deploy, args=[options.ultra])
            deploy_thread.start()

            start_time = time()

            result = _progress(deploy_info, silent, verbose)
            if (0 == result):
                result = _postupload_progress(deploy_info, connection, cookie, silent, verbose)
                if (0 == result):
                    if not silent:
                        log('Deployment time: %s' % _fmt_time((time() - start_time)))
                    game.set_deployed()

        except KeyboardInterrupt:
            warning('Program stopped by user!')
            if deploy_info:
                deploy_info.cancel()
            result = -1

        except Exception as e:
            error(str(e))
            if deploy_info:
                deploy_info.cancel()
            result = -1

        if deploy_info:
            del deploy_info

        if deploy_thread:
            del deploy_thread

        logout(connection, cookie)

        return result

    except GameError:
        return -1

    #except Exception as e:
    #    error(str(e))
    #    return -1

if __name__ == "__main__":
    exit(main())
