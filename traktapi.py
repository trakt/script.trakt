# -*- coding: utf-8 -*-
#
import xbmc
import xbmcaddon
import time, socket
import math
import urllib2
import logging

from trakt import Trakt
from utilities import Debug, notification, getSetting, getSettingAsBool, getSettingAsInt, getString, setSetting, findMovieMatchInList, findShowMatchInList, findEpisodeMatchInList
from urllib2 import Request, urlopen, HTTPError, URLError
from httplib import HTTPException, BadStatusLine

try:
	import simplejson as json
except ImportError:
	import json

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')

#TODO remove when moving to new wrapper
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

	__baseURL = "https://api.trakt.tv"
	__apikey = "d4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868"
	__token = ""
	__username = ""
	__password = ""

	def __init__(self):
		logging.basicConfig()
		Debug("[traktAPI] Initializing.")

		# Get user login data
		self.__username = getSetting('username')
		self.__password = getSetting('password')
		self.__token = getSetting('token')

		# Configure
		Trakt.configuration.defaults.client(
		    id=self.__apikey
		)

		if not self.__token:
			self.getToken()

	# helper for onSettingsChanged
	def updateSettings(self):

		_username = getSetting('username')
		_password = getSetting('password')

		if not ((self.__username == _username)):
			self.__username = _username

		if not ((self.__password == _password)):
			self.__password = _password

		self.getToken()

	def getToken(self):
		# Attempt authentication (retrieve new token)
		self.__token = Trakt['auth'].login(getSetting('username'), getSetting('password'))


	def scrobbleEpisode(self, show, episode, percent, status):
		Debug('show info %s' % show)
		Debug('episode info %s' % episode)
		if episode.get('user'):
			del episode['user']


		result = None

		with Trakt.configuration.auth(self.__username, self.__token):
			if status == 'start':
				result =Trakt['scrobble'].start(
					show=show,
					episode=episode,
					progress=math.ceil(percent))
			elif status == 'pause':
				result = Trakt['scrobble'].pause(
					show=show,
					episode=episode,
					progress=math.ceil(percent))
			elif status == 'stop':
				result = Trakt['scrobble'].stop(
					show=show,
					episode=episode,
					progress=math.ceil(percent))
			else:
					Debug("[traktAPI] scrobble() Bad scrobble status")
		return result


	def scrobbleMovie(self, movie, percent, status):

		Debug("[traktAPI] scrobble(data: %s)" % (str(movie)))

		result = None
		with Trakt.configuration.auth(self.__username, self.__token):
			if status == 'start':
				Debug("[traktAPI] scrobble() Start")
				result = Trakt['scrobble'].start(
					movie=movie,
					progress=math.ceil(percent))
			elif status == 'pause':
				Debug("[traktAPI] scrobble() Pause")
				result = Trakt['scrobble'].pause(
					movie=movie,
					progress=math.ceil(percent))
			elif status == 'stop':
				Debug("[traktAPI] scrobble() Stop")
				result = Trakt['scrobble'].stop(
					movie=movie,
					progress=math.ceil(percent))
			else:
				Debug("[traktAPI] scrobble() Bad scrobble status")
		Debug("[traktAPI] scrobble() %s" % result)				
		return result

	def getShowsLibrary(self, shows):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/collection'].shows(shows)
		return shows

	def getMoviesLibrary(self, movies):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/collection'].movies(movies)
		return movies


	def getShowsWatched(self, shows):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/watched'].shows(shows)
		return shows

	def getMoviesWatched(self, movies):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/watched'].movies(movies)
		return movies

	def getShowsRated(self, shows):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/ratings'].shows(shows)
		return shows

	def getEpisodesRated(self, episodes):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/ratings'].episodes(episodes)
		return episodes

	def getMoviesRated(self, movies):
		with Trakt.configuration.auth(self.__username, self.__token):
				Trakt['sync/ratings'].movies(movies)
		return movies

	def addToCollection(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/collection'].add(mediaObject)
		return result

	def removeFromCollection(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/collection'].remove(mediaObject)
		return result



    #TODO move this to the new api wrapper


	def __getData(self, url, args, method, timeout=60):
		data = None
		try:
			Debug("[traktAPI] __getData(): urllib2.Request(%s)" % url)

			headers = {'trakt-user-login': self.__username,
						'trakt-user-token': self.__token,
						'Content-type': 'application/json',
						'trakt-api-key': self.__apikey,
						'trakt-api-version': '2'
						}
			if args == None:
				req = Request(url, headers)
			else:
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

		except BadStatusLine as e:
			raise traktUnknownError("BadStatusLine: '%s' from URL: '%s'" % (e.line, url))
		except IOError as e:
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
			except traktError as e:
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
		ratings = self.getRatedItems('shows')
		return findShowMatchInList(id, ratings)
	def getEpisodeRatingForUser(self, id, season, episode):
		ratings = self.getRatedItems('episodes')
		return findEpisodeMatchInList(id, season, episode, ratings, 'rating')
	def getMovieRatingForUser(self, id):
		ratings = self.getRatedItems('movies')
		return findMovieMatchInList(id, ratings)

	# url: https://api.trakt.tv/sync/ratings/<type>
	# note: if no items, returns []
	def getRatedItems(self, type):
			url = "%s/sync/ratings/%s" % (self.__baseURL, type)
			Debug("[traktAPI] getRatedItems(url: %s)" % url)
			return self.traktRequest('GET', url)					

    # url: http://api.trakt.tv/sync/ratings
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

	def getIdLookup(self, idType, id):
		url = "%s/search?id_type=%s&id=%s" % (self.__baseURL, idType, id)
		Debug("[traktAPI] getIdLookup(url: %s)" % url)
		lookup = self.traktRequest('GET', url)
		return lookup[0][lookup[0]['type']]

