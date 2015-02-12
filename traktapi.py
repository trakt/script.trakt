# -*- coding: utf-8 -*-
#
import xbmcaddon
import math
import logging

from trakt import Trakt, ClientError, ServerError
from utilities import Debug, getSetting, findMovieMatchInList, findEpisodeMatchInList, notification, getString

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')

class traktAPI(object):

	__apikey = "d4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868"
	__token = ""
	__username = ""
	__password = ""

	def __init__(self):
		Debug("[traktAPI] Initializing.")

		# Get user login data
		self.__username = getSetting('username')
		self.__password = getSetting('password')
		self.__token = getSetting('token')

		# Configure
		logging.basicConfig(level=logging.INFO)
		Trakt.configuration.defaults.client(
			id=self.__apikey
		)

		if not self.__token:
			self.getToken()

	# helper for onSettingsChanged
	def updateSettings(self):

		_username = getSetting('username')
		_password = getSetting('password')

		if not (self.__username == _username):
			self.__username = _username

		if not (self.__password == _password):
			self.__password = _password

		self.getToken()

	def getToken(self):
		if not self.__username and not self.__password:

			notification('trakt', getString(1106)) #Sync started
		elif not self.__password:
			notification('trakt', getString(1107)) #Sync started
		else:
			# Attempt authentication (retrieve new token)
			with Trakt.configuration.http(retry=True):
				auth = Trakt['auth'].login(getSetting('username'), getSetting('password'))
				if auth:
					self.__token = auth
				else:
					Debug("[traktAPI] Authentication Failure")
					notification('trakt', getString(1110))


	def scrobbleEpisode(self, show, episode, percent, status):
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
		result = None

		with Trakt.configuration.auth(self.__username, self.__token):
			if status == 'start':
				result = Trakt['scrobble'].start(
					movie=movie,
					progress=math.ceil(percent))
			elif status == 'pause':
				result = Trakt['scrobble'].pause(
					movie=movie,
					progress=math.ceil(percent))
			elif status == 'stop':
				result = Trakt['scrobble'].stop(
					movie=movie,
					progress=math.ceil(percent))
			else:
				Debug("[traktAPI] scrobble() Bad scrobble status")
		return result

	def getShowsCollected(self, shows):
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/collection'].shows(shows, exceptions=True)
		return shows

	def getMoviesCollected(self, movies):
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/collection'].movies(movies, exceptions=True)
		return movies


	def getShowsWatched(self, shows):
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/watched'].shows(shows, exceptions=True)
		return shows

	def getMoviesWatched(self, movies):
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/watched'].movies(movies, exceptions=True)
		return movies

	def addToCollection(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/collection'].add(mediaObject)
		return result

	def removeFromCollection(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/collection'].remove(mediaObject)
		return result

	def addToHistory(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/history'].add(mediaObject)
		return result

	def getEpisodeRatingForUser(self, tvdbId, season, episode):
		ratings = {}
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/ratings'].episodes(ratings)
		return findEpisodeMatchInList(tvdbId, season, episode, ratings)

	def getMovieRatingForUser(self, imdbId):
		ratings = {}
		with Trakt.configuration.auth(self.__username, self.__token):
			with Trakt.configuration.http(retry=True):
				Trakt['sync/ratings'].movies(ratings)
		return findMovieMatchInList(imdbId, ratings)

	# Send a rating to trakt as mediaObject so we can add the rating
	def addRating(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/ratings'].add(mediaObject)
		return result

	# Send a rating to trakt as mediaObject so we can remove the rating
	def removeRating(self, mediaObject):
		with Trakt.configuration.auth(self.__username, self.__token):
			result = Trakt['sync/ratings'].remove(mediaObject)
		return result