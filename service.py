# -*- coding: utf-8 -*-
#

import xbmcaddon
from utilities import Debug, checkSettings
from notification_service import NotificationService

__settings__ = xbmcaddon.Addon("script.trakt")
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__ = __addon__.getAddonInfo('id')
__language__ = __addon__.getLocalizedString

Debug("Loading '%s' version '%s'" % (__addonid__, __addonversion__))

# starts update/sync
def autostart():
	if checkSettings(True):
		# startup notifcation service
		NotificationService()
	
	Debug("Plugin shutting down.")

autostart()
