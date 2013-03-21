# -*- coding: utf-8 -*-
#

import xbmc
import time

import utilities
from utilities import Debug
from rating import ratingCheck

class Scrobbler():

	traktapi = None
	isPlaying = False
	isPaused = False
	isMultiPartEpisode = False
	lastMPCheck = 0
	curMPEpisode = 0
	videoDuration = 1
	watchedTime = 0
	pausedAt = 0
	curVideo = None
	curVideoInfo = None
	playlistLength = 1
	markedAsWatched = []
	traktSummaryInfo = None

	def __init__(self, api):
		self.traktapi = api

	def _currentEpisode(self, watchedPercent, episodeCount):
		split = (100 / episodeCount)
		for i in range(episodeCount - 1, 0, -1):
			if watchedPercent >= (i * split):
				return i
		return 0

	def update(self, forceCheck = False):
		if self.isPlaying and not self.isPaused:
			self.watchedTime = xbmc.Player().getTime()

			if self.isMultiPartEpisode:
				# do transition check every minute
				if (time.time() > (self.lastMPCheck + 60)) or forceCheck:
					self.lastMPCheck = time.time()
					watchedPercent = (self.watchedTime / self.videoDuration) * 100
					epIndex = self._currentEpisode(watchedPercent, self.curVideo['multi_episode_count'])
					if self.curMPEpisode != epIndex:
						# current episode in multi-part episode has changed
						Debug("[Scrobbler] Attempting to scrobble episode part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))

						# recalculate watchedPercent and duration for multi-part, and scrobble
						adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
						duration = adjustedDuration / 60
						watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100
						response = self.traktapi.scrobbleEpisode(self.curVideoInfo, duration, watchedPercent)
						if response != None:
							Debug("[Scrobbler] Scrobble response: %s" % str(response))

						# update current information
						self.curMPEpisode = epIndex
						self.curVideoInfo = utilities.getEpisodeDetailsFromXbmc(self.curVideo['multi_episode_data'][self.curMPEpisode], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])

						if not forceCheck:
							self.watching()

	def playbackStarted(self, data):
		Debug("[Scrobbler] playbackStarted(data: %s)" % data)
		if self.curVideo != None and self.curVideo != data:
			self.playbackEnded()
		if not data:
			return
		self.curVideo = data
		self.curVideoInfo = None
		# {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"item":{"type":"movie"},"player":{"playerid":1,"speed":1},"title":"Shooter","year":2007},"sender":"xbmc"}}
		# {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"episode":3,"item":{"type":"episode"},"player":{"playerid":1,"speed":1},"season":4,"showtitle":"24","title":"9:00 A.M. - 10:00 A.M."},"sender":"xbmc"}}
		if 'type' in self.curVideo:
			Debug("[Scrobbler] Watching: %s" % self.curVideo['type'])
			if not xbmc.Player().isPlayingVideo():
				Debug("[Scrobbler] Suddenly stopped watching item")
				return
			xbmc.sleep(1000) # Wait for possible silent seek (caused by resuming)
			try:
				self.watchedTime = xbmc.Player().getTime()
				self.videoDuration = xbmc.Player().getTotalTime()
			except Exception, e:
				Debug("[Scrobbler] Suddenly stopped watching item: %s" % e.message)
				self.curVideo = None
				return

			if self.videoDuration == 0:
				if utilities.isMovie(self.curVideo['type']):
					self.videoDuration = 90
				elif utilities.isEpisode(self.curVideo['type']):
					self.videoDuration = 30
				else:
					self.videoDuration = 1

			self.playlistLength = len(xbmc.PlayList(xbmc.PLAYLIST_VIDEO))
			if (self.playlistLength == 0):
				Debug("[Scrobbler] Warning: Cant find playlist length, assuming that this item is by itself")
				self.playlistLength = 1

			self.traktSummaryInfo = None
			self.isMultiPartEpisode = False
			if utilities.isMovie(self.curVideo['type']):
				if 'id' in self.curVideo:
					self.curVideoInfo = utilities.getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber', 'title', 'year'])
					if utilities.getSettingAsBool('rate_movie'):
						# pre-get sumamry information, for faster rating dialog.
						self.traktSummaryInfo = self.traktapi.getMovieSummary(self.curVideoInfo['imdbnumber'])
				elif 'title' in self.curVideo and 'year' in self.curVideo:
					self.curVideoInfo = {}
					self.curVideoInfo['imdbnumber'] = ''
					self.curVideoInfo['title'] = self.curVideo['title']
					self.curVideoInfo['year'] = self.curVideo['year']

			elif utilities.isEpisode(self.curVideo['type']):
				if 'id' in self.curVideo:
					self.curVideoInfo = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
					if utilities.getSettingAsBool('rate_episode'):
						# pre-get sumamry information, for faster rating dialog.
						self.traktSummaryInfo = self.traktapi.getShowSummary(self.curVideoInfo['tvdb_id'], self.curVideoInfo['season'], self.curVideoInfo['episode'])
				elif 'showtitle' in self.curVideo and 'season' in self.curVideo and 'episode' in self.curVideo:
					self.curVideoInfo = {}
					self.curVideoInfo['tvdb_id'] = None
					self.curVideoInfo['year'] = None
					self.curVideoInfo['showtitle'] = self.curVideo['showtitle']
					self.curVideoInfo['season'] = self.curVideo['season']
					self.curVideoInfo['episode'] = self.curVideo['episode']
					self.curVideoInfo['uniqueid'] = None

				if 'multi_episode_count' in self.curVideo:
					self.isMultiPartEpisode = True
					self.markedAsWatched = []
					episode_count = self.curVideo['multi_episode_count']
					for i in range(episode_count):
						self.markedAsWatched.append(False)

			self.isPlaying = True
			self.watching()

	def playbackResumed(self):
		if not self.isPlaying:
			return

		Debug("[Scrobbler] playbackResumed()")
		if self.isPaused:
			p = time.time() - self.pausedAt
			Debug("[Scrobbler] Resumed after: %s" % str(p))
			self.pausedAt = 0
			self.isPaused = False
			self.update(True)
			self.watching()

	def playbackPaused(self):
		if not self.isPlaying:
			return

		Debug("[Scrobbler] playbackPaused()")
		self.update(True)
		Debug("[Scrobbler] Paused after: %s" % str(self.watchedTime))
		self.isPaused = True
		self.pausedAt = time.time()

	def playbackSeek(self):
		if not self.isPlaying:
			return

		Debug("[Scrobbler] playbackSeek()")
		self.update(True)
		self.watching()

	def playbackEnded(self):
		if not self.isPlaying:
			return

		Debug("[Scrobbler] playbackEnded()")
		if self.curVideo == None:
			Debug("[Scrobbler] Warning: Playback ended but video forgotten.")
			return
		self.isPlaying = False
		self.markedAsWatched = []
		if self.watchedTime != 0:
			if 'type' in self.curVideo:
				ratingCheck(self.curVideo, self.traktSummaryInfo, self.watchedTime, self.videoDuration, self.playlistLength)
				self.check()
			self.watchedTime = 0
			self.isMultiPartEpisode = False
		self.traktSummaryInfo = None
		self.curVideo = None

	def watching(self):
		if not self.isPlaying:
			return

		if not self.curVideoInfo:
			return

		Debug("[Scrobbler] watching()")
		scrobbleMovieOption = utilities.getSettingAsBool('scrobble_movie')
		scrobbleEpisodeOption = utilities.getSettingAsBool('scrobble_episode')

		self.update(True)

		duration = self.videoDuration / 60
		watchedPercent = (self.watchedTime / self.videoDuration) * 100

		if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
			response = self.traktapi.watchingMovie(self.curVideoInfo, duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Watch response: %s" % str(response))
				
		elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
			if self.isMultiPartEpisode:
				Debug("[Scrobbler] Multi-part episode, watching part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
				# recalculate watchedPercent and duration for multi-part
				adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
				duration = adjustedDuration / 60
				watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100
			
			response = self.traktapi.watchingEpisode(self.curVideoInfo, duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Watch response: %s" % str(response))

	def stoppedWatching(self):
		Debug("[Scrobbler] stoppedWatching()")
		scrobbleMovieOption = utilities.getSettingAsBool("scrobble_movie")
		scrobbleEpisodeOption = utilities.getSettingAsBool("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption:
			response = self.traktapi.cancelWatchingMovie()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: %s" % str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption:
			response = self.traktapi.cancelWatchingEpisode()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: %s" % str(response))

	def scrobble(self):
		if not self.curVideoInfo:
			return

		Debug("[Scrobbler] scrobble()")
		scrobbleMovieOption = utilities.getSettingAsBool('scrobble_movie')
		scrobbleEpisodeOption = utilities.getSettingAsBool('scrobble_episode')

		duration = self.videoDuration / 60
		watchedPercent = (self.watchedTime / self.videoDuration) * 100

		if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
			response = self.traktapi.scrobbleMovie(self.curVideoInfo, duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Scrobble response: %s" % str(response))

		elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
			if self.isMultiPartEpisode:
				Debug("[Scrobbler] Multi-part episode, scrobbling part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
				adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
				duration = adjustedDuration / 60
				watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100
			
			response = self.traktapi.scrobbleEpisode(self.curVideoInfo, duration, watchedPercent)
			if response != None:
				Debug("[Scrobbler] Scrobble response: %s" % str(response))

	def check(self):
		scrobbleMinViewTimeOption = utilities.getSettingAsFloat("scrobble_min_view_time")

		Debug("[Scrobbler] watched: %s / %s" % (str(self.watchedTime), str(self.videoDuration)))
		if ((self.watchedTime / self.videoDuration) * 100) >= scrobbleMinViewTimeOption:
			self.scrobble()
		else:
			self.stoppedWatching()
