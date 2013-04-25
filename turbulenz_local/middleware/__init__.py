# Copyright (c) 2010-2011,2013 Turbulenz Limited

from turbulenz_local.middleware.gzipcompress import GzipMiddleware
from turbulenz_local.middleware.metrics import MetricsMiddleware
from turbulenz_local.middleware.requestlog import LoggingMiddleware
from turbulenz_local.middleware.static_game_files import StaticGameFilesMiddleware
from turbulenz_local.middleware.static_files import StaticFilesMiddleware
from turbulenz_local.middleware.compact import CompactMiddleware
from turbulenz_local.middleware.etag import EtagMiddleware
from turbulenz_local.middleware.error import ErrorMiddleware
