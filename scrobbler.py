# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import threading
import time

import utilities
from utilities import Debug, get_float_setting
from rating import ratingCheck

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

class Scrobbler(threading.Thread):

	traktapi = None
	totalTime = 1
	watchedTime = 0
	startTime = 0
	pausedTime = 0
	curVideo = None
	curVideoData = None
	pinging = False
	playlistLength = 1
	abortRequested = False
	markFirstAsWatched = False

	def __init__(self, api):
		threading.Thread.__init__(self)
		self.traktapi = api
		self.start()

	def run(self):
		# When requested ping trakt to say that the user is still watching the item
		count = 0
		Debug("[Scrobbler] Starting.")
		while (not (self.abortRequested or xbmc.abortRequested)):
			xbmc.sleep(5000) # sleep for 5 seconds
			if self.pinging and xbmc.Player().isPlayingVideo():
				count += 1
				self.watchedTime = xbmc.Player().getTime()
				self.startTime = time.time()
				if count >= 100:
					self.watching()
					count = 0
			else:
				count = 0

		Debug("[Scrobbler] Stopping.")

	def playbackStarted(self, data):
		Debug("[Scrobbler] playbackStarted(data: %s)" % data)
		if self.curVideo != None and self.curVideo != data['item']:
			self.playbackEnded()
		self.curVideo = data['item']
		self.curVideoData = data
		if self.curVideo != None:
			# {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"item":{"type":"movie"},"player":{"playerid":1,"speed":1},"title":"Shooter","year":2007},"sender":"xbmc"}}
			# {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"episode":3,"item":{"type":"episode"},"player":{"playerid":1,"speed":1},"season":4,"showtitle":"24","title":"9:00 A.M. - 10:00 A.M."},"sender":"xbmc"}}
			if 'type' in self.curVideo: #and 'id' in self.curVideo:
				Debug("[Scrobbler] Watching: "+self.curVideo['type']) #+" - "+str(self.curVideo['id']))
				try:
					if not xbmc.Player().isPlayingVideo():
						Debug("[Scrobbler] Suddenly stopped watching item")
						return
					time.sleep(1) # Wait for possible silent seek (caused by resuming)
					self.watchedTime = xbmc.Player().getTime()
					self.totalTime = xbmc.Player().getTotalTime()
					self.markFirstAsWatched = False
					if self.totalTime == 0:
						if self.curVideo['type'] == 'movie':
							self.totalTime = 90
						elif self.curVideo['type'] == 'episode':
							self.totalTime = 30
						else:
							self.totalTime = 1
					#self.playlistLength = utilities.getPlaylistLengthFromXBMCPlayer(data['player']['playerid'])
					# playerid 1 is video.
					self.playlistLength = utilities.getPlaylistLengthFromXBMCPlayer(1)
					if (self.playlistLength == 0):
						Debug("[Scrobbler] Warning: Cant find playlist length?!, assuming that this item is by itself")
						self.playlistLength = 1
				except Exception, e:
					Debug("[Scrobbler] Suddenly stopped watching item, or error: %s" % e.message)
					self.curVideo = None
					self.startTime = 0
					return
				self.startTime = time.time()
				self.watching()
				self.pinging = True
			else:
				self.curVideo = None
				self.startTime = 0

	def playbackResumed(self):
		Debug("[Scrobbler] playbackResumed()")
		if self.pausedTime != 0:
			p = time.time() - self.pausedTime
			Debug("[Scrobbler] Resumed after: %s" % str(p))
			self.pausedTime = 0
			self.watching()

	def playbackPaused(self):
		Debug("[Scrobbler] playbackPaused()")
		if self.startTime != 0:
			self.watchedTime += time.time() - self.startTime
			Debug("[Scrobbler] Paused after: "+str(self.watchedTime))
			self.startTime = 0
			self.pausedTime = time.time()

	def playbackSeek(self):
		Debug("[Scrobbler] playbackSeek()")
		if self.startTime != 0:
			self.watchedTime = xbmc.Player().getTime()
			self.startTime = time.time()

	def playbackEnded(self):
		Debug("[Scrobbler] playbackEnded()")
		if self.startTime != 0:
			if self.curVideo == None:
				Debug("[Scrobbler] Warning: Playback ended but video forgotten")
				return
			self.watchedTime += time.time() - self.startTime
			self.pinging = False
			self.markFirstAsWatched = False
			if self.watchedTime != 0:
				if 'type' in self.curVideo: #and 'id' in self.curVideo:
					self.check()
					ratingCheck(self.curVideo, self.watchedTime, self.totalTime, self.playlistLength)
				self.watchedTime = 0
			self.startTime = 0
			self.curVideo = None

	def watching(self):
		Debug("[Scrobbler] watching()")
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			match = None
			if 'id' in self.curVideo:
				match = utilities.getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber', 'title', 'year'])
			elif 'title' in self.curVideoData and 'year' in self.curVideoData:
				match = {}
				match['imdbnumber'] = ''
				match['title'] = self.curVideoData['title']
				match['year'] = self.curVideoData['year']
			if match == None:
				return
			
			duration = self.totalTime / 60
			watchedPercent = int((self.watchedTime / self.totalTime) * 100)
			response = self.traktapi.watchingMovie(match['imdbnumber'], match['title'], match['year'], duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response))
				
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = None
			if 'id' in self.curVideo:
				if self.curVideo.has_key("doubleep") and ((self.watchedTime / self.totalTime) * 100 >= 50):
					if not self.markFirstAsWatched:
						# force a scrobble of the first episode
						Debug("[Scrobbler] Attempting to mark first episode in a double episode as watched.")
						firstEP = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
						response = self.traktapi.scrobbleEpisode(firstEP['tvdb_id'], firstEP['showtitle'], firstEP['year'], firstEP['season'], firstEP['episode'], firstEP['uniqueid']['unknown'], self.totalTime/60, 100)
						if response != None:
							Debug("[Scrobbler] Scrobble response: %s" % str(response))
						self.markFirstAsWatched = True
					
					Debug("[Scrobbler] Double episode, into 2nd part now.")
					match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['doubleep'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
				else:
					match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
			elif 'showtitle' in self.curVideoData and 'season' in self.curVideoData and 'episode' in self.curVideoData:
				match = {}
				match['tvdb_id'] = None
				match['year'] = None
				match['showtitle'] = self.curVideoData['showtitle']
				match['season'] = self.curVideoData['season']
				match['episode'] = self.curVideoData['episode']
				match['uniqueid'] = self.curVideoData['uniqueid']['unknown']
			if match == None:
				return
				
			duration = self.totalTime / 60
			watchedPercent = int((self.watchedTime / self.totalTime) * 100)
			response = self.traktapi.watchingEpisode(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], match['uniqueid']['unknown'], duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response))

	def stoppedWatching(self):
		Debug("[Scrobbler] stoppedWatching()")
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			response = self.traktapi.cancelWatchingMovie()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			response = self.traktapi.cancelWatchingEpisode()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))

	def scrobble(self):
		Debug("[Scrobbler] scrobble()")
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			match = None
			if 'id' in self.curVideo:
				match = utilities.getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber', 'title', 'year'])
			elif 'title' in self.curVideoData and 'year' in self.curVideoData:
				match = {}
				match['imdbnumber'] = ''
				match['title'] = self.curVideoData['title']
				match['year'] = self.curVideoData['year']
			if match == None:
				return

			duration = self.totalTime / 60
			watchedPercent = int((self.watchedTime / self.totalTime) * 100)
			response = self.traktapi.scrobbleMovie(match['imdbnumber'], match['title'], match['year'], duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response))

		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = None
			if 'id' in self.curVideo:
				if self.curVideo.has_key("doubleep"):
					Debug("[Scrobbler] Double episode, scrobbling 2nd part.")
					match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['doubleep'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
				else:
					match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
			elif 'showtitle' in self.curVideoData and 'season' in self.curVideoData and 'episode' in self.curVideoData:
				match = {}
				match['tvdb_id'] = None
				match['year'] = None
				match['showtitle'] = self.curVideoData['showtitle']
				match['season'] = self.curVideoData['season']
				match['episode'] = self.curVideoData['episode']
				match['uniqueid'] = self.curVideoData['uniqueid']['unknown']
			if match == None:
				return
			
			duration = self.totalTime / 60
			watchedPercent = int((self.watchedTime / self.totalTime) * 100)
			response = self.traktapi.scrobbleEpisode(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], match['uniqueid']['unknown'], duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response))

	def check(self):
		scrobbleMinViewTimeOption = get_float_setting("scrobble_min_view_time")

		Debug("[Scrobbler] watched: %s / %s" % (str(self.watchedTime), str(self.totalTime)))
		if ((self.watchedTime / self.totalTime) * 100) >= scrobbleMinViewTimeOption:
			self.scrobble()
		else:
			self.stoppedWatching()
