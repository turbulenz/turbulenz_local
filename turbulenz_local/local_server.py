#!/usr/bin/env python
# Copyright (c) 2013 Turbulenz Limited

import argparse
import sys
import os.path
from htmllib import HTMLParser, HTMLParseError
from formatter import NullFormatter
from subprocess import call

try:
    # Depends on jsmin
    from turbulenz_tools.utils.htmlmin import HTMLMinifier
except ImportError:
    print 'Error - This script requires the turbulenz_tools package'
    exit(1)

from turbulenz_local.lib.compact import compact
from turbulenz_local import __version__ as local_version

TURBULENZ_LOCAL = os.path.dirname(__file__)
COMMON_INI = os.path.join(TURBULENZ_LOCAL, 'config', 'common.ini')
DEV_INI = os.path.join(TURBULENZ_LOCAL, 'config', 'development.ini')
RELEASE_INI = os.path.join(TURBULENZ_LOCAL, 'config', 'release.ini')
DEFAULT_GAMES = os.path.join(TURBULENZ_LOCAL, 'config', 'defaultgames.yaml')


#######################################################################################################################

#TODO: resolve these
from shutil import rmtree, copy, Error as ShError
import errno
import stat
import os

def echo(msg):
    print msg

def error(msg):
    echo('ERROR: %s' % msg)


# pylint: disable=C0103
def cp(src, dst, verbose=True):
    if verbose:
        echo('Copying: %s -> %s' % (os.path.basename(src), os.path.basename(dst)))
    try:
        copy(src, dst)
    except (ShError, IOError) as e:
        error(str(e))
# pylint: enable=C0103

# pylint: disable=C0103
def rm(filename, verbose=True):
    if verbose:
        echo('Removing: %s' % filename)
    try:
        os.remove(filename)
    except OSError as _:
        pass
# pylint: enable=C0103

def mkdir(path, verbose=True):
    if verbose:
        echo('Creating: %s' % path)
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise

