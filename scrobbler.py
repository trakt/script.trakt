# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import sys
import threading
import time

import utilities
from utilities import Debug
from rating import ratingCheck

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

class Scrobbler(threading.Thread):
	totalTime = 1
	watchedTime = 0
	startTime = 0
	pausedTime = 0
	curVideo = None
	curVideoData = None
	pinging = False
	playlistLength = 1
	abortRequested = False
	VideoExcluded = False

	def run(self):
		# When requested ping trakt to say that the user is still watching the item
		count = 0
		while (not (self.abortRequested or xbmc.abortRequested)):
			xbmc.sleep(5000) # sleep for 5 seconds
			if self.pinging and xbmc.Player().isPlayingVideo():
				count += 1
				self.watchedTime = xbmc.Player().getTime()
				self.startTime = time.time()
				if count >= 100:
					self.startedWatching()
					count = 0
			else:
				count = 0

		Debug("Scrobbler stopping")

	def playbackStarted(self, data):
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

	def playbackResumed(self):
		if self.pausedTime != 0:
			p = time.time() - self.pausedTime
			Debug("[Scrobbler] Resumed after: %s" % str(p))
			self.pausedTime = 0
			self.startedWatching()
	
	def playbackPaused(self):
		if self.startTime != 0:
			self.watchedTime += time.time() - self.startTime
			Debug("[Scrobbler] Paused after: "+str(self.watchedTime))
			self.startTime = 0
			self.pausedTime = time.time()

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
					ratingCheck(self.curVideo, self.watchedTime, self.totalTime, self.playlistLength)
				self.watchedTime = 0
			self.startTime = 0
			self.curVideo = None

	def startedWatching(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")
		ExcludeLiveTV = __settings__.getSetting("ExcludeLiveTV")
		ExcludeHTTP = __settings__.getSetting("ExcludeHTTP")		
		ExcludePathOption = __settings__.getSetting("ExcludePathOption")
		ExcludePathOption2 = __settings__.getSetting("ExcludePathOption2")
		ExcludePathOption3 = __settings__.getSetting("ExcludePathOption3")
		ExcludePath = __settings__.getSetting("ExcludePath")
		ExcludePath2 = __settings__.getSetting("ExcludePath2")
		ExcludePath3 = __settings__.getSetting("ExcludePath3")
		
		LiveTVExcluded = False
		HTTPExcluded = False		
		PathExcluded = False

		currentPath = xbmc.Player().getPlayingFile()
		if (currentPath.find("pvr://") > -1) and ExcludeLiveTV == 'true':
			Debug("Video is playing via Live TV, which is currently set as excluded location.", False)
			LiveTVExcluded = True			
		if (currentPath.find("http://") > -1) and ExcludeHTTP == 'true':
			Debug("Video is playing via HTTP source, which is currently set as excluded location.", False)
			HTTPExcluded = True		
		if  ExcludePath != "" and ExcludePathOption == 'true':
			if (currentPath.find(ExcludePath) > -1):
				Debug('Video is playing from location, which is currently set as excluded path 1.', False)
				PathExcluded = True
		if  ExcludePath2 != "" and ExcludePathOption2 == 'true':
			currentPath = xbmc.Player().getPlayingFile()
			if (currentPath.find(ExcludePath2) > -1):
				Debug('Video is playing from location, which is currently set as excluded path 2.', False)
				PathExcluded = True
		if  ExcludePath3 != "" and ExcludePathOption3 == 'true':
			currentPath = xbmc.Player().getPlayingFile()
			if (currentPath.find(ExcludePath3) > -1):
				Debug('Video is playing from location, which is currently set as excluded path 3.', False)
				PathExcluded = True

		if (LiveTVExcluded or HTTPExcluded or PathExcluded):
			self.VideoExcluded = True
			Debug("Video from excluded location was detected. No scrobbling!", False)

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true' and not self.VideoExcluded:
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
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true' and not self.VideoExcluded:
			match = None
			if 'id' in self.curVideo:
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
			response = utilities.watchingEpisodeOnTrakt(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], match['uniqueid']['unknown'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response))

	def stoppedWatching(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true' and not self.VideoExcluded:
			response = utilities.cancelWatchingMovieOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true' and not self.VideoExcluded:
			response = utilities.cancelWatchingEpisodeOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response))

	def scrobble(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")

		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true' and not self.VideoExcluded:
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
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true' and not self.VideoExcluded:
			match = None
			if 'id' in self.curVideo:
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
			response = utilities.scrobbleEpisodeOnTrakt(match['tvdb_id'], match['showtitle'], match['year'], match['season'], match['episode'], match['uniqueid']['unknown'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
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
