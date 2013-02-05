# -*- coding: utf-8 -*-
#

import xbmcaddon
from utilities import Debug, checkSettings, getTraktSettings
from notification_service import NotificationService

__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

Debug("loading " + __settings__.getAddonInfo("id") + " version " + __settings__.getAddonInfo("version"))

# starts update/sync
def autostart():
	if checkSettings(True):
		getTraktSettings()
		notificationThread = NotificationService()
		notificationThread.start()
		notificationThread.join()

autostart()
