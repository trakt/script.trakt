# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import sys
import threading
import time

import utilities
from utilities import Debug

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

class Scrobbler(threading.Thread):
	totalTime = 1
	watchedTime = 0
	startTime = 0
	curVideo = None
	curVideoData = None
	pinging = False
	playlistLength = 1
	abortRequested = False

	def run(self):
		# When requested ping trakt to say that the user is still watching the item
		count = 0
		while (not (self.abortRequested or xbmc.abortRequested)):
			time.sleep(5)
			if self.pinging:
				count += 1
				self.watchedTime = xbmc.Player().getTime()
				if count >= 100:
					self.startedWatching()
					count = 0
			else:
				count = 0

		Debug("Scrobbler stopping")

	def playbackStarted(self, data):
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
					if self.totalTime == 0:
						if self.curVideo['type'] == 'movie':
							self.totalTime = 90
						elif self.curVideo['type'] == 'episode':
							self.totalTime = 30
						else:
							self.totalTime = 1
					self.playlistLength = utilities.getPlaylistLengthFromXBMCPlayer(data['player']['playerid'])
					if (self.playlistLength == 0):
						Debug("[Scrobbler] Warning: Cant find playlist length?!, assuming that this item is by itself")
						self.playlistLength = 1
				except:
					Debug("[Scrobbler] Suddenly stopped watching item, or error: "+str(sys.exc_info()[0]))
					self.curVideo = None
					self.startTime = 0
					return
				self.startTime = time.time()
				self.startedWatching()
				self.pinging = True
			else:
				self.curVideo = None
				self.startTime = 0

	def playbackPaused(self):
		if self.startTime != 0:
			self.watchedTime += time.time() - self.startTime
			Debug("[Scrobbler] Paused after: "+str(self.watchedTime))
			self.startTime = 0

	def playbackEnded(self):
		if self.startTime != 0:
			if self.curVideo == None:
				Debug("[Scrobbler] Warning: Playback ended but video forgotten")
				return
			self.watchedTime += time.time() - self.startTime
			self.pinging = False
			if self.watchedTime != 0:
				if 'type' in self.curVideo: #and 'id' in self.curVideo:
					self.check()
				self.watchedTime = 0
			self.startTime = 0

	def startedWatching(self):
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
			response = utilities.watchingMovieOnTrakt(match['imdbnumber'], match['title'], match['year'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = None
			if 'id' in self.curVideo:
				match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid'])
			elif 'showtitle' in self.curVideoData and 'season' in self.curVideoData and 'episode' in self.curVideoData:
				match = {}
				match['tvdb_id'] = None
				match['year'] = None
				match['showtitle'] = self.curVideoData['showtitle']
				match['season'] = self.curVideoData['season']
				match['episode'] = self.curVideoData['episode']
			if match == None:
				return
			response = utilities.watchingEpisodeOnTrakt(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response))

	def stoppedWatching(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			response = utilities.cancelWatchingMovieOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			response = utilities.cancelWatchingEpisodeOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))

	def scrobble(self):
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
			response = utilities.scrobbleMovieOnTrakt(match['imdbnumber'], match['title'], match['year'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = None
			if 'id' in self.curVideo:
				match = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode'])
			elif 'showtitle' in self.curVideoData and 'season' in self.curVideoData and 'episode' in self.curVideoData:
				match = {}
				match['tvdb_id'] = None
				match['year'] = None
				match['showtitle'] = self.curVideoData['showtitle']
				match['season'] = self.curVideoData['season']
				match['episode'] = self.curVideoData['episode']
			if match == None:
				return
			response = utilities.scrobbleEpisodeOnTrakt(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response))

	def check(self):
		__settings__ = xbmcaddon.Addon("script.trakt") #read settings again, encase they have changed
		scrobbleMinViewTimeOption = __settings__.getSetting("scrobble_min_view_time")

		Debug("watched: " + str(self.watchedTime) + " / " + str(self.totalTime))
		if (self.watchedTime/self.totalTime)*100>=float(scrobbleMinViewTimeOption):
			self.scrobble()
		else:
			self.stoppedWatching()
