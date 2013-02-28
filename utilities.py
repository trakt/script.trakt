# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import time, socket
import math
import urllib2
import base64

from urllib2 import HTTPError, URLError
from httplib import HTTPException

try:
	import simplejson as json
except ImportError:
	import json

try:
	from hashlib import sha1
except ImportError:
	from sha import new as sha1

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

apikey = 'b6135e0f7510a44021fac8c03c36c81a17be35d9'

username = __settings__.getSetting("username").strip()
pwd = sha1(__settings__.getSetting("password")).hexdigest()
debug = __settings__.getSetting("debug")
traktSettings = None

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

def checkSettings(daemon=False):
	if username == "":
		if daemon:
			notification("trakt", __language__(1106).encode( "utf-8", "ignore" )) # please enter your Username and Password in settings
		else:
			xbmcgui.Dialog().ok("trakt", __language__(1106).encode( "utf-8", "ignore" )) # please enter your Username and Password in settings
			__settings__.openSettings()
		return False
	elif __settings__.getSetting("password") == "":
		if daemon:
			notification("trakt", __language__(1107).encode( "utf-8", "ignore" )) # please enter your Password in settings
		else:
			xbmcgui.Dialog().ok("trakt", __language__(1107).encode( "utf-8", "ignore" )) # please enter your Password in settings
			__settings__.openSettings()
		return False

	data = traktJsonRequest('POST', '/account/test/%%API_KEY%%', silent=True)
	if data == None: #Incorrect trakt login details
		if daemon:
			notification("trakt", __language__(1110).encode( "utf-8", "ignore" )) # please enter your Password in settings
		else:
			xbmcgui.Dialog().ok("trakt", __language__(1110).encode( "utf-8", "ignore" )) # please enter your Password in settings
			__settings__.openSettings()
		return False

	return True

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



# helper method to format api call url
def formatTraktURL(req):

	# default to always https
	url = "https://api.trakt.tv" + req
	
	# replace api and username values
	url = url.replace("%%API_KEY%%", apikey)
	url = url.replace("%%USERNAME%%", username)
	
	return url

# helper function for making requests through urllib2
def get_data(url, args):
	data = None
	try:
		Debug("get_data(): urllib2.Request(%s)" % url)
		if args == None:
			req = urllib2.Request(url)
		else:
			req = urllib2.Request(url, args)
			# add basic http header authentication
			base64string = base64.encodestring('%s:%s' % (username, pwd)).replace('\n', '')
			req.add_header("Authorization", "Basic %s" % base64string)
		Debug("get_data(): urllib2.urlopen()")
		response = urllib2.urlopen(req)
		Debug("get_data(): response.read()")
		data = response.read()
	except socket.timeout:
		Debug("get_data(): can't connect to trakt - timeout")
		notification("trakt", __language__(1108).encode( "utf-8", "ignore" ) + " (timeout)") # can't connect to trakt
		return None
	except HTTPError, e:
		Debug("get_data(): HTTPError = %s" % str(e.code))
		return None
	except URLError, e:
		Debug("get_data(): URLError = %s" % str(e.reason))
		return None
	except HTTPException, e:
		Debug("get_data(): HTTPException")
		return None
	except Exception:
		import traceback
		Debug("get_data(): Generic exception: %s" % traceback.format_exc())
		return None

	return data