def rmdir(path, verbose=True):
    def _handle_remove_readonly(func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
            func(path)
        else:
            raise

    if verbose:
        echo('Removing: %s' % path)
    try:
        rmtree(path, onerror=_handle_remove_readonly)
    except OSError:
        pass

#######################################################################################################################

def command_devserver_js(uglifyjs=None):
    uglifyjs = uglifyjs or 'external/uglifyjs/bin/uglifyjs'

    def compactor(dev_filename, rel_filename):
        # Use compactor to generate release version.
        echo('Compacting: %s -> %s' % (dev_filename, rel_filename))
        rc = call('node %s -o %s %s' % (uglifyjs, rel_filename, dev_filename), shell=True)
        if rc != 0:
            error('Failed to run uglifyjs, specify location with --uglifyjs')
            exit(1)

    versions_yaml = os.path.join(TURBULENZ_LOCAL, 'config', 'js_versions.yaml')
    dev_path = os.path.join(TURBULENZ_LOCAL, 'public', 'development')
    rel_path = os.path.join(TURBULENZ_LOCAL, 'public', 'release')
    ext = 'js'

    mkdir(os.path.join(rel_path, ext))

    try:
        compact(dev_path, rel_path, versions_yaml, ext, compactor)
    except IOError as e:
        error('Failed to save js version details: %s' % str(e))


def command_devserver_css(yuicompressor=None):
    yuicompressor = yuicompressor or 'external/yuicompressor/yuicompressor-2.4.2/yuicompressor-2.4.2.jar'

    def compactor(dev_filename, rel_filename):
        # Use compactor to generate release version.
        echo('Compacting: %s -> %s' % (dev_filename, rel_filename))
        rc = call('java -jar %s --type css -o %s %s' % (yuicompressor, rel_filename, dev_filename), shell=True)
        if rc != 0:
            error('Failed to run yuicompressor, specify location with --yuicompressor and check java')
            exit(1)

    versions_yaml = os.path.join(TURBULENZ_LOCAL, 'config', 'css_versions.yaml')
    dev_path = os.path.join(TURBULENZ_LOCAL, 'public', 'development')
    rel_path = os.path.join(TURBULENZ_LOCAL, 'public', 'release')
    ext = 'css'

    mkdir(os.path.join(rel_path, ext))

    try:
        compact(dev_path, rel_path, versions_yaml, ext, compactor, True)
    except IOError as e:
        error('Failed to save css version details: %s' % str(e))


def command_devserver_html():

    def compactor(dev_filename, rel_filename):
        # Use compactor to generate release version.
        echo('Compacting: %s -> %s' % (dev_filename, rel_filename))
        source_data = open(dev_filename, 'r').read()
        try:
            # Verify that the html file is correct
            htmlparser = HTMLParser(NullFormatter())
            htmlparser.feed(source_data)
            htmlparser.close()
            # Now try to minify
            output_file = open(rel_filename, 'wb')
            compactor = HTMLMinifier(output_file.write, True)
            compactor.feed(source_data)
            compactor.close()
            output_file.close()
        except HTMLParseError as e:
            error(str(e))
            exit(1)

    versions_yaml = os.path.join(TURBULENZ_LOCAL, 'config', 'html_versions.yaml')
    dev_path = os.path.join(TURBULENZ_LOCAL, 'public', 'development')
    rel_path = os.path.join(TURBULENZ_LOCAL, 'public', 'release')
    ext = 'html'

    mkdir(os.path.join(rel_path, ext))

    try:
        compact(dev_path, rel_path, versions_yaml, ext, compactor)
    except IOError as e:
        error('Failed to save html version details: %s' % str(e))

def init_devserver(devserver_folder):
    if not os.path.exists(devserver_folder):
        mkdir(devserver_folder)
    games_yaml_path = os.path.join(devserver_folder, 'games.yaml')
    common_ini_path = os.path.join(devserver_folder, 'common.ini')
    dev_ini_path = os.path.join(devserver_folder, 'development.ini')
    release_ini_path = os.path.join(devserver_folder, 'release.ini')

    # We always overwrite the common ini file, but keep silent if it was there already
    if not os.path.exists(common_ini_path):
        cp(COMMON_INI, common_ini_path)
    else:
        cp(COMMON_INI, common_ini_path, verbose=False)

    # Only copy config where it doesn't exist yet
    old_ini = None
    if not os.path.exists(games_yaml_path):
        cp(DEFAULT_GAMES, games_yaml_path)
    if not os.path.exists(dev_ini_path):
        cp(DEV_INI, dev_ini_path)
    else:
        old_ini = dev_ini_path
    if not os.path.exists(release_ini_path):
        cp(RELEASE_INI, release_ini_path)
    else:
        old_ini = release_ini_path

    # If there were existing ini files check for the old format, if so overwrite both ini's
    if old_ini:
        f = open(old_ini, 'r')
        old_conf = f.read()
        f.close()
        if old_conf.find('config:common.ini') == -1:
            echo('WARNING: Overwriting legacy format development and release ini files. Existing files renamed to .bak')
            cp(dev_ini_path, '%s.bak' % dev_ini_path)
            cp(release_ini_path, '%s.bak' % release_ini_path)
            cp(DEV_INI, dev_ini_path)
            cp(RELEASE_INI, release_ini_path)

def command_devserver(args):
    # Devserver requires release Javascript and CSS
    if args.compile:
        command_devserver_js(args.uglifyjs)
        command_devserver_css(args.yuicompressor)
        command_devserver_html()

    if args.development:
        start_cmd = 'paster serve --reload development.ini'
    else:
        start_cmd = 'paster serve --reload release.ini'
    if args.options:
        start_cmd = '%s %s' % (start_cmd, args.options)
    try:
        call(start_cmd, cwd=args.home, shell=True)
    # We catch this incase we want to close the devserver
    except KeyboardInterrupt:
        pass

def command_devserver_clean(devserver_folder):
    rmdir('%s/public/release/js' % TURBULENZ_LOCAL)
    rm('%s/config/js_versions.yaml' % TURBULENZ_LOCAL)
    rmdir('%s/public/release/css' % TURBULENZ_LOCAL)
    rm('%s/config/css_versions.yaml' % TURBULENZ_LOCAL)
    rmdir('%s/public/release/html' % TURBULENZ_LOCAL)
    rm('%s/config/html_versions.yaml' % TURBULENZ_LOCAL)
    rmdir('%s/public/release' % TURBULENZ_LOCAL)

def main():
    parser = argparse.ArgumentParser(description="Manages the turbulenz local development server.")
    parser.add_argument('--launch', action='store_true', help="Launch the local development server")
    parser.add_argument('--development', action='store_true', help="Run the local development server in dev mode")
    parser.add_argument('--compile', action='store_true', help="Compile development scripts for release mode")
    parser.add_argument('--clean', action='store_true', help="Clean built development scripts")
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--uglifyjs', help="Set the path to uglifyjs")
    parser.add_argument('--yuicompressor', help="Set the path to yuicompressor jar")
    parser.add_argument('--init', action='store_true', help="Initialize the local server folder with default settings")
    parser.add_argument('--options', help="Additional options to pass to the local development server")
    parser.add_argument('--home', default='devserver', help="Set the home folder for the local development server")

    args = parser.parse_args(sys.argv[1:])

    if args.version:
        print local_version
        exit(0)

    if not (args.init or args.launch or args.clean or args.compile):
        parser.print_help()
        exit(0)

    if args.init:
        init_devserver(args.home)

    if args.launch:
        command_devserver(args)
        exit(0)

    if args.clean:
        command_devserver_clean(args.home)

    if args.compile:
        command_devserver_js(args.uglifyjs)
        command_devserver_css(args.yuicompressor)
        command_devserver_html()


if __name__ == "__main__":
    exit(main())
