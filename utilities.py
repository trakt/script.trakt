# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import math
import time

try:
	import simplejson as json
except ImportError:
	import json

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')

def Debug(msg, force = False):
	if(getSettingAsBool('debug') or force):
		try:
			print "[trakt] " + msg
		except UnicodeEncodeError:
			print "[trakt] " + msg.encode('utf-8', 'ignore')

def notification(header, message, time=5000, icon=__addon__.getAddonInfo('icon')):
	xbmc.executebuiltin("XBMC.Notification(%s,%s,%i,%s)" % (header, message, time, icon))

def getSetting(setting):
    return __addon__.getSetting(setting).strip()

def getSettingAsBool(setting):
        return getSetting(setting).lower() == "true"

def getSettingAsFloat(setting):
    try:
        return float(getSetting(setting))
    except ValueError:
        return 0

def getSettingAsInt(setting):
    try:
        return int(getSettingAsFloat(setting))
    except ValueError:		
        return 0

def setSetting(setting, value):
	__addon__.setSetting(setting, str(value))

def getString(string_id):
    return __addon__.getLocalizedString(string_id).encode('utf-8', 'ignore')

def getProperty(property):
	return xbmcgui.Window(10000).getProperty(property)

def getPropertyAsBool(property):
	return getProperty(property) == "True"
	
def setProperty(property, value):
	xbmcgui.Window(10000).setProperty(property, value)

def clearProperty(property):
	xbmcgui.Window(10000).clearProperty(property)

def isMovie(type):
	return type == 'movie'

def isEpisode(type):
	return type == 'episode'

def isShow(type):
	return type == 'show'

def isSeason(type):
	return type == 'season'

def isValidMediaType(type):
	return type in ['movie', 'show', 'episode']

def xbmcJsonRequest(params):
	data = json.dumps(params)
	request = xbmc.executeJSONRPC(data)
	response = json.loads(request)

	try:
		if 'result' in response:
			return response['result']
		return None
	except KeyError:
		Debug("[%s] %s" % (params['method'], response['error']['message']), True)
		return None

def sqlDateToUnixDate(date):
	if not date:
		return 0
	t = time.strptime(date, "%Y-%m-%d %H:%M:%S")
	return int(time.mktime(t))

def chunks(l, n):
	return [l[i:i+n] for i in range(0, len(l), n)]

# check exclusion settings for filename passed as argument
def checkScrobblingExclusion(fullpath):

	if not fullpath:
		return True
	
	Debug("checkScrobblingExclusion(): Checking exclusion settings for '%s'." % fullpath)
	
	if (fullpath.find("pvr://") > -1) and getSettingAsBool('ExcludeLiveTV'):
		Debug("checkScrobblingExclusion(): Video is playing via Live TV, which is currently set as excluded location.")
		return True
				
	if (fullpath.find("http://") > -1) and getSettingAsBool('ExcludeHTTP'):
		Debug("checkScrobblingExclusion(): Video is playing via HTTP source, which is currently set as excluded location.")
		return True
		
	ExcludePath = getSetting('ExcludePath')
	if ExcludePath != "" and getSettingAsBool('ExcludePathOption'):
		if (fullpath.find(ExcludePath) > -1):
			Debug("checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 1.")
			return True

	ExcludePath2 = getSetting('ExcludePath2')
	if ExcludePath2 != "" and getSettingAsBool('ExcludePathOption2'):
		if (fullpath.find(ExcludePath2) > -1):
			Debug("checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 2.")
			return True

	ExcludePath3 = getSetting('ExcludePath3')
	if ExcludePath3 != "" and getSettingAsBool('ExcludePathOption3'):
		if (fullpath.find(ExcludePath3) > -1):
			Debug("checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 3.")
			return True
	
	return False

def getFormattedItemName(type, info, short=False):
	s = None
	if isShow(type):
		s = info['title']
	elif isEpisode(type):
		if short:
			s = "S%02dE%02d - %s" % (info['episode']['season'], info['episode']['number'], info['episode']['title'])
		else:
			s = "%s - S%02dE%02d - %s" % (info['show']['title'], info['episode']['season'], info['episode']['number'], info['episode']['title'])
	elif isMovie(type):
		s = "%s (%s)" % (info['title'], info['year'])
	return s

def getShowDetailsFromXBMC(showID, fields):
	result = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params':{'tvshowid': showID, 'properties': ['year', 'imdbnumber']}, 'id': 1})
	Debug("getShowDetailsFromXBMC(): %s" % str(result))

	if not result:
		Debug("getEpisodeDetailsFromXbmc(): Result from XBMC was empty.")
		return None

	try:
		return result['tvshowdetails']
	except KeyError:
		Debug("getShowDetailsFromXBMC(): KeyError: result['tvshowdetails']")
		return None

# get a single episode from xbmc given the id
def getEpisodeDetailsFromXbmc(libraryId, fields):
	result = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodeDetails', 'params':{'episodeid': libraryId, 'properties': fields}, 'id': 1})
	Debug("getEpisodeDetailsFromXbmc(): %s" % str(result))

	if not result:
		Debug("getEpisodeDetailsFromXbmc(): Result from XBMC was empty.")
		return None

	show_data = getShowDetailsFromXBMC(result['episodedetails']['tvshowid'], ['year', 'imdbnumber'])
	
	if not show_data:
		Debug("getEpisodeDetailsFromXbmc(): Result from getShowDetailsFromXBMC() was empty.")
		return None
		
	result['episodedetails']['tvdb_id'] = show_data['imdbnumber']
	result['episodedetails']['year'] = show_data['year']
	
	try:
		return result['episodedetails']
	except KeyError:
		Debug("getEpisodeDetailsFromXbmc(): KeyError: result['episodedetails']")
		return None

# get a single movie from xbmc given the id
def getMovieDetailsFromXbmc(libraryId, fields):
	result = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params':{'movieid': libraryId, 'properties': fields}, 'id': 1})
	Debug("getMovieDetailsFromXbmc(): %s" % str(result))

	if not result:
		Debug("getMovieDetailsFromXbmc(): Result from XBMC was empty.")
		return None

	try:
		return result['moviedetails']
	except KeyError:
		Debug("getMovieDetailsFromXbmc(): KeyError: result['moviedetails']")
		return None
