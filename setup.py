#!/usr/bin/env python
# Copyright (c) 2013 Turbulenz Limited

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from turbulenz_local import __version__

import platform
import sys
from glob import iglob

if 'sdist' in sys.argv:
    SCRIPTS = list(iglob('scripts/*'))
elif platform.system() == 'Windows':
    SCRIPTS = list(iglob('scripts/*.bat'))
else:
    SCRIPTS = [ s for s in iglob('scripts/*') if not s.endswith('.bat') ]

setup(name='turbulenz_local',
    version=__version__,
    description='Turbulenz Local Development Web Server',
    author='Turbulenz Limited',
    author_email='support@turbulenz.com',
    url='https://turbulenz.com/',
    install_requires=[
        "simplejson>=2.1.5",
        "jinja2>=2.4",
        "Pylons>=1.0",
        "PyYAML>=3.09",
        "tornado>=3.0.1",
        "urllib3>=1.7.1",
        "poster>=0.8.1",
        "turbulenz_tools>=1.0.4"
    ],
    scripts=SCRIPTS,
    packages=[ 'turbulenz_local',
               'turbulenz_local.controllers', 'turbulenz_local.controllers.apiv1',
               'turbulenz_local.controllers.localv1',
               'turbulenz_local.handlers', 'turbulenz_local.handlers.localv1',
               'turbulenz_local.lib', 'turbulenz_local.middleware',
               'turbulenz_local.models', 'turbulenz_local.models.apiv1' ],
    include_package_data=True,
    package_data={'turbulenz_local': ['i18n/*/LC_MESSAGES/*.mo']},
    zip_safe=False,
    license = 'MIT',
    platforms = 'Posix; MacOS X; Windows',
    classifiers = ['Development Status :: 5 - Production/Stable',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Topic :: Software Development',
                   'Programming Language :: Python :: 2.7'],
    )
