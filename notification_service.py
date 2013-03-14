# -*- coding: utf-8 -*-
""" Handles notifications from XBMC via its own thread and forwards them on to the scrobbler """

import sys
import xbmc
import xbmcaddon
import xbmcgui

if sys.version_info < (2, 7):
	import simplejson as json
else:
	import json

import globals
from traktapi import traktAPI
from utilities import Debug, checkScrobblingExclusion, xbmcJsonRequest
from scrobbler import Scrobbler
from movie_sync import SyncMovies
from episode_sync import SyncEpisodes
from sync_exec import do_sync

class NotificationService:

	_scrobbler = None
	
	def __init__(self):
		self.run()

	def _dispatch(self, data):
		Debug("[Notification] Dispatch: %s" % data)
		xbmc.sleep(500)
		
		# check if scrobbler thread is still alive
		if not self._scrobbler.isAlive():

			if self.Player._playing and not self._scrobbler.pinging:
				# make sure pinging is set
				self._scrobbler.pinging = True

			Debug("[Notification] Scrobler thread died, restarting.")
			self._scrobbler.start()
		
		action = data["action"]
		if action == "started":
			del data["action"]
			p = {"item": data}
			self._scrobbler.playbackStarted(p)
		elif action == "ended" or action == "stopped":
			self._scrobbler.playbackEnded()
		elif action == "paused":
			self._scrobbler.playbackPaused()
		elif action == "resumed":
			self._scrobbler.playbackResumed()
		elif action == "seek" or action == "seekchapter":
			self._scrobbler.playbackSeek()
		elif action == "databaseUpdated":
			if do_sync('movies'):
				movies = SyncMovies(show_progress=False, api=globals.traktapi)
				movies.Run()
			if do_sync('episodes'):
				episodes = SyncEpisodes(show_progress=False, api=globals.traktapi)
				episodes.Run()
		elif action == "scanStarted":
			pass
		elif action == "settingsChanged":
			Debug("[Notification] Settings changed, reloading.")
			globals.traktapi.updateSettings()
		else:
			Debug("[Notification] '%s' unknown dispatch action!" % action)

	def run(self):
		Debug("[Notification] Starting")
		
		# setup event driven classes
		self.Player = traktPlayer(action = self._dispatch)
		self.Monitor = traktMonitor(action = self._dispatch)
		
		# init traktapi class
		globals.traktapi = traktAPI()

		# initalize scrobbler class
		self._scrobbler = Scrobbler(globals.traktapi)

		# start loop for events
		while (not xbmc.abortRequested):
			xbmc.sleep(500)
			
		# we aborted
		if xbmc.abortRequested:
			Debug("[Notification] abortRequested received, shutting down.")
			
			# delete player/monitor
			del self.Player
			del self.Monitor
			
			# join scrobbler, to wait for termination
			Debug("[Notification] Joining scrobbler thread to wait for exit.")
			self._scrobbler.join()

class traktMonitor(xbmc.Monitor):

	def __init__(self, *args, **kwargs):
		xbmc.Monitor.__init__(self)
		self.action = kwargs["action"]
		Debug("[traktMonitor] Initalized")

	# called when database gets updated and return video or music to indicate which DB has been changed
	def onDatabaseUpdated(self, database):
		if database == "video":
			Debug("[traktMonitor] onDatabaseUpdated(database: %s)" % database)
			data = {"action": "databaseUpdated"}
			self.action(data)

	# called when database update starts and return video or music to indicate which DB is being updated
	def onDatabaseScanStarted(self, database):
		if database == "video":
			Debug("[traktMonitor] onDatabaseScanStarted(database: %s)" % database)
			data = {"action": "scanStarted"}
			self.action(data)

	def onSettingsChanged(self):
		data = {"action": "settingsChanged"}
		self.action(data)
		

