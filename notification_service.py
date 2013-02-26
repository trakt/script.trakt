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

from utilities import Debug
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
		action = data["action"]
		if action == "started":
			p = {"item": {"type": data["type"], "id": data["id"]}}
			self._scrobbler.playbackStarted(p)
		elif action == "ended" or action == "stopped":
			self._scrobbler.playbackEnded()
		elif action == "paused":
			self._scrobbler.playbackPaused()
		elif action == "resumed":
			self._scrobbler.playbackResumed()
		elif action == "databaseUpdated":
			if do_sync('movies'):
				movies = SyncMovies(show_progress=False)
				movies.Run()
			if do_sync('episodes'):
				episodes = SyncEpisodes(show_progress=False)
				episodes.Run()
		elif action == "scanStarted":
			Debug("[Notification] Dispatch: scanStarted")
		else:
			Debug("[Notification] '%s' unknown dispatch action!" % action)

	def run(self):
		Debug("[Notification] Starting")
		
		# setup event driven classes
		self.Player = traktPlayer(action = self._dispatch)
		self.Monitor = traktMonitor(action = self._dispatch)
		
		# initalize scrobbler class
		self._scrobbler = Scrobbler()
		self._scrobbler.start()
		
		# start loop for events
		while (not xbmc.abortRequested):
			xbmc.sleep(500)
			
		# we aborted
		if xbmc.abortRequested:
			Debug("[Notification] abortRequested received, shutting down.")
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
		
		# only do anything if we're playing a video
		if self.isPlayingVideo():
			# get item data from json rpc
			rpccmd = json.dumps({"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": 1}, "id": 1})
			result = xbmc.executeJSONRPC(rpccmd)
			Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
			result = json.loads(result)
			
			self.type = result["result"]["item"]["type"]
			if self.type == "unknown":
				Debug("[traktPlayer] onPlayBackStarted() - Started playing a non-library file, skipping.")
				return
			
			self.id = result["result"]["item"]["id"]
			
			data = {"action": "started", "id": self.id, "type": self.type}
			
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

	# called when user performs a chapter seek
	def onPlayBackSeekChapter(self, chapter):
		if self._playing:
			Debug("[traktPlayer] onPlayBackSeekChapter(chapter: %s) - %s" % (str(chapter), self.isPlayingVideo()))
