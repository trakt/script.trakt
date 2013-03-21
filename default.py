# -*- coding: utf-8 -*-
#

import xbmcaddon
import utilities
from service import traktService

__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__ = __addon__.getAddonInfo('id')

utilities.Debug("Loading '%s' version '%s'" % (__addonid__, __addonversion__))
traktService().run()
utilities.Debug("'%s' shutting down." % __addonid__)