# make a JSON api request to trakt
# method: http method (GET or POST)
# req: REST request (ie '/user/library/movies/all.json/%%API_KEY%%/%%USERNAME%%')
# args: arguments to be passed by POST JSON (only applicable to POST requests), default:{}
# returnStatus: when unset or set to false the function returns None apon error and shows a notification,
#	when set to true the function returns the status and errors in ['error'] as given to it and doesn't show the notification,
#	use to customise error notifications
# anon: anonymous (dont send username/password), default:False
# connection: default it to make a new connection but if you want to keep the same one alive pass it here
# silent: default is True, when true it disable any error notifications (but not debug messages)
# passVersions: default is False, when true it passes extra version information to trakt to help debug problems
def traktJsonRequest(method, req, args={}, returnStatus=False, anon=False, conn=False, silent=True, passVersions=False):
	raw = None
	data = None
	jdata = {}
	retries = get_int_setting("retries")

	if not (method == 'POST' or method == 'GET'):
		Debug("traktJsonRequest(): Unknown method '%s'" % method)
		return None
	
	# get trakt api url to open
	url = formatTraktURL(req)
	
	if method == 'POST':
		if passVersions:
			args['plugin_version'] = __settings__.getAddonInfo("version")
			args['media_center_version'] = xbmc.getInfoLabel("system.buildversion")
			args['media_center_date'] = xbmc.getInfoLabel("system.builddate")
		jdata = json.dumps(args)
		Debug("traktJsonRequest(): Request Data: '%s'" % str(jdata))

	Debug("traktJsonRequest(): Starting retry loop, maximum %i retries." % retries)
	
	for i in range(0,retries):	
		try:
			Debug("traktJsonRequest(): (%i) Request URL '%s'" % (i, url))
			raw = get_data(url, jdata)
			if xbmc.abortRequested:
				Debug("traktJsonRequest(): (%i) xbmc.abortRequested" % i)
				break
			if not raw:
				Debug("traktJsonRequest(): (%i) JSON Response empty" % i)
				time.sleep(0.1)
				continue
				
			# get json formatted data	
			data = json.loads(raw)
			Debug("traktJsonRequest(): (%i) JSON response: '%s'" % (i, str(data)))
			
			# check for the status variable in JSON data
			if 'status' in data:
				if data['status'] == 'success':
					break
				else:
					Debug("traktJsonRequest(): (%i) JSON Error '%s' -> '%s'" % (i, data['status'], data['error']))
					time.sleep(0.1)
					continue
			
			# check to see if we have data
			if data:
				Debug("traktJsonRequest(): Have JSON data, breaking retry.")
				break
			
		except ValueError:
			Debug("traktJsonRequest(): (%i) Bad JSON response: '%s'", (i, raw))
			if not silent:
				notification("trakt", __language__(1109).encode( "utf-8", "ignore" ) + ": Bad response from trakt") # Error
		except Exception:
			import traceback
			Debug("traktJsonRequest(): (%i) Unknown Exception: %s" % (i, traceback.format_exc()))

		time.sleep(0.1)
	
	# handle scenario where all retries fail
	if not data:
		Debug("traktJsonRequest(): JSON Request failed, data is still empty after retries.")
		return None
	
	if 'status' in data:
		if data['status'] == 'failure':
			Debug("traktJsonRequest(): Error: %s" % str(data['error']))
			if returnStatus:
				return data
			if not silent:
				notification("trakt", __language__(1109).encode( "utf-8", "ignore" ) + ": " + str(data['error'])) # Error
			return None
		elif data['status'] == 'success':
			Debug("traktJsonRequest(): JSON request was successful.")

	return data

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

###############################
##### Scrobbling to trakt #####
###############################

#tell trakt that the user is watching a movie
def watchingMovieOnTrakt(imdb_id, title, year, duration, percent):
	Debug("watchingMovieOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/movie/watching/%%API_KEY%%', {'imdb_id': imdb_id, 'title': title, 'year': year, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	Debug("watchingMovieOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("watchingMovieOnTrakt(): Error in request")
	return response

#tell trakt that the user is watching an episode
def watchingEpisodeOnTrakt(tvdb_id, title, year, season, episode, uniqueid, duration, percent):
	Debug("watchingEpisodeOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/show/watching/%%API_KEY%%', {'tvdb_id': tvdb_id, 'title': title, 'year': year, 'season': season, 'episode': episode, 'episode_tvdb_id': uniqueid, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	Debug("watchingEpisodeOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("watchingEpisodeOnTrakt(): Error in request")
	return response

#tell trakt that the user has stopped watching a movie
def cancelWatchingMovieOnTrakt():
	Debug("cancelWatchingMovieOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/movie/cancelwatching/%%API_KEY%%')
	Debug("cancelWatchingMovieOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("cancelWatchingMovieOnTrakt(): Error in request")
	return response

#tell trakt that the user has stopped an episode
def cancelWatchingEpisodeOnTrakt():
	Debug("cancelWatchingEpisodeOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/show/cancelwatching/%%API_KEY%%')
	Debug("cancelWatchingEpisodeOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("cancelWatchingEpisodeOnTrakt(): Error in request")
	return response

#tell trakt that the user has finished watching an movie
def scrobbleMovieOnTrakt(imdb_id, title, year, duration, percent):
	Debug("scrobbleMovieOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/movie/scrobble/%%API_KEY%%', {'imdb_id': imdb_id, 'title': title, 'year': year, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	Debug("scrobbleMovieOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("scrobbleMovieOnTrakt(): Error in request")
	return response

#tell trakt that the user has finished watching an episode
def scrobbleEpisodeOnTrakt(tvdb_id, title, year, season, episode, uniqueid, duration, percent):
	Debug("scrobbleEpisodeOnTrakt(): Calling traktJsonRequest()")
	response = traktJsonRequest('POST', '/show/scrobble/%%API_KEY%%', {'tvdb_id': tvdb_id, 'title': title, 'year': year, 'season': season, 'episode': episode, 'episode_tvdb_id': uniqueid, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	Debug("scrobbleEpisodeOnTrakt(): traktJsonRequest() returned")
	if response == None:
		Debug("scrobbleEpisodeOnTrakt(): Error in request")
	return response

def getTraktSettings():
	"""Get the users settings from trakt.tv"""
	global traktSettings

	response = traktJsonRequest('POST', '/account/settings/%%API_KEY%%', passVersions=True)
	if response == None:
		Debug("Error in request from 'getTraktSettings()'")

	traktSettings = response