class traktPlayer(xbmc.Player):

	_playing = False

	def __init__(self, *args, **kwargs):
		xbmc.Player.__init__(self)
		self.action = kwargs["action"]
		Debug("[traktPlayer] Initalized")

	# called when xbmc starts playing a file
	def onPlayBackStarted(self):
		xbmc.sleep(1000)
		self.type = None
		self.id = None
		self.doubleEP = None
		
		# only do anything if we're playing a video
		if self.isPlayingVideo():
			# get item data from json rpc
			result = xbmcJsonRequest({"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": 1}, "id": 1})
			Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
			
			# check for exclusion
			_filename = self.getPlayingFile()
			if checkScrobblingExclusion(_filename):
				Debug("[traktPlayer] onPlayBackStarted() - '%s' is in exclusion settings, ignoring." % _filename)
				return
			
			self.type = result["item"]["type"]

			data = {"action": "started"}
			
			# check type of item
			if self.type == "unknown":
				# do a deeper check to see if we have enough data to perform scrobbles
				Debug("[traktPlayer] onPlayBackStarted() - Started playing a non-library file, checking available data.")
				
				season = xbmc.getInfoLabel("VideoPlayer.Season")
				episode = xbmc.getInfoLabel("VideoPlayer.Episode")
				showtitle = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
				year = xbmc.getInfoLabel("VideoPlayer.Year")
				
				if season and episode and showtitle:
					# we have season, episode and show title, can scrobble this as an episode
					self.type = "episode"
					data["type"] = "episode"
					data["season"] = int(season)
					data["episode"] = int(episode)
					data["showtitle"] = showtitle
					data["title"] = xbmc.getInfoLabel("VideoPlayer.Title")
					Debug("[traktPlayer] onPlayBackStarted() - Playing a non-library 'episode' - %s - S%02dE%02d - %s." % (data["title"], data["season"], data["episode"]))
				elif year and not season and not showtitle:
					# we have a year and no season/showtitle info, enough for a movie
					self.type = "movie"
					data["type"] = "movie"
					data["year"] = int(year)
					data["title"] = xbmc.getInfoLabel("VideoPlayer.Title")
					Debug("[traktPlayer] onPlayBackStarted() - Playing a non-library 'movie' - %s (%d)." % (data["title"], data["year"]))
				else:
					Debug("[traktPlayer] onPlayBackStarted() - Non-library file, not enough data for scrobbling, skipping.")
					return
			
			elif self.type == "episode" or self.type == "movie":
				# get library id
				self.id = result["item"]["id"]
				data["id"] = self.id
				data["type"] = self.type
			
				if self.type == "episode":
					# do a double ep check
					Debug("[traktPlayer] onPlayBackStarted() - Doing double episode check.")
					result = xbmcJsonRequest({"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": self.id, "properties": ["tvshowid", "season","episode"]}, "id": 1})
					if result:
						Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
						tvshowid = int(result["episodedetails"]["tvshowid"])
						season = int(result["episodedetails"]["season"])
						episode = int(result["episodedetails"]["episode"])
						epindex = episode - 1
						
						result = xbmcJsonRequest({"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": tvshowid, "season": season, "properties": ["episode", "file"], "limits": {"start": epindex, "end": epindex + 2}}, "id": 1})
						if result:
							Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
							# make sure episodes array exists in results
							if result.has_key("episodes"):
								# continue if we have 2 items in episodes array
								if len(result["episodes"]) == 2:
									ep1 = result["episodes"][0]
									ep2 = result["episodes"][1]
									
									# check if fullpath matches
									if (ep1["file"] == ep2["file"]) and (ep2["file"] == self.getPlayingFile()):
										self.doubleEP = ep2["episodeid"]
										data["doubleep"] = self.doubleEP
										Debug("[traktPlayer] onPlayBackStarted() - This episode is part of a double episode.")

			else:
				Debug("[traktPlayer] onPlayBackStarted() - Video type '%s' unrecognized, skipping." % self.type)
				return

			self._playing = True
			
			# send dispatch
			self.action(data)

	# called when xbmc stops playing a file
	def onPlayBackEnded(self):
		if self._playing:
			Debug("[traktPlayer] onPlayBackEnded() - %s" % self.isPlayingVideo())
			self._playing = False
			data = {"action": "ended"}
			self.action(data)

	# called when user stops xbmc playing a file
	def onPlayBackStopped(self):
		if self._playing:
			Debug("[traktPlayer] onPlayBackStopped() - %s" % self.isPlayingVideo())
			self._playing = False
			data = {"action": "stopped"}
			self.action(data)

	# called when user pauses a playing file
	def onPlayBackPaused(self):
		if self._playing:
			Debug("[traktPlayer] onPlayBackPaused() - %s" % self.isPlayingVideo())
			data = {"action": "paused"}
			self.action(data)

	# called when user resumes a paused file
	def onPlayBackResumed(self):
		if self._playing:
			Debug("[traktPlayer] onPlayBackResumed() - %s" % self.isPlayingVideo())
			data = {"action": "resumed"}
			self.action(data)

	# called when user queues the next item
	def onQueueNextItem(self):
		if self._playing:
			Debug("[traktPlayer] onQueueNextItem() - %s" % self.isPlayingVideo())

	# called when players speed changes. (eg. user FF/RW)
	def onPlayBackSpeedChanged(self, speed):
		if self._playing:
			Debug("[traktPlayer] onPlayBackSpeedChanged(speed: %s) - %s" % (str(speed), self.isPlayingVideo()))

	# called when user seeks to a time
	def onPlayBackSeek(self, time, offset):
		if self._playing:
			Debug("[traktPlayer] onPlayBackSeek(time: %s, offset: %s) - %s" % (str(time), str(offset), self.isPlayingVideo()))
			data = {"action": "seek"}
			self.action(data)

	# called when user performs a chapter seek
	def onPlayBackSeekChapter(self, chapter):
		if self._playing:
			Debug("[traktPlayer] onPlayBackSeekChapter(chapter: %s) - %s" % (str(chapter), self.isPlayingVideo()))
			data = {"action": "seekchapter"}
			self.action(data)
