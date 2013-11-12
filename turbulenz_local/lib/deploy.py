# Copyright (c) 2010-2013 Turbulenz Limited
"""
Controller class for deploying a game
"""
from urllib3.exceptions import HTTPError, SSLError
from simplejson import dump as json_dump, load as json_load, loads as json_loads, JSONDecodeError

from os import stat, sep, error, rename, remove, makedirs, utime, access, R_OK, walk
from os.path import join, basename, abspath, splitext, sep, isdir, dirname
from errno import EEXIST
from stat import S_ISREG
from glob import iglob
from logging import getLogger
from mimetypes import guess_type
from gzip import GzipFile
from shutil import rmtree
from Queue import Queue
from threading import Thread
from time import time
from subprocess import Popen, PIPE

# pylint: disable=F0401
from poster.encode import gen_boundary, get_headers, MultipartParam
# pylint: enable=F0401

from turbulenz_local.tools import get_absolute_path, get_7zip_path
from turbulenz_tools.utils.hash import hash_file_sha256_md5, hash_file_sha256, hash_file_md5
from turbulenz_local import __version__


LOG = getLogger(__name__)


def _update_file_mtime(file_path, mtime):
    # We round mtime up to the next second to avoid precision problems with floating point values
    mtime = long(mtime) + 1
    utime(file_path, (mtime, mtime))

def _get_upload_file_token(index, filename):
    # We build the upload token using an index and the file extension since the hub doesn't care
    # about the actual filename only the extension
    return '%d%s' % (index, splitext(filename)[1])

def _get_cached_file_name(file_name, file_hash, file_length):
    return '%s%x%s' % (file_hash, file_length, splitext(file_name)[1])


