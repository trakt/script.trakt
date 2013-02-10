# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import nbconnection
import time, socket
import math

try:
	import simplejson as json
except ImportError:
	import json

try:
	from hashlib import sha as sha # Python 2.6 +
except ImportError:
	import sha # Python 2.5 and earlier

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

apikey = 'b6135e0f7510a44021fac8c03c36c81a17be35d9'

username = __settings__.getSetting("username").strip()
pwd = sha.new(__settings__.getSetting("password").strip()).hexdigest()
debug = __settings__.getSetting("debug")

def Debug(msg, force = False):
	if(debug == 'true' or force):
		try:
			print "[trakt] " + msg
		except UnicodeEncodeError:
			print "[trakt] " + msg.encode( "utf-8", "ignore" )

def notification( header, message, time=5000, icon=__settings__.getAddonInfo("icon")):
	xbmc.executebuiltin( "XBMC.Notification(%s,%s,%i,%s)" % ( header, message, time, icon ) )

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

# get a connection to trakt
def getTraktConnection():
	https = __settings__.getSetting('https')
	try:
		if (https == 'true'):
			conn = nbconnection.NBConnection('api.trakt.tv', https=True)
		else:
			conn = nbconnection.NBConnection('api.trakt.tv')
	except socket.timeout:
		Debug("getTraktConnection: can't connect to trakt - timeout")
		notification("trakt", __language__(1108).encode( "utf-8", "ignore" ) + " (timeout)") # can't connect to trakt
		return None
	return conn

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
	closeConnection = False
	if conn == False:
		conn = getTraktConnection()
		closeConnection = True
	if conn == None:
		Debug("traktJsonRequest(): Unable to create connection to trakt.")
		if returnStatus:
			data = {}
			data['status'] = 'failure'
			data['error'] = 'Unable to connect to trakt'
			return data
		return None

	try:
		req = req.replace("%%API_KEY%%", apikey)
		req = req.replace("%%USERNAME%%", username)
		if method == 'POST':
			if not anon:
				args['username'] = username
				args['password'] = pwd
			if passVersions:
				args['plugin_version'] = __settings__.getAddonInfo("version")
				args['media_center_version'] = xbmc.getInfoLabel("system.buildversion")
				args['media_center_date'] = xbmc.getInfoLabel("system.builddate")
			jdata = json.dumps(args)
			conn.request('POST', req, jdata)
		elif method == 'GET':
			conn.request('GET', req)
		else:
			Debug("traktJsonRequest(): Unknown method " + method)
			return None
		Debug("traktJsonRequest(): "+method+" JSON url: "+req)
	except socket.error:
		Debug("traktJsonRequest(): Unable to connect to trakt.")
		if not silent:
			notification("trakt", __language__(1108).encode( "utf-8", "ignore" )) # can't connect to trakt
		if returnStatus:
			data = {}
			data['status'] = 'failure'
			data['error'] = 'Socket error, unable to connect to trakt'
			return data
		return None

	conn.go()

	while True:
		if xbmc.abortRequested:
			Debug("traktJsonRequest(): Broke loop due to abort.")
			if returnStatus:
				data = {}
				data['status'] = 'failure'
				data['error'] = 'Abort requested, not waiting for response'
				return data
			return None
		if conn.readError:
			Debug("traktJsonRequest(): Error reading response.")
			if returnStatus:
				data = {}
				data['status'] = 'failure'
				data['error'] = 'Error getting response, read error on socket.'
				return data
			return None
		if conn.hasResult():
			Debug("traktJsonRequest(): hasResult()")
			break
		time.sleep(0.1)

	Debug("traktJsonRequest(): Get response object.")
	response = conn.getResult()
	if response == None:
		Debug("traktJsonRequest(): Response not set.")
		if returnStatus:
			data = {}
			data['status'] = 'failure'
			data['error'] = 'Error getting response, response not set.'
			return data
		return None
		
	Debug("traktJsonRequest(): Trying to read response.")
	try:
		raw = response.read()
	except:
		Debug("traktJsonRequest(): Exception reading response.")
		if returnStatus:
			data = {}
			data['status'] = 'failure'
			data['error'] = 'Error getting response, exception reading response.'
			return data
		return None
	
	if closeConnection:
		conn.close()

	try:
		data = json.loads(raw)
		Debug("traktJsonRequest(): JSON response: " + str(data))
	except ValueError:
		Debug("traktJsonRequest(): Bad JSON response: " + raw)
		if returnStatus:
			data = {}
			data['status'] = 'failure'
			data['error'] = 'Bad response from trakt'
			return data
		if not silent:
			notification("trakt", __language__(1109).encode( "utf-8", "ignore" ) + ": Bad response from trakt") # Error
		return None

	if 'status' in data:
		if data['status'] == 'failure':
			Debug("traktJsonRequest(): Error: " + str(data['error']))
			if returnStatus:
				return data
			if not silent:
				notification("trakt", __language__(1109).encode( "utf-8", "ignore" ) + ": " + str(data['error'])) # Error
			return None

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
	response = traktJsonRequest('POST', '/movie/watching/%%API_KEY%%', {'imdb_id': imdb_id, 'title': title, 'year': year, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	if response == None:
		Debug("Error in request from 'watchingMovieOnTrakt()'")
	return response

#tell trakt that the user is watching an episode
def watchingEpisodeOnTrakt(tvdb_id, title, year, season, episode, uniqueid, duration, percent):
	response = traktJsonRequest('POST', '/show/watching/%%API_KEY%%', {'tvdb_id': tvdb_id, 'title': title, 'year': year, 'season': season, 'episode': episode, 'episode_tvdb_id': uniqueid, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	if response == None:
		Debug("Error in request from 'watchingEpisodeOnTrakt()'")
	return response

#tell trakt that the user has stopped watching a movie
def cancelWatchingMovieOnTrakt():
	response = traktJsonRequest('POST', '/movie/cancelwatching/%%API_KEY%%')
	if response == None:
		Debug("Error in request from 'cancelWatchingMovieOnTrakt()'")
	return response

#tell trakt that the user has stopped an episode
def cancelWatchingEpisodeOnTrakt():
	response = traktJsonRequest('POST', '/show/cancelwatching/%%API_KEY%%')
	if response == None:
		Debug("Error in request from 'cancelWatchingEpisodeOnTrakt()'")
	return response

#tell trakt that the user has finished watching an movie
def scrobbleMovieOnTrakt(imdb_id, title, year, duration, percent):
	response = traktJsonRequest('POST', '/movie/scrobble/%%API_KEY%%', {'imdb_id': imdb_id, 'title': title, 'year': year, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	if response == None:
		Debug("Error in request from 'scrobbleMovieOnTrakt()'")
	return response

#tell trakt that the user has finished watching an episode
def scrobbleEpisodeOnTrakt(tvdb_id, title, year, season, episode, uniqueid, duration, percent):
	response = traktJsonRequest('POST', '/show/scrobble/%%API_KEY%%', {'tvdb_id': tvdb_id, 'title': title, 'year': year, 'season': season, 'episode': episode, 'episode_tvdb_id': uniqueid, 'duration': math.ceil(duration), 'progress': math.ceil(percent)}, passVersions=True)
	if response == None:
		Debug("Error in request from 'scrobbleEpisodeOnTrakt()'")
	return response
