# -*- coding: utf-8 -*-
#
import xbmcaddon

from trakt import Trakt
from utilities import Debug, notification, getSetting, getSettingAsBool, getSettingAsInt, getString, setSetting

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')
__addonversion__ = __addon__.getAddonInfo('version')


class traktAPI(object):

	def __init__(self, loadSettings=False):
		Debug("[traktAPI] Initializing.")

		# Get user login data
		self.__username = getSetting('username')
		self.__password = getSetting('password')
		self.__token = getSetting('token')

		# Configure
		Trakt.configuration.defaults.client(
		    id='d4161a7a106424551add171e5470112e4afdaf2438e6ef2fe0548edc75924868'
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
		self.__token = Trakt['auth'].login(self.__username, self.__password)			



	def scrobbleEpisode(self, info, percent, status):
		show = { 'show': {'title': info['showtitle'], 'year': info['year']} }
		episode = { 'episode': { 'season': info['season'], 'number': info['episode'], 'ids': {}} }
		if 'uniqueid' in info:
			data['ids']['tvdb'] = info['uniqueid']['unknown']
			Debug("[traktAPI] scrobble(data: %s)" % (url, str(data)))


			return
			with Trakt.configuration.auth(self.__username, self.__token):
				if status == 'start':
					Trakt['scrobble'].start(
						show=show,
						episode=episode,
						progress=math.ceil(percent))	
				elif status == 'pause':
					Trakt['scrobble'].pause(
						show=show,
						episode=episode,
						progress=math.ceil(percent))	
				elif status == 'stop':
					Trakt['scrobble'].stop(
						show=show,
						episode=episode,
						progress=math.ceil(percent))	
				else:
					Debug("[traktAPI] scrobble() Bad scrobble status")				

	def scrobbleMovie(self, info, percent, status):
		movie = { 'movie': { 'ids': {'imdb': info['imdbnumber']}, 'title': info['title'], 'year': info['year']} }
		Debug("[traktAPI] scrobble(data: %s)" % (str(movie)))

		return 
		with Trakt.configuration.auth(self.__username, self.__token):
			if status == 'start':
				Trakt['scrobble'].start(
					movie=movie,
					progress=math.ceil(percent))	
			elif status == 'pause':
				Trakt['scrobble'].pause(
					movie=movie,
					progress=math.ceil(percent))	
			elif status == 'stop':
				Trakt['scrobble'].stop(
					movie=movie,
					progress=math.ceil(percent))	
			else:
				Debug("[traktAPI] scrobble() Bad scrobble status")

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

