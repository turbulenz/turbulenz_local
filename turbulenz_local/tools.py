# Copyright (c) 2010-2011,2013 Turbulenz Limited

import os
import re
import platform

from os.path import isabs, realpath, normpath, dirname, join, isdir, exists
from errno import EEXIST
from io import BytesIO
from gzip import GzipFile
from unicodedata import normalize
from logging import getLogger
from subprocess import Popen, PIPE

import simplejson as json

from pylons import config

LOG = getLogger(__name__)

_PUNCT_RE = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.:;+]+')

SYSNAME = platform.system()
MACHINE = platform.machine()


def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug. Could be a lot better."""
    result = []
    for word in _PUNCT_RE.split(unicode(text).lower()):
        word = normalize('NFKD', word).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))

def humanize_filesize(num):
    """
    Convert a file size to human-readable form.
    eg:  in = 2048, out = ('2', 'KB')
    """
    if num < 1024.0:
        return ('%3.0f' % num, 'B')
    for x in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return ('%3.1f' % num, x)
        num /= 1024.0

def get_absolute_path(directory):
    """
    Return absolute path by working out path relative to games root
    """
    if isabs(directory):
        return directory

    return realpath(normpath(join(config['games_root'], directory)))

def create_dir(directory):
    """
    Create the directory structure if necessary. return 'True' if it was created
    successfully and can be written into, 'False' otherwise.
    """
    if directory.strip() == '':
        return False
    else:
        absDir = get_absolute_path(directory)
        try:
            os.makedirs(absDir)
        except OSError as e:
            if e.errno != EEXIST:
                LOG.error('Failed creating meta dir: %s', str(e))
                return False
        return os.access(absDir, os.W_OK)

def load_json_asset(json_path):
    # Load mapping table
    try:
        json_handle = open(get_absolute_path(json_path))
        j = json.load(json_handle)
    except IOError as e:
        LOG.error(str(e))
    except ValueError as e:
        LOG.error(str(e))
    else:
        return j
    return None

def compress_file(file_path, compress_path):
    seven_zip = get_7zip_path()
    if seven_zip:
        process = Popen([seven_zip,
                        'a', '-tgzip',
                         #'-mx=9', '-mfb=257', '-mpass=15',
                         compress_path, file_path],
                        stdout=PIPE, stderr=PIPE)
        output, _ = process.communicate()
        retcode = process.poll()
        if retcode:
            LOG.error('Failed to compress file "%s" as "%s": %s', file_path, compress_path, str(output))
            return False
        else:
            return True
    else:
        cache_dir = dirname(compress_path)
        if not isdir(cache_dir):
            os.makedirs(cache_dir)
        try:
            with GzipFile(compress_path, mode='wb', compresslevel=9) as gzipfile:
                with open(file_path, 'rb') as f:
                    gzipfile.write(f.read())
        except IOError as e:
            LOG.error(str(e))
            return False
        LOG.warning('Using Python for GZip compression, install 7zip for optimal performance')
        return True

def get_compressed_file_data(file_path, compresslevel=5):
    compressed_buffer = BytesIO()

    gzip_file = GzipFile(mode='wb',
                         compresslevel=compresslevel,
                         fileobj=compressed_buffer)

    try:
        fileobj = open(file_path, 'rb')
        while True:
            x = fileobj.read(65536)
            if not x:
                break
            gzip_file.write(x)
            x = None
        fileobj.close()
    except IOError as e:
        LOG.error(str(e))
        return None

    gzip_file.close()

    compressed_data = compressed_buffer.getvalue()
    compressed_buffer.close()

    return compressed_data

def get_7zip_path():
    path_7zip = config.get('deploy.7zip_path', None)
    if path_7zip:
        return path_7zip

    sdk_root = normpath(dirname(__file__))
    while not isdir(normpath(join(sdk_root, 'external', '7-Zip'))):
        new_root = normpath(join(sdk_root, '..'))
        if new_root == sdk_root:
            return None
        sdk_root = new_root
        del new_root
    if SYSNAME == 'Linux':
        if MACHINE == 'x86_64':
            path_7zip = join(sdk_root, 'external/7-Zip/bin/linux64/7za')
        else:
            path_7zip = join(sdk_root, 'external/7-Zip/bin/linux32/7za')
    elif SYSNAME == 'Windows':
        path_7zip = join(sdk_root, 'external/7-Zip/bin/win/7za.exe')
    elif SYSNAME == 'Darwin':
        path_7zip = join(sdk_root, 'external/7-Zip/bin/macosx/7za')
    else:
        raise Exception('Unknown OS!')
    if exists(path_7zip):
        return path_7zip
    else:
        return None

def get_remote_addr(request, keep_forwarding_chain=False):
    forward_chain = request.headers.get('X-Forwarded-For')
    if forward_chain:
        if keep_forwarding_chain:
            return forward_chain
        else:
            forward_split = forward_chain.split(',', 1)
            return forward_split[0].strip()
    else:
        return request.environ['REMOTE_ADDR']
