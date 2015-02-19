# -*- coding: utf-8 -*-
#
import xbmcaddon
import logging
import kodilogging
from service import traktService

__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__ = __addon__.getAddonInfo('id')
kodilogging.config()
logger = logging.getLogger(__name__)

logger.debug("Loading '%s' version '%s'" % (__addonid__, __addonversion__))

try:
	traktService().run()
except Exception as ex:
	message = utilities.createError(ex)
	logger.fatal(message)

logger.debug("'%s' shutting down." % __addonid__)