# pylint: disable=R0902
class Deployment(object):

    _batch_checks = True

    _empty_meta_data = {'length': 0,
                        'hash': '',
                        'md5': ''}

    _base_check_url = '/dynamic/upload/check?'
    _check_url_format = 'name=%s&hash=%s&length=%d'

    _cached_hash_folder = '__cached_hashes__'
    _cached_hash_ttl = (30 * 24 * 60 * 60) # 30 days

    _do_not_compress = set([ 'ogg',
                             'png',
                             'jpeg',
                             'jpg',
                             'gif',
                             'ico',
                             'mp3',
                             'wav',
                             'swf',
                             'webm',
                             'mp4' ])

    _directories_to_ignore = set([ '.git',
                                   '.hg',
                                   '.svn' ])

    def __init__(self, game, hub_pool, hub_project, hub_version, hub_versiontitle, hub_cookie, cache_dir):
        self.path = abspath(get_absolute_path(game.path))
        self.plugin_main = game.plugin_main
        self.canvas_main = game.canvas_main
        self.flash_main = game.flash_main
        self.mapping_table = game.mapping_table
        self.files = game.deploy_files.items
        self.engine_version = game.engine_version
        self.is_multiplayer = game.is_multiplayer
        self.aspect_ratio = game.aspect_ratio

        self.cache_dir = cache_dir
        self.game_cache_dir = join(abspath(cache_dir), game.slug)

        self.stopped = False
        self.hub_project = hub_project
        self.hub_version = hub_version
        self.hub_versiontitle = hub_versiontitle
        self.hub_session = None
        self.hub_pool = hub_pool
        self.hub_cookie = hub_cookie
        self.hub_timeout = 200
        self.total_files = 0
        self.num_files = 0
        self.num_bytes = 0
        self.uploaded_files = 0
        self.uploaded_bytes = 0
        self.done = False
        self.error = None

        try:
            makedirs(self.get_gzip_dir())
        except OSError as e:
            if e.errno != EEXIST:
                LOG.error(str(e))

    def get_meta_data_path(self):
        return self.game_cache_dir + '.json.gz'

    def get_gzip_dir(self):
        return self.game_cache_dir.replace('\\', '/')

    def deploy(self, ultra=False):
        self.done = self.upload_files(ultra)

        if self.hub_session:
            headers = {'Cookie': self.hub_cookie}
            fields = {'session': self.hub_session}

            try:
                if self.done:
                    self.hub_pool.request('POST',
                                          '/dynamic/upload/end',
                                           fields=fields,
                                           headers=headers,
                                           redirect=False,
                                           retries=5,
                                           timeout=self.hub_timeout)
                else:
                    self.hub_pool.request('POST',
                                          '/dynamic/upload/cancel',
                                           fields=fields,
                                           headers=headers,
                                           redirect=False,
                                           retries=5,
                                           timeout=self.hub_timeout)
            except (HTTPError, SSLError) as e:
                LOG.error(e)

    def cancel(self):
        self.stopped = True
        self.error = 'Canceled.'

    def stop(self, error_msg):
        self.stopped = True
        self.error = error_msg

    def read_metadata_cache(self):
        try:
            file_name = self.get_meta_data_path()
            gzip_file = GzipFile(filename=file_name,
                                 mode='rb')
            meta_data_cache = json_load(gzip_file)
            gzip_file.close()
            cache_time = stat(file_name).st_mtime
        except IOError:
            cache_time = -1
            meta_data_cache = {}
        return cache_time, meta_data_cache

    def write_metadata_cache(self, meta_data, force_mtime):
        try:
            file_path = self.get_meta_data_path()

            gzip_file = GzipFile(filename=file_path,
                                 mode='wb',
                                 compresslevel=9)
            json_dump(meta_data, gzip_file, separators=(',', ':'), sort_keys=True)
            gzip_file.close()

            if force_mtime > 0:
                _update_file_mtime(file_path, force_mtime)

        except (IOError, OSError):
            pass

    def delete_unused_cache_files(self, meta_data, meta_data_cache):
        old_files_to_delete = (set(meta_data_cache.iterkeys()) - set(meta_data.iterkeys()))
        if old_files_to_delete:
            gzip_cache_dir = self.get_gzip_dir()
            for relative_path in old_files_to_delete:
                cache_file_name = '%s/%s.gz' % (gzip_cache_dir, relative_path)
                if access(cache_file_name, R_OK):
                    remove(cache_file_name)

    def batch_check_files(self, files, checked_queue_put):
        urlopen = self.hub_pool.urlopen
        base_url = self._base_check_url
        url_format = self._check_url_format
        get_upload_token = _get_upload_file_token
        timeout = self.hub_timeout
        if self._batch_checks:
            query = '&'.join((url_format % (get_upload_token(i, f[1]), f[3], f[2])) for i, f in enumerate(files))
            r = urlopen('GET',
                        base_url + query,
                        redirect=False,
                        assert_same_host=False,
                        timeout=timeout)
            if r.status == 200:
                # pylint: disable=E1103
                missing_files = set(json_loads(r.data).get('missing', []))
                # pylint: enable=E1103
                for i, f in enumerate(files):
                    if get_upload_token(i, f[1]) in missing_files:
                        # Update meta data cache and upload
                        checked_queue_put(f)
                    else:
                        # Only needs to update meta data cache
                        checked_queue_put((f[1], f[2], f[3], f[4], f[5]))
                return

            else:
                f = files.pop(0)
                if r.status == 304:
                    # First one only needs to update meta data cache
                    checked_queue_put((f[1], f[2], f[3], f[4], f[5]))
                elif r.status == 404:
                    # First one needs to update meta data cache and to upload
                    checked_queue_put(f)
                else:
                    raise Exception(r.reason)
                if len(files) == 1:
                    return
                # Legacy format, check one by one...
                self._batch_checks = False
                r = None

        for f in files:
            query = url_format % (basename(f[1]), f[3], f[2])
            if urlopen('GET',
                       base_url + query,
                       redirect=False,
                       assert_same_host=False,
                       timeout=timeout).status == 304:
                # Only needs to update meta data cache
                checked_queue_put((f[1], f[2], f[3], f[4], f[5]))
            else:
                # Update meta data cache and upload
                checked_queue_put(f)


    # pylint: disable=R0914
    def check_files(self, files, start, end, checked_queue_put, hashes, ultra, cache_time, meta_data_cache):
        files_to_batch_check = []
        base_path_len = len(self.path)
        if not self.path.endswith(sep):
            base_path_len += 1
        gzip_cache_dir = self.get_gzip_dir()
        compressor_path = get_7zip_path()
        empty_meta_data = self._empty_meta_data
        get_cached_file_name = _get_cached_file_name

        while start < end:
            if self.stopped:
                checked_queue_put(None) # Make sure the waiting thread wakes up
                break

            abs_path = files[start]
            start += 1

            relative_path = abs_path[base_path_len:]

            try:
                file_stat = stat(abs_path)

                file_size = file_stat.st_size

                if not S_ISREG(file_stat.st_mode) or file_size <= 0: # Not a valid file
                    checked_queue_put(relative_path)
                    continue

                calculate_hash = update_meta_data = False
                file_time = max(file_stat.st_mtime, file_stat.st_ctime)
                if cache_time < file_time:
                    calculate_hash = True
                else:
                    old_meta_data = meta_data_cache.get(relative_path, empty_meta_data)
                    if file_size != old_meta_data['length']:
                        calculate_hash = True
                    else:
                        file_hash = old_meta_data['hash']
                        file_md5 = old_meta_data['md5']

                # Avoid compressing some files because they either already use 'deflate' or
                # because the browser needs them uncompressed
                if relative_path.split('.')[-1] not in self._do_not_compress:
                    deploy_file_name = '%s/%s.gz' % (gzip_cache_dir, relative_path)
                    do_compress = False
                    try:
                        file_stat = stat(deploy_file_name)
                        if file_stat.st_mtime < file_time:
                            do_compress = True
                        elif file_stat.st_size >= file_size:
                            deploy_file_name = abs_path
                    except error:
                        do_compress = True
                    if do_compress:
                        if compressor_path:
                            if ultra:
                                process = Popen([compressor_path,
                                                 'a', '-tgzip',
                                                 '-mx=9', '-mfb=257', '-mpass=15',
                                                 deploy_file_name, abs_path],
                                                stdout=PIPE, stderr=PIPE)
                            else:
                                process = Popen([compressor_path,
                                                 'a', '-tgzip',
                                                 deploy_file_name, abs_path],
                                                stdout=PIPE, stderr=PIPE)
                            update_meta_data = True

                            if calculate_hash:
                                calculate_hash = False
                                file_hash = hash_file_sha256(abs_path)
                            output, _ = process.communicate()
                            if process.poll():
                                self.stop('Error compressing file "%s": "%s".' % (relative_path, str(output)))
                                continue
                            else:
                                try:
                                    if stat(deploy_file_name).st_size >= file_size:
                                        deploy_file_name = abs_path
                                except error as e:
                                    self.stop('Error opening compressed file "%s": "%s".' % (deploy_file_name, str(e)))
                                    continue
                                file_md5 = hash_file_md5(deploy_file_name)
                        else:
                            # Compress with Python gzip, will warn that 7zip is preferred
                            cache_dir = dirname(deploy_file_name)
                            try:
                                makedirs(cache_dir)
                            except OSError as e:
                                if e.errno != EEXIST:
                                    self.stop('Error compressing file "%s": "%s".' % (relative_path, str(e)))
                                    continue
                            try:
                                with GzipFile(deploy_file_name, mode='wb', compresslevel=9) as gzipfile:
                                    with open(abs_path, 'rb') as f:
                                        gzipfile.write(f.read())
                            except IOError as e:
                                self.stop('Error compressing file "%s": "%s".' % (relative_path, str(e)))
                                continue
                            LOG.warning('Using Python for GZip compression, install 7zip for optimal performance')
                            update_meta_data = True
                            if calculate_hash:
                                calculate_hash = False
                                file_hash = hash_file_sha256(abs_path)
                            try:
                                if stat(deploy_file_name).st_size >= file_size:
                                    deploy_file_name = abs_path
                            except error as e:
                                self.stop('Error opening compressed file "%s": "%s".' % (deploy_file_name, str(e)))
                                continue
                            file_md5 = hash_file_md5(deploy_file_name)
                else:
                    deploy_file_name = abs_path

                if calculate_hash:
                    update_meta_data = True
                    if deploy_file_name == abs_path:
                        file_hash, file_md5 = hash_file_sha256_md5(abs_path)
                    else:
                        file_hash = hash_file_sha256(abs_path)
                        file_md5 = hash_file_md5(deploy_file_name)

                if get_cached_file_name(relative_path, file_hash, file_size) not in hashes:
                    file_item = (deploy_file_name, relative_path, file_size, file_hash, file_md5, file_time)
                    files_to_batch_check.append(file_item)
                    if len(files_to_batch_check) >= 10:
                        self.batch_check_files(files_to_batch_check, checked_queue_put)
                        files_to_batch_check = []

                elif update_meta_data:
                    checked_queue_put((relative_path, file_size, file_hash, file_md5, file_time))
                else:
                    checked_queue_put((relative_path, file_size, file_hash, file_time)) # Nothing to do

                file_stat = None

            except (error, IOError) as e:
                self.stop('Error opening file "%s": "%s".' % (relative_path, str(e)))
            except Exception as e:
                self.stop('Error checking file "%s": "%s".' % (relative_path, str(e)))

        if len(files_to_batch_check) > 0:
            try:
                self.batch_check_files(files_to_batch_check, checked_queue_put)
            except (HTTPError, SSLError, ValueError) as e:
                self.stop('Error checking files: "%s".' % str(e))
            except Exception as e:
                self.stop('Error checking files: "%s".' % str(e))
    # pylint: enable=R0914

    def find_files(self):
        files = set()
        path = self.path
        directories_to_ignore = self._directories_to_ignore
        for pattern in self.files:
            if pattern:
                for abs_path in iglob(join(path, pattern)):

                    if isdir(abs_path):
                        for tmp_root, dir_names, list_of_files in walk(abs_path):
                            if dir_names:
                                # Filter subdirectories by updating the given list inplace
                                dir_names[:] = (dirname for dirname in dir_names
                                                if dirname not in directories_to_ignore)
                            # Fix filenames and add them to the set
                            files.update(join(tmp_root, filename).replace('\\', '/') for filename in list_of_files)
                    else:
                        files.add(abs_path.replace('\\', '/'))
        return list(files)

    def load_hashes(self, project):
        hashes = set()

        try:
            # Files containing cached hashes are stored in a folder called "__cached_hashes__".
            # The name of the file contains the creation time
            # so we skip files that are too old
            hashes_folder = join(self.cache_dir, self._cached_hash_folder)

            stale_time = long(time() - self._cached_hash_ttl) # 30 days

            for file_path in iglob(join(hashes_folder, '*.json')):
                delete_file = True

                try:
                    file_time = long(splitext(basename(file_path))[0])
                    if stale_time < file_time:
                        file_obj = open(file_path, 'rb')
                        hashes_meta = json_load(file_obj)
                        file_obj.close()
                        # pylint: disable=E1103
                        hashes_version = hashes_meta.get('version', 0)
                        if 2 <= hashes_version:
                            cached_hashes = hashes_meta.get('hashes', None)
                            if cached_hashes:
                                delete_file = False
                                hashes_host = hashes_meta.get('host', None)
                                if hashes_host == self.hub_pool.host:
                                    hashes.update(cached_hashes)
                        # pylint: enable=E1103
                except (TypeError, ValueError):
                    pass

                if delete_file:
                    LOG.info('Deleting stale cache file: %s', file_path)
                    remove(file_path)

        except (IOError, error):
            pass
        except Exception as e:
            LOG.error(str(e))

        hashes.update(self.request_hashes(project))

        return hashes

    def request_hashes(self, project):
        try:
            min_version = 2
            r = self.hub_pool.urlopen('GET',
                                      '/dynamic/upload/list?version=%d&project=%s' % (min_version, project),
                                      headers={'Cookie': self.hub_cookie,
                                               'Accept-Encoding': 'gzip'},
                                      redirect=False,
                                      assert_same_host=False,
                                      timeout=self.hub_timeout)
            if r.status == 200:
                response = json_loads(r.data)
                # pylint: disable=E1103
                if response.get('version', 1) >= min_version:
                    return response['hashes']
                # pylint: enable=E1103

        except (HTTPError, SSLError, TypeError, ValueError):
            pass
        except Exception as e:
            LOG.error(str(e))
        return []

    def save_hashes(self, hashes):
        try:
            hashes_folder = join(self.cache_dir, self._cached_hash_folder)
            try:
                makedirs(hashes_folder)
            except OSError as e:
                if e.errno != EEXIST:
                    LOG.error(str(e))
                    return

            # Load existing cache and only save the delta
            for file_path in iglob(join(hashes_folder, '*.json')):
                try:
                    file_obj = open(file_path, 'rb')
                    hashes_meta = json_load(file_obj)
                    file_obj.close()
                    hashes_host = hashes_meta['host']
                    if hashes_host == self.hub_pool.host:
                        hashes.difference_update(hashes_meta['hashes'])
                except (IOError, TypeError, ValueError, KeyError, AttributeError):
                    pass

            if hashes:
                try:
                    file_path = join(hashes_folder, '%d.json' % long(time()))
                    file_obj = open(file_path, 'wb')
                    hashes_meta = {'version': 2,
                                   'host': self.hub_pool.host,
                                   'hashes': list(hashes)}
                    json_dump(hashes_meta, file_obj, separators=(',', ':'))
                    file_obj.close()
                except IOError:
                    pass

        # pylint: disable=W0703
        except Exception as e:
            LOG.error(str(e))
        # pylint: enable=W0703

    def start_scan_workers(self, files, checked_queue, hashes, ultra, cache_time, meta_data_cache):
        num_files = len(files)
        num_workers = 4
        if num_workers > num_files:
            num_workers = num_files
        start = 0
        step = int((num_files + (num_workers - 1)) / num_workers)
        for _ in range(num_workers):
            end = (start + step)
            if end > num_files:
                end = num_files
            Thread(target=self.check_files, args=[files, start, end,
                                                  checked_queue.put,
                                                  hashes, ultra, cache_time, meta_data_cache]).start()
            start = end

    # pylint: disable=R0914
    def scan_files(self, hashes, ultra):

        files = self.find_files()
        num_files = len(files)

        self.total_files = num_files

        cache_time, meta_data_cache = self.read_metadata_cache()

        checked_queue = Queue()

        self.start_scan_workers(files, checked_queue, hashes, ultra, cache_time, meta_data_cache)

        files_scanned = []
        files_to_upload = []
        meta_data = {}
        update_meta_data = False
        newer_time = -1

        while True:
            item = checked_queue.get()

            if item is None or self.stopped: # Stop event
                break

            elif isinstance(item, basestring): # Invalid file
                num_files -= 1

            else:
                if len(item) == 4: # Nothing to do for this file
                    relative_path, file_size, file_hash, file_time = item
                    meta_data[relative_path] = meta_data_cache[relative_path]
                    files_scanned.append((relative_path, file_size, file_hash))

                else:
                    if len(item) == 5: # Only need to update meta data cache
                        relative_path, file_size, file_hash, file_md5, file_time = item
                        files_scanned.append((relative_path, file_size, file_hash))

                    else: # Need to upload too
                        deploy_path, relative_path, file_size, file_hash, file_md5, file_time = item
                        files_to_upload.append((deploy_path, relative_path, file_size, file_hash, file_md5))

                    meta_data[relative_path] = {'length': file_size,
                                                'hash': file_hash,
                                                'md5': file_md5}
                    update_meta_data = True

                if newer_time < file_time:
                    newer_time = file_time

                self.num_bytes += file_size
                self.num_files += 1

            if self.num_files >= num_files:
                break

            item = None

        if self.stopped:
            # Copy old data to avoid recalculations
            meta_data.update(meta_data_cache)

        if update_meta_data or newer_time > cache_time or len(meta_data) != len(meta_data_cache):
            self.write_metadata_cache(meta_data, newer_time)
            self.delete_unused_cache_files(meta_data, meta_data_cache)

        return files_scanned, files_to_upload
    # pylint: enable=R0914

    def update_num_bytes(self, x):
        self.num_bytes += len(x)

    def post(self, url, params, boundary):
        headers = get_headers(params, boundary)
        headers['Cookie'] = self.hub_cookie
        params = MultipartParam.from_params(params)
        return self.hub_pool.urlopen('POST',
                                     url,
                                     MultipartReader(params, boundary),
                                     headers=headers,
                                     timeout=self.hub_timeout)

    # pylint: disable=R0914
    def post_files(self, files, start, end, uploaded_queue_put, boundary, local_deploy):

        hub_session = self.hub_session
        hub_cookie = self.hub_cookie
        hub_pool = self.hub_pool

        while start < end:
            if self.stopped:
                uploaded_queue_put(None) # Make sure the waiting thread wakes up
                break

            item = files[start]
            start += 1

            deploy_path, relative_path, file_size, file_hash, file_md5 = item

            try:
                if local_deploy:
                    guessed_type = guess_type(relative_path)[0]
                    if guessed_type is None:
                        guessed_type = ""
                    params = {'file.content_type': guessed_type,
                              'file.name': relative_path,
                              'file.path': deploy_path,
                              'session': hub_session,
                              'hash': file_hash,
                              'length': str(file_size),
                              'md5': file_md5}
                    if deploy_path.endswith('.gz'):
                        params['encoding'] = 'gzip'
                    r = hub_pool.request('POST',
                                         '/dynamic/upload/file',
                                          fields=params,
                                          headers={'Cookie': hub_cookie},
                                          timeout=self.hub_timeout)
                else:
                    params = [MultipartParam('file',
                                             filename=relative_path,
                                             filetype=guess_type(relative_path)[0],
                                             fileobj=open(deploy_path, 'rb')),
                              ('session', hub_session),
                              ('hash', file_hash),
                              ('length', file_size),
                              ('md5', file_md5)]
                    if deploy_path.endswith('.gz'):
                        params.append(('encoding', 'gzip'))

                    headers = get_headers(params, boundary)
                    headers['Cookie'] = hub_cookie
                    params = MultipartParam.from_params(params)
                    params = MultipartReader(params, boundary)

                    r = hub_pool.urlopen('POST',
                                         '/dynamic/upload/file',
                                         params,
                                         headers=headers,
                                         timeout=self.hub_timeout)
            except IOError:
                self.stop('Error opening file "%s".' % deploy_path)
                continue
            except (HTTPError, SSLError, ValueError) as e:
                self.stop('Error uploading file "%s": "%s".' % (relative_path, e))
                continue

            if r.headers.get('content-type', '') != 'application/json; charset=utf-8':
                self.stop('Hub error uploading file "%s".' % relative_path)
                continue

            answer = json_loads(r.data)

            # pylint: disable=E1103
            if r.status != 200:
                if answer.get('corrupt', False):
                    self.stop('File "%s" corrupted on transit.' % relative_path)
                else:
                    msg = answer.get('msg', None)
                    if msg:
                        self.stop('Error when uploading file "%s".\n%s' % (relative_path, msg))
                    else:
                        self.stop('Error when uploading file "%s": "%s"' % (relative_path, r.reason))
                continue

            if not answer.get('ok', False):
                self.stop('Error uploading file "%s".' % relative_path)
                continue
            # pylint: enable=E1103

            uploaded_queue_put((relative_path, file_size, file_hash))

            answer = None
            r = None
            params = None
            relative_path = None
            deploy_path = None
            item = None
    # pylint: enable=R0914

    def start_upload_workers(self, files, uploaded_queue, boundary, local_deploy):
        num_files = len(files)
        num_workers = 4
        if num_workers > num_files:
            num_workers = num_files
        start = 0
        step = int((num_files + (num_workers - 1)) / num_workers)
        for _ in range(num_workers):
            end = (start + step)
            if end > num_files:
                end = num_files
            Thread(target=self.post_files, args=[files, start, end, uploaded_queue.put, boundary, local_deploy]).start()
            start = end

    def upload_files(self, ultra):

        hashes = self.load_hashes(self.hub_project)
        files_scanned, files_to_upload = self.scan_files(hashes, ultra)

        if self.stopped:
            return False

        num_files = self.num_files
        if num_files <= 0:
            return True

        boundary = gen_boundary()

        local_deploy = self.hub_pool.host in ['127.0.0.1', '0.0.0.0', 'localhost']

        try:
            if local_deploy:
                params = {'files.path': self.get_meta_data_path(),
                          'encoding': 'gzip',
                          'project': self.hub_project,
                          'version': self.hub_version,
                          'versiontitle': self.hub_versiontitle,
                          'pluginmain': self.plugin_main,
                          'canvasmain': self.canvas_main,
                          'flashmain': self.flash_main,
                          'mappingtable': self.mapping_table,
                          'engineversion': self.engine_version,
                          'ismultiplayer': self.is_multiplayer,
                          'aspectratio': self.aspect_ratio,
                          'numfiles': str(num_files),
                          'numbytes': str(self.num_bytes),
                          'localversion': __version__}
                r = self.hub_pool.request('POST',
                                          '/dynamic/upload/begin',
                                           fields=params,
                                           headers={'Cookie': self.hub_cookie},
                                           timeout=self.hub_timeout)
            else:
                r = self.post('/dynamic/upload/begin',
                              [MultipartParam('files',
                                              filename='files.json',
                                              filetype='application/json; charset=utf-8',
                                              fileobj=open(self.get_meta_data_path(), 'rb')),
                               ('encoding', 'gzip'),
                               ('project', self.hub_project),
                               ('version', self.hub_version),
                               ('versiontitle', self.hub_versiontitle),
                               ('pluginmain', self.plugin_main),
                               ('canvasmain', self.canvas_main),
                               ('flashmain', self.flash_main),
                               ('mappingtable', self.mapping_table),
                               ('engineversion', self.engine_version),
                               ('ismultiplayer', self.is_multiplayer),
                               ('aspectratio', self.aspect_ratio),
                               ('numfiles', num_files),
                               ('numbytes', self.num_bytes),
                               ('localversion', __version__)],
                              boundary)
        except IOError:
            self.stop('Error opening file "%s".' % self.get_meta_data_path())
            return False
        except (HTTPError, SSLError) as e:
            self.stop('Error starting upload: "%s".' % e)
            return False

        if r.status == 504:
            self.stop('Hub timed out.')
            return False

        if r.headers.get('content-type', '') == 'application/json; charset=utf-8' and r.data != '':
            try:
                answer = json_loads(r.data)
            except JSONDecodeError as e:
                LOG.error(e)
                answer = {}
        else:
            answer = {}

        if r.status != 200:
            msg = answer.get('msg', False)
            if msg:
                self.stop(msg)
            else:
                self.stop('Error starting upload: "%s".' % r.reason)
            return False

        hub_session = answer.get('session', None)

        if not answer.get('ok', False) or not hub_session:
            self.stop('Unsupported response format from Hub.')
            return False

        self.hub_session = hub_session

        get_cached_file_name = _get_cached_file_name

        for file_name, file_size, file_hash in files_scanned:
            hashes.add(get_cached_file_name(file_name, file_hash, file_size))

            self.uploaded_bytes += file_size
            self.uploaded_files += 1

        if self.uploaded_files >= num_files:
            self.save_hashes(hashes)
            return True

        # we only reach this code if there are files to upload
        uploaded_queue = Queue()
        self.start_upload_workers(files_to_upload, uploaded_queue, boundary, local_deploy)

        while True:

            item = uploaded_queue.get()

            if item is None or self.stopped:
                break

            file_name, file_size, file_hash = item

            hashes.add(get_cached_file_name(file_name, file_hash, file_size))

            self.uploaded_bytes += file_size
            self.uploaded_files += 1
            if self.uploaded_files >= num_files:
                self.save_hashes(hashes)
                return True

            item = None

        self.save_hashes(hashes)
        return False

    @classmethod
    def rename_cache(cls, cache_dir, old_slug, new_slug):
        old_file = join(cache_dir, old_slug) + '.json.gz'
        new_file = join(cache_dir, new_slug) + '.json.gz'
        old_folder = join(cache_dir, old_slug)
        new_folder = join(cache_dir, new_slug)

        # delete the new folder is necessary, otherwise the
        # old one will just end up inside of it
        try:
            remove(new_file)
            rmtree(new_folder)
        except OSError:
            pass
        try:
            rename(old_file, new_file)
            rename(old_folder, new_folder)
        except OSError:
            pass
# pylint: enable=R0902


class MultipartReader(object):
    def __init__(self, params, boundary):
        self.params = params
        self.boundary = boundary

        self.i = 0
        self.param = None
        self.param_iter = None

    def __iter__(self):
        return self

    def read(self, blocksize):
        """generator function to return multipart/form-data representation
        of parameters"""
        if self.param_iter is not None:
            try:
                return self.param_iter.next()
            except StopIteration:
                self.param = None
                self.param_iter = None

        if self.i is None:
            return None
        elif self.i >= len(self.params):
            self.param_iter = None
            self.param = None
            self.i = None
            return "--%s--\r\n" % self.boundary

        self.param = self.params[self.i]
        self.param_iter = self.param.iter_encode(self.boundary, blocksize)
        self.i += 1
        return self.read(blocksize)

    def reset(self):
        self.i = 0
        for param in self.params:
            param.reset()
