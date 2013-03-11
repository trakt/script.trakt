# -*- coding: utf-8 -*-
#

import xbmcaddon
import globals
from utilities import Debug
from traktapi import traktAPI
from notification_service import NotificationService

__addon__ = xbmcaddon.Addon("script.trakt")
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__ = __addon__.getAddonInfo('id')
__language__ = __addon__.getLocalizedString

Debug("Loading '%s' version '%s'" % (__addonid__, __addonversion__))

# starts update/sync
def autostart():

	# init traktapi class
	globals.traktapi = traktAPI()

	# startup notification
	NotificationService()
	
	Debug("Plugin shutting down.")

autostart()
