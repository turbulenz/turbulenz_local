# Copyright (c) 2013 Turbulenz Limited

from os import listdir as os_listdir
from os.path import join as path_join, isdir as path_isdir, exists as path_exists

from glob import iglob

def _posixpath(path):
    return path.replace('\\', '/')

def _join(*args):
    return _posixpath(path_join(*args))

def compact(dev_path, rel_path, versions_yaml, src_type, compactor_fn, merge=False):
    from yaml import dump as yaml_dump
    from turbulenz_tools.utils.hash import hash_for_file, hash_for_string

    rel_path = _posixpath(rel_path)
    dev_path = _posixpath(dev_path)
    new_versions = { }

    def _compact_directory(path):
        # Search for folders and recurse.
        for p in [f for f in os_listdir(path) if path_isdir(path_join(path, f))]:
            _compact_directory(_join(path, p))

        # Search the development path for all src files.
        for dev_filename in iglob(_join(path, '*.%s' % src_type)):
            dev_filename = _posixpath(dev_filename)
            current_hash = hash_for_file(dev_filename)
            # Build a suitable output filename - hash.ext
            rel_filename = _join(rel_path, src_type, '%s.%s' % (current_hash, src_type))
            if not path_exists(rel_filename):
                compactor_fn(dev_filename, rel_filename)

            # Update the list of compact files, so it can be reused when generating script tags.
            new_versions[dev_filename[len(dev_path):]] = rel_filename[len(rel_path):]

    _compact_directory(dev_path)

    if merge:
        current_hash = hash_for_string(''.join([v for _, v in new_versions.iteritems()]))
        rel_filename = _join(rel_path, src_type, '%s.%s' % (current_hash, src_type))
        if not path_exists(rel_filename):
            # Merge the compacted files.
            with open(rel_filename, 'w') as t:
                for _, v in new_versions.iteritems():
                    with open('%s%s' % (rel_path, v)) as f:
                        t.write(f.read())
                        t.write('\n')

        new_versions['/%s/_merged.%s' % (src_type, src_type)] = rel_filename[len(rel_path):]

    # We don't catch any exceptions here - as it will be handled by the calling function.
    with open(versions_yaml, 'w') as f:
        yaml_dump(new_versions, f, default_flow_style=False)
