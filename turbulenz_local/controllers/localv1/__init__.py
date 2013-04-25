# Copyright (c) 2010-2011,2013 Turbulenz Limited

import logging

from pylons import tmpl_context as c, config

from turbulenz_local.controllers import BaseController, render

LOG = logging.getLogger(__name__)

class Localv1Controller(BaseController):

    def __init__(self):
        BaseController.__init__(self)

        # We only publish routes to the applications that:
        # 1. Have a name
        # 2. Are not flagged as 'private'
        routes = [ ]
        for r in config.get('routes.map').matchlist:
            if not r.defaults.get('private', False):
                name = r.name
                if name:
                    routes.append( (name, r.routepath) )
        self.routes = routes

    def app(self):
        c.routes = self.routes
        return render('local.html')
