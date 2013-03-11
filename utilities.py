# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import math

try:
	import simplejson as json
except ImportError:
	import json

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

debug = __settings__.getSetting("debug")

def Debug(msg, force = False):
	if(debug == 'true' or force):
		try:
			print "[trakt] " + msg
		except UnicodeEncodeError:
			print "[trakt] " + msg.encode( "utf-8", "ignore" )

def notification( header, message, time=5000, icon=__settings__.getAddonInfo("icon")):
	xbmc.executebuiltin( "XBMC.Notification(%s,%s,%i,%s)" % ( header, message, time, icon ) )

# helper function to get bool type from settings
def get_bool_setting(setting):
	return __settings__.getSetting(setting) == 'true'

# helper function to get string type from settings
def get_string_setting(setting):
	return __settings__.getSetting(setting).strip()

# helper function to get int type from settings
def get_int_setting(setting):
	return int(get_float_setting(setting))

# helper function to get float type from settings
def get_float_setting(setting):
	return float(__settings__.getSetting(setting))

def xbmcJsonRequest(params):
	data = json.dumps(params)
	request = xbmc.executeJSONRPC(data)
	response = json.loads(request)

	try:
		if "result" in response:
			return response["result"]
		return None
	except KeyError:
		Debug("[%s] %s" % (params["method"], response["error"]["message"]), True)
		return None

def chunks(l, n):
	return [l[i:i+n] for i in range(0, len(l), n)]

# check exclusion settings for filename passed as argument
def checkScrobblingExclusion(fullpath):

	if not fullpath:
		return True
	
	Debug("checkScrobblingExclusion(): Checking exclusion settings for '%s'" % fullpath)
	
	if (fullpath.find("pvr://") > -1) and get_bool_setting("ExcludeLiveTV"):
		Debug("checkScrobblingExclusion(): Video is playing via Live TV, which is currently set as excluded location.")
		return True
				
	if (fullpath.find("http://") > -1) and get_bool_setting("ExcludeHTTP"):
		Debug("checkScrobblingExclusion(): Video is playing via HTTP source, which is currently set as excluded location.")
		return True
		
	ExcludePath = get_string_setting("ExcludePath")
	if ExcludePath != "" and get_bool_setting("ExcludePathOption"):
		if (fullpath.find(ExcludePath) > -1):
			Debug('checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 1.')
			return True

	ExcludePath2 = get_string_setting("ExcludePath2")
	if ExcludePath2 != "" and get_bool_setting("ExcludePathOption2"):
		if (fullpath.find(ExcludePath2) > -1):
			Debug('checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 2.')
			return True

	ExcludePath3 = get_string_setting("ExcludePath3")
	if ExcludePath3 != "" and get_bool_setting("ExcludePathOption3"):
		if (fullpath.find(ExcludePath3) > -1):
			Debug('checkScrobblingExclusion(): Video is playing from location, which is currently set as excluded path 3.')
			return True
	
	return False

# get a single episode from xbmc given the id
def getEpisodeDetailsFromXbmc(libraryId, fields):
	rpccmd = json.dumps({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodeDetails', 'params':{'episodeid': libraryId, 'properties': fields}, 'id': 1})

	result = xbmc.executeJSONRPC(rpccmd)
	Debug('[VideoLibrary.GetEpisodeDetails] ' + result)
	result = json.loads(result)

	# check for error
	try:
		error = result['error']
		Debug("getEpisodeDetailsFromXbmc: " + str(error))
		return None
	except KeyError:
		pass # no error

	try:
		# get tvdb id
		rpccmd_show = json.dumps({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params':{'tvshowid': result['result']['episodedetails']['tvshowid'], 'properties': ['year', 'imdbnumber']}, 'id': 1})

		result_show = xbmc.executeJSONRPC(rpccmd_show)
		Debug('[VideoLibrary.GetTVShowDetails] ' + result_show)
		result_show = json.loads(result_show)

		# add to episode data
		result['result']['episodedetails']['tvdb_id'] = result_show['result']['tvshowdetails']['imdbnumber']
		result['result']['episodedetails']['year'] = result_show['result']['tvshowdetails']['year']

		return result['result']['episodedetails']
	except KeyError:
		Debug("getEpisodeDetailsFromXbmc: KeyError: result['result']['episodedetails']")
		return None

# get a single movie from xbmc given the id
def getMovieDetailsFromXbmc(libraryId, fields):
	rpccmd = json.dumps({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params':{'movieid': libraryId, 'properties': fields}, 'id': 1})

	result = xbmc.executeJSONRPC(rpccmd)
	Debug('[VideoLibrary.GetMovieDetails] ' + result)
	result = json.loads(result)

	# check for error
	try:
		error = result['error']
		Debug("getMovieDetailsFromXbmc: " + str(error))
		return None
	except KeyError:
		pass # no error

	try:
		return result['result']['moviedetails']
	except KeyError:
		Debug("getMovieDetailsFromXbmc: KeyError: result['result']['moviedetails']")
		return None

# get the length of the current video playlist being played from XBMC
def getPlaylistLengthFromXBMCPlayer(playerid):
	if playerid == -1:
		return 1 #Default player (-1) can't be checked properly
	if playerid < 0 or playerid > 2:
		Debug("[Util] getPlaylistLengthFromXBMCPlayer, invalid playerid: "+str(playerid))
		return 0
	rpccmd = json.dumps({'jsonrpc': '2.0', 'method': 'Player.GetProperties', 'params':{'playerid': playerid, 'properties':['playlistid']}, 'id': 1})
	result = xbmc.executeJSONRPC(rpccmd)
	result = json.loads(result)
	# check for error
	try:
		error = result['error']
		Debug("[Util] getPlaylistLengthFromXBMCPlayer, Player.GetProperties: " + str(error))
		return 0
	except KeyError:
		pass # no error
	playlistid = result['result']['playlistid']

	rpccmd = json.dumps({'jsonrpc': '2.0', 'method': 'Playlist.GetProperties', 'params':{'playlistid': playlistid, 'properties': ['size']}, 'id': 1})
	result = xbmc.executeJSONRPC(rpccmd)
	result = json.loads(result)
	# check for error
	try:
		error = result['error']
		Debug("[Util] getPlaylistLengthFromXBMCPlayer, Playlist.GetProperties: " + str(error))
		return 0
	except KeyError:
		pass # no error

	return result['result']['size']

