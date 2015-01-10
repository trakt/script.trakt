# -*- coding: utf-8 -*-
#
from trakt import Trakt


# read settings
__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')

class traktAPI(object):

	def __init__(self, loadSettings=False):
		Debug("[traktAPI] Initializing.")

		self.__username = getSetting('username')
		self.__password = getSetting('password')

		Trakt.configure(
		    api_key='d4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868',

		    # `credentials` is optional (only required when updating your profile)
		    credentials=(
		        getSetting('username'),
		        getSetting('password')
    )
)



