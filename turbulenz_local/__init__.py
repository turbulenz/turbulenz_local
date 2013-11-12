# Copyright (c) 2010-2013 Turbulenz Limited

__version__ = '1.1.4'

import os.path
CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config')

try:
    from turbulenz_tools.version import SDK_VERSION as SDK_VERSION_4
    SDK_VERSION_3 = ".".join(SDK_VERSION_4.split(".")[0:3])

    SDK_VERSION = SDK_VERSION_3
except ImportError:
    SDK_VERSION = None

