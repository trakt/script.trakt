# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import xbmcgui
import time, socket
import math
import urllib2
import base64

from utilities import Debug, notification, getSetting, getSettingAsBool, getSettingAsInt, getString, setSetting, findMovieMatchInList, findShowMatchInList, findEpisodeMatchInList
from urllib2 import Request, urlopen, HTTPError, URLError
from httplib import HTTPException, BadStatusLine

try:
	import simplejson as json
except ImportError:
	import json

try:
	from hashlib import sha1
except ImportError:
	from sha import new as sha1

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')

class traktError(Exception):
	def __init__(self, value, code=None):
		self.value = value
		if code:
			self.code = code
	def __str__(self):
		return repr(self.value)

class traktAuthProblem(traktError): pass
class traktServerBusy(traktError): pass
class traktUnknownError(traktError): pass
class traktNotFoundError(traktError): pass
class traktNetworkError(traktError):
	def __init__(self, value, timeout):
		super(traktNetworkError, self).__init__(value)
		self.timeout = timeout

class traktAPI(object):

	__apikey = "d4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868"
	__baseURL = "https://api.trakt.tv"
	__username = ""
	__password = ""
	__userToken = ""
	__apiVersion = "2"

	def __init__(self, loadSettings=False):
		Debug("[traktAPI] Initializing.")

		self.__username = getSetting('username')
		self.__password = getSetting('password')

		self.__userToken = self.__userLogin()

	def __userLogin(self):
		# inject username/pass into json data
		args = {}
		args['login'] = self.__username
		args['password'] = self.__password

		url = "%s/auth/login" % (self.__baseURL)
		# get data from trakt.tv
		data = self.traktRequest('POST', url, args)

		Debug("[traktAPI] __userLogin(): token: '%s'" % data['token'])
		return data['token']


	def __getData(self, url, args, method, timeout=60):
		data = None
		try:
			Debug("[traktAPI] __getData(): urllib2.Request(%s)" % url)

			headers = { 'trakt-user-login': self.__username,
						'trakt-user-token': self.__userToken,
						'Content-type': 'application/json',
						'trakt-api-key': self.__apikey,
						'trakt-api-version': '2'
						}

			if args == None:
				Debug("[traktAPI] __getData(): Without args")
				req = Request(url, headers)
			else:
				Debug("[traktAPI] __getData(): With args")
				req = Request(url, args, headers)

			req.get_method = lambda: method
			Debug("[traktAPI] __getData(): urllib2.urlopen()")
			t1 = time.time()
			response = urlopen(req, timeout=timeout)
			t2 = time.time()

			Debug("[traktAPI] __getData(): response.read()")
			data = response.read()

			Debug("[traktAPI] __getData(): Response Code: %i" % response.getcode())
			Debug("[traktAPI] __getData(): Response Time: %0.2f ms" % ((t2 - t1) * 1000))
			Debug("[traktAPI] __getData(): Response Headers: %s" % str(response.info().dict))

		except BadStatusLine, e:
			raise traktUnknownError("BadStatusLine: '%s' from URL: '%s'" % (e.line, url))
		except IOError, e:
			if hasattr(e, 'code'): # error 401 or 503, possibly others
				# read the error document, strip newlines, this will make an html page 1 line
				error_data = e.read().replace("\n", "").replace("\r", "")

				if e.code == 401: # authentication problem
					raise traktAuthProblem(error_data)
				elif e.code == 503: # server busy problem
					raise traktServerBusy(error_data)
				else:
					try:
						_data = json.loads(error_data)
						if 'status' in _data:
							data = error_data
					except ValueError:
						raise traktUnknownError(error_data, e.code)

			elif hasattr(e, 'reason'): # usually a read timeout, or unable to reach host
				raise traktNetworkError(str(e.reason), isinstance(e.reason, socket.timeout))

			else:
				raise traktUnknownError(e.message)

		return data

	# make a JSON api request to trakt
	# method: http method (GET or POST or PUT or DELETE)
	# args: arguments to be passed by JSON, default:{}
	# returnStatus: when unset or set to false the function returns None upon error and shows a notification,
	#	when set to true the function returns the status and errors in ['error'] as given to it and doesn't show the notification,
	#	use to customise error notifications
	# silent: default is True, when true it disable any error notifications (but not debug messages)
	# hideResponse: used to not output the json response to the log
	def traktRequest(self, method, url, args=None, returnStatus=False, returnOnFailure=False, silent=True, hideResponse=False):
		raw = None
		data = None
		jdata = {}
		retries = getSettingAsInt('retries')

		if args is None:
			args = {}

		if not (method == 'POST' or method == 'GET' or method == 'PUT' or method == 'DELETE'):
			Debug("[traktAPI] traktRequest(): Unknown method '%s'." % method)
			return None

		# debug log before username and sha1hash are injected
		Debug("[traktAPI] traktRequest(): Request data: '%s'." % str(json.dumps(args)))

		# convert to json data
		jdata = json.dumps(args)

		Debug("[traktAPI] traktRequest(): Starting retry loop, maximum %i retries." % retries)

		# start retry loop
		for i in range(retries):
			Debug("[traktAPI] traktRequest(): (%i) Request URL '%s'" % (i, url))

			# check if we are closing
			if xbmc.abortRequested:
				Debug("[traktAPI] traktRequest(): (%i) xbmc.abortRequested" % i)
				break

			try:
				# get data from trakt.tv
				raw = self.__getData(url, jdata, method)
			except traktError, e:
				if isinstance(e, traktServerBusy):
					Debug("[traktAPI] traktRequest(): (%i) Server Busy (%s)" % (i, e.value))
					xbmc.sleep(5000)
				elif isinstance(e, traktAuthProblem):
					Debug("[traktAPI] traktRequest(): (%i) Authentication Failure (%s)" % (i, e.value))
					setSetting('account_valid', False)
					notification('trakt', getString(1110))
					return
				elif isinstance(e, traktNetworkError):
					Debug("[traktAPI] traktRequest(): (%i) Network error: %s" % (i, e.value))
					if e.timeout:
						notification('trakt', getString(1108) + " (timeout)") # can't connect to trakt
					xbmc.sleep(5000)
				elif isinstance(e, traktUnknownError):
					Debug("[traktAPI] traktRequest(): (%i) Other problem (%s)" % (i, e.value))
				else:
					pass

				xbmc.sleep(1000)
				continue

			# check if we are closing
			if xbmc.abortRequested:
				Debug("[traktAPI] traktRequest(): (%i) xbmc.abortRequested" % i)
				break

			# check that returned data is not empty
			if not raw:
				Debug("[traktAPI] traktRequest(): (%i) JSON Response empty" % i)
				xbmc.sleep(1000)
				continue

			try:
				# get json formatted data
				data = json.loads(raw)
				if hideResponse:
					Debug("[traktAPI] traktRequest(): (%i) JSON response recieved, response not logged" % i)
				else:
					Debug("[traktAPI] traktRequest(): (%i) JSON response: '%s'" % (i, str(data)))
			except ValueError:
				# malformed json response
				Debug("[traktAPI] traktRequest(): (%i) Bad JSON response: '%s'" % (i, raw))
				if not silent:
					notification('trakt', getString(1109) + ": Bad response from trakt") # Error

			# check for the status variable in JSON data
			if data and 'status' in data:
				if data['status'] == 'success':
					break
				elif returnOnFailure and data['status'] == 'failure':
					Debug("[traktAPI] traktRequest(): Return on error set, breaking retry.")
					break
				elif 'error' in data and data['status'] == 'failure':
					Debug("[traktAPI] traktRequest(): (%i) JSON Error '%s' -> '%s'" % (i, data['status'], data['error']))
					xbmc.sleep(1000)
					continue
				else:
					pass

			# check to see if we have data, an empty array is still valid data, so check for None only
			if not data is None:
				Debug("[traktAPI] traktRequest(): Have JSON data, breaking retry.")
				break

			xbmc.sleep(500)

		# handle scenario where all retries fail
		if data is None:
			Debug("[traktAPI] traktRequest(): JSON Request failed, data is still empty after retries.")
			return None

		if 'status' in data:
			if data['status'] == 'failure':
				Debug("[traktAPI] traktRequest(): Error: %s" % str(data['error']))
				if returnStatus or returnOnFailure:
					return data
				if not silent:
					notification('trakt', getString(1109) + ": " + str(data['error'])) # Error
				return None
			elif data['status'] == 'success':
				Debug("[traktAPI] traktRequest(): JSON request was successful.")

		return data

	# helper for onSettingsChanged
	def updateSettings(self):

		_username = getSetting('username')
		_password = getSetting('password')

		if not ((self.__username == _username)):
			self.__username = _username

		if not ((self.__password == _password)):
			self.__password = _password			


	# url: https://api.trakt.tv/scrobble/<status>
	def scrobble(self, data, status):
			url = "%s/scrobble/%s" % (self.__baseURL, status)
			Debug("[traktAPI] scrobble(url: %s, data: %s)" % (url, str(data)))
			if getSettingAsBool('simulate_scrobbling'):
				Debug("[traktAPI] Simulating response.")
				return {'status': 'success'}
			else:
				return self.traktRequest('POST', url, data, returnOnFailure=True)

	def scrobbleEpisode(self, info, percent, status):
		data = { 'show': {'title': info['showtitle'], 'year': info['year']}, 'episode': { 'season': info['season'], 'number': info['episode']}, 'progress': math.ceil(percent)}
		if 'uniqueid' in info:
			data['episode_tvdb_id'] = info['uniqueid']['unknown']
		return self.scrobble(data, status)
	def scrobbleMovie(self, info, percent, status):
		data = { 'movie': { 'ids': {'imdb': info['imdbnumber']}, 'title': info['title'], 'year': info['year']}, 'progress': math.ceil(percent)}
		return self.scrobble(data, status)

	# url: https://api.trakt.tv/sync/collection/<type>
	# note: if user has nothing in collection, response is then []
	def getCollection(self, type):
			url = "%s/sync/collection/%s" % (self.__baseURL, type)
			Debug("[traktAPI] getCollection(url: %s)" % url)
			return self.traktRequest('GET', url)

	def getShowCollection(self):
		return self.getCollection('shows')
	def getMovieCollection(self):
		return self.getCollection('movies')

	# url: https://api.trakt.tv/sync/watched/<type>
	# note: if nothing watched in collection, returns []
	def getWatchedLibrary(self, type):
			url = "%s/sync/watched/%s" % (self.__baseURL, self.__username, type)
			Debug("[traktAPI] getWatchedLibrary(url: %s)" % url)
			return self.traktRequest('GET', url)

	def getWatchedEpisodeLibrary(self,):
		return self.getWatchedLibrary('shows')
	def getWatchedMovieLibrary(self):
		return self.getWatchedLibrary('movies')

	# url: https://api.trakt.tv/sync/collection
	def addToCollection(self, type, data):
			url = "%s/sync/collection" % (self.__baseURL)
			Debug("[traktAPI] addToCollection(url: %s, data: %s)" % (url, str(data)))
			return self.traktRequest('POST', url, data)

	def addEpisode(self, data):
		return self.addToCollection('show/episode', data)
	def addShow(self, data):
		return self.addToCollection('show', data)
	def addMovie(self, data):
		return self.addToCollection('movie', data)

	# url: https://api.trakt.tv/sync/collection/remove
	def removeFromCollection(self, type, data):
			url = "%s/sync/collection/remove" % (self.__baseURL)
			Debug("[traktAPI] removeFromCollection(url: %s, data: %s)" % (url, str(data)))
			return self.traktRequest('POST', url, data)

	def removeEpisode(self, data):
		return self.removeFromCollection('show/episode', data)
	def removeShow(self, data):
		return self.removeFromCollection('show', data)
	def removeMovie(self, data):
		return self.removeFromCollection('movie', data)

	# url: https://api.trakt.tv/sync/history
	# returns: {u'status': u'success', u'message': u'2 episodes marked as seen'}
	def updateSeenInLibrary(self, type, data):
			url = "%s/sync/history" % (self.__baseURL)
			Debug("[traktAPI] updateSeenInLibrary(url: %s, data: %s)" % (url, str(data)))
			return self.traktRequest('POST', url, data)

	def updateSeenEpisode(self, data):
		return self.updateSeenInLibrary('show/episode', data)
	def updateSeenShow(self, data):
		return self.updateSeenInLibrary('show', data)
	def updateSeenMovie(self, data):
		return self.updateSeenInLibrary('movie', data)

	def getShowSummary(self, id):
		url = "%s/shows/%s" % (self.__baseURL, id)
		Debug("[traktAPI] getShowSummary(url: %s)" % (url))
		result = self.traktRequest('GET', url)
		result['user'] = {}
		result['user']['ratings'] = self.getShowRatingForUser(id)
		return result
	def getEpisodeSummary(self, id, season, episode):
		url = "%s/shows/%s/seasons/%s/episodes/%s" % (self.__baseURL, id, season, episode)
		Debug("[traktAPI] getEpisodeSummary(url: %s)" % (url))
		result = self.traktRequest('GET', url)
		result['user'] = {}
		result['user']['ratings'] = self.getEpisodeRatingForUser(id, season, episode)
		return result
	def getMovieSummary(self, id):
		url = "%s/movies/%s" % (self.__baseURL, id)
		Debug("[traktAPI] getMovieSummary(url: %s)" % (url))
		result = self.traktRequest('GET', url)
		result['user'] = {}
		result['user']['ratings'] = self.getMovieRatingForUser(id)
		return result

	def getShowRatingForUser(self, id):
		ratings = self.getRatedShows()
		return findShowMatchInList(id, ratings)
	def getEpisodeRatingForUser(self, id, season, episode):
		ratings = self.getRatedShows()
		return findEpisodeMatchInList(id, season, episode, ratings, 'rating')
	def getMovieRatingForUser(self, id):
		ratings = self.getRatedMovies()
		return findMovieMatchInList(id, ratings)

	def getShowWatchedForUser(self, id):
		watched = self.getWatchedEpisodeLibrary()
		return findShowMatchInList(id, watched)
	def getEpisodeWatchedForUser(self, id, season, episode):
		watched = self.getWatchedEpisodeLibrary()
		return findEpisodeMatchInList(id, season, episode, watched, 'watched')	
	def getMovieWatchedForUser(self, id):
		watched = self.getWatchedMovieLibrary()
		return findMovieMatchInList(id, watched)		

			

	# url: https://api.trakt.tv/shows/<id>/seasons/<season>
	# returns: returns detailed episode info for a specific season of a show.
	def getSeasonInfo(self, id, season):
		url = "%s/shows/%s/seasons/%s" % (self.__baseURL, id, season)
		return self.getSummary(url)

	# url: https://api.trakt.tv/sync/ratings
	def rate(self, type, data):

			url = "%s/sync/ratings" % (self.__baseURL)
			Debug("[traktAPI] rate(url: %s, data: %s)" % (url, str(data)))
			return self.traktRequest('POST', url, data)

	def rateShow(self, data):
		return self.rate('shows', data)
	def rateEpisode(self, data):
		return self.rate('episodes', data)
	def rateMovie(self, data):
		return self.rate('movies', data)

	# url:https://api.trakt.tv/users/<username>/lists
	# returns: Returns all custom lists for a user.
	def getUserLists(self):
			url = "%s/users/%s/lists" % (self.__baseURL, self.__username)
			Debug("[traktAPI] getUserLists(url: %s)" % url)
			return self.traktRequest('GET', url)

	# url: https://api.trakt.tv/users/<username>/lists/<id>/items
	# returns: Returns list details and all items it contains.
	def getUserList(self, data):
			url = "%s/users/%s/lists/%s" % (self.__baseURL, self.__username, data)
			Debug("[traktAPI] getUserList(url: %s)" % url)
			return self.traktRequest('GET', url)

	def userListAdd(self, list_name, privacy, description=None, allow_shouts=False, show_numbers=False):
		#TODO not yet on trakt
		data = {'name': list_name, 'show_numbers': show_numbers, 'allow_shouts': allow_shouts, 'privacy': privacy}
		if description:
			data['description'] = description
		return self.userList('add', data)
	def userListDelete(self, slug_name):
		url = "%s/users/%s/lists/%s" % (self.__baseURL, self.__username, slug_name)
		Debug("[traktAPI] userList(url: %s, data: %s)" % (url, str(data)))
		return self.traktRequest('DELETE', url)
	def userListUpdate(self, data, slug_name):
		url = "%s/users/%s/lists/%s" % (self.__baseURL, self.__username, slug_name)
		Debug("[traktAPI] userList(url: %s, data: %s)" % (url, str(data)))
		return self.traktRequest('PUT', url, data)

	def userListItemAdd(self, data):
		url = "%s/users/%s/lists/%s/items" % (self.__baseURL, self.__username, slug_name)
		Debug("[traktAPI] userList(url: %s, data: %s)" % (url, str(data)))
		return self.traktRequest('POST', url, data)
	def userListItemDelete(self, data):
		url = "%s/users/%s/lists/%s/items/remove" % (self.__baseURL, self.__username, slug_name)
		Debug("[traktAPI] userList(url: %s, data: %s)" % (url, str(data)))
		return self.traktRequest('POST', url, data)

	# url: https://api.trakt.tv/sync/watchlist/<type>
	# note: if nothing in list, returns []
	def getWatchlist(self, type):
			url = "%s/sync/watchlist/%s" % (self.__baseURL, type)
			Debug("[traktAPI] getWatchlist(url: %s)" % url)
			return self.traktRequest('GET', url)

	def getWatchlistShows(self):
		return self.getWatchlist('shows')
	def getWatchlistMovies(self):
		return self.getWatchlist('movies')

	# url: https://api.trakt.tv/sync/watchlist
	# returns:
	def watchlistAddItems(self, data):
			url = "%s/sync/watchlist" % (self.__baseURL)
			Debug("[traktAPI] watchlistAddItem(url: %s)" % url)
			return self.traktRequest('POST', url, data)

	def watchlistAddShows(self, data):
		return self.watchlistAddItems(data)
	def watchlistAddMovies(self, data):
		return self.watchlistAddItems(data)

	# url: https://api.trakt.tv/sync/watchlist/remove
	# returns:
	def watchlistRemoveItems(self, data):
			url = "%s/sync/watchlist/remove" % (self.__baseURL)
			Debug("[traktAPI] watchlistRemoveItems(url: %s)" % url)
			return self.traktRequest('POST', url, data)

	def watchlistRemoveShows(self, data):
		return self.watchlistRemoveItems(data)
	def watchlistRemoveMovies(self, data):
		return self.watchlistRemoveItems(data)

	# url: https://api.trakt.tv/sync/ratings/<type>
	# note: if no items, returns []
	def getRatedItems(self, type):
			url = "%s/sync/ratings/%s" % (self.__baseURL, type)
			Debug("[traktAPI] getRatedItems(url: %s)" % url)
			return self.traktRequest('GET', url)

	def getRatedMovies(self):
		return self.getRatedItems('movies')
	def getRatedShows(self):
		return self.getRatedItems('shows')
	def getRatedEpisodes(self):
		return self.getRatedItems('episodes')		
