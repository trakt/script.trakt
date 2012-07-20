# -*- coding: utf-8 -*-
# 

#import xbmc,xbmcaddon,xbmcgui
from utilities import *
from notification_service import *

__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

Debug("loading " + __settings__.getAddonInfo("id") + " version " + __settings__.getAddonInfo("version"))

# starts update/sync
def autostart():
	if checkSettings(True):
		notificationThread = NotificationService()
		notificationThread.start()	  
		notificationThread.join()

autostart()