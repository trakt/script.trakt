# -*- coding: utf-8 -*-
# 

import os
import xbmc, xbmcaddon, xbmcgui
import threading
import time

from utilities import *

# read settings
__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

class Scrobbler(threading.Thread):
	totalTime = 1
	watchedTime = 0
	startTime = 0
	curVideo = None
	pinging = False
	playlistLength = 1
	abortRequested = False
	
	def run(self):
		# When requested ping trakt to say that the user is still watching the item
		count = 0
		while (not (self.abortRequested or xbmc.abortRequested)):
			time.sleep(5) # 1min wait
			#Debug("[Scrobbler] Cycling " + str(self.pinging) + " - watchedTime: " + str(self.watchedTime))
			if self.pinging:
				count += 1
				self.watchedTime = xbmc.Player().getTime()
				if count>=100:
					Debug("[Scrobbler] Pinging watching "+str(self.curVideo))
					#tmp = time.time()
					#self.startTime = tmp
					self.startedWatching()
					count = 0
			else:
				count = 0
		
		Debug("Scrobbler stopping")
	
	def playbackStarted(self, data):
		self.curVideo = data['item']
		if self.curVideo <> None:
			if 'type' in self.curVideo and 'id' in self.curVideo:
				Debug("[Scrobbler] Watching: "+self.curVideo['type']+" - "+str(self.curVideo['id']))
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
					self.playlistLength = getPlaylistLengthFromXBMCPlayer(data['player']['playerid'])
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
		if self.startTime <> 0:
			self.watchedTime += time.time() - self.startTime
			Debug("[Scrobbler] Paused after: "+str(self.watchedTime))
			self.startTime = 0

	def playbackEnded(self):
		if self.startTime <> 0:
			if self.curVideo == None:
				Debug("[Scrobbler] Warning: Playback ended but video forgotten")
				return
			self.watchedTime += time.time() - self.startTime
			self.pinging = False
			if self.watchedTime <> 0:
				if 'type' in self.curVideo and 'id' in self.curVideo:
					self.check()
				self.watchedTime = 0
			self.startTime = 0
			
	def startedWatching(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")
		
		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			match = getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber','title','year'])
			if match == None:
				return
			response = watchingMovieOnTrakt(match['imdbnumber'], match['title'], match['year'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response));
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode'])
			if match == None:
				return
			response = watchingEpisodeOnTrakt(None, match['showtitle'], None, match['season'], match['episode'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Watch response: "+str(response));
		
	def stoppedWatching(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")
		
		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			response = cancelWatchingMovieOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response));
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			response = cancelWatchingEpisodeOnTrakt()
			if response != None:
				Debug("[Scrobbler] Cancel watch response: "+str(response));
			
	def scrobble(self):
		scrobbleMovieOption = __settings__.getSetting("scrobble_movie")
		scrobbleEpisodeOption = __settings__.getSetting("scrobble_episode")
		
		if self.curVideo['type'] == 'movie' and scrobbleMovieOption == 'true':
			match = getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber','title','year'])
			if match == None:
				return
			response = scrobbleMovieOnTrakt(match['imdbnumber'], match['title'], match['year'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response));
		elif self.curVideo['type'] == 'episode' and scrobbleEpisodeOption == 'true':
			match = getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode'])
			if match == None:
				return
			response = scrobbleEpisodeOnTrakt(None, match['showtitle'], None, match['season'], match['episode'], self.totalTime/60, int(100*self.watchedTime/self.totalTime))
			if response != None:
				Debug("[Scrobbler] Scrobble response: "+str(response));

	def check(self):
		__settings__ = xbmcaddon.Addon("script.trakt") #read settings again, encase they have changed
		scrobbleMinViewTimeOption = __settings__.getSetting("scrobble_min_view_time")
		
		Debug("watchedTime: " + str(self.watchedTime) + " - totalTime: " + str(self.totalTime) + " - minTime: " + str(float(scrobbleMinViewTimeOption)));
		Debug(str((self.watchedTime/self.totalTime)*100));
		Debug(str(float(scrobbleMinViewTimeOption)));
		if (self.watchedTime/self.totalTime)*100>=float(scrobbleMinViewTimeOption):
			self.scrobble()
		else:
			self.stoppedWatching()