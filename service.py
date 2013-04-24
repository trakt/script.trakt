# -*- coding: utf-8 -*-

import xbmc
import threading
import Queue

import globals
import utilities
from traktapi import traktAPI
from rating import rateMedia, rateOnTrakt
from scrobbler import Scrobbler
from sync import Sync

try:
	import simplejson as json
except ImportError:
	import json

class traktService:

	scrobbler = None
	watcher = None
	syncThread = None
	dispatchQueue = Queue.Queue()
	_interval = 10 * 60 # how often to send watching call
	
	def __init__(self):
		threading.Thread.name = 'trakt'

	def _dispatchQueue(self, data):
		utilities.Debug("Queuing for dispatch: %s" % data)
		self.dispatchQueue.put(data)
	
	def _dispatch(self, data):
		utilities.Debug("Dispatch: %s" % data)
		action = data['action']
		if action == 'started':
			del data['action']
			self.scrobbler.playbackStarted(data)
			self.watcher = threading.Timer(self._interval, self.doWatching)
			self.watcher.name = "trakt-watching"
			self.watcher.start()
		elif action == 'ended' or action == 'stopped':
			self.scrobbler.playbackEnded()
			if self.watcher:
				if self.watcher.isAlive():
					self.watcher.cancel()
					self.watcher = None
		elif action == 'paused':
			self.scrobbler.playbackPaused()
		elif action == 'resumed':
			self.scrobbler.playbackResumed()
		elif action == 'seek' or action == 'seekchapter':
			self.scrobbler.playbackSeek()
		elif action == 'databaseUpdated':
			self.doSync()
		elif action == 'scanStarted':
			pass
		elif action == 'settingsChanged':
			utilities.Debug("Settings changed, reloading.")
			globals.traktapi.updateSettings()
		else:
			utilities.Debug("Unknown dispatch action, '%s'." % action)

	def run(self):
		startup_delay = utilities.getSettingAsInt('startup_delay')
		if startup_delay:
			utilities.Debug("Delaying startup by %d seconds." % startup_delay)
			xbmc.sleep(startup_delay * 1000)

		utilities.Debug("Service thread starting.")

		# clear any left over properties
		utilities.clearProperty('traktManualSync')
		utilities.clearProperty('traktManualRateData')
		utilities.clearProperty('traktManualRate')
		
		# setup event driven classes
		self.Player = traktPlayer(action = self._dispatchQueue)
		self.Monitor = traktMonitor(action = self._dispatchQueue)

		# init traktapi class
		globals.traktapi = traktAPI()

		# init sync thread
		self.syncThread = syncThread()

		# init scrobbler class
		self.scrobbler = Scrobbler(globals.traktapi)

		# start loop for events
		while (not xbmc.abortRequested):
			while not self.dispatchQueue.empty() and (not xbmc.abortRequested):
				data = self.dispatchQueue.get()
				utilities.Debug("Queued dispatch: %s" % data)
				self._dispatch(data)

			# check if we were tasked to do a manual sync
			if utilities.getPropertyAsBool('traktManualSync'):
				if not self.syncThread.isAlive():
					utilities.Debug("Performing a manual sync.")
					self.doSync(manual=True)
				else:
					utilities.Debug("There already is a sync in progress.")

				utilities.clearProperty('traktManualSync')

			# check if we were tasked to do a manual rating
			if utilities.getPropertyAsBool('traktManualRate'):
				self.doManualRating()
				utilities.clearProperty('traktManualRateData')
				utilities.clearProperty('traktManualRate')
			
			if xbmc.Player().isPlayingVideo():
				self.scrobbler.update()

			xbmc.sleep(500)

		# we are shutting down
		utilities.Debug("Beginning shut down.")

		# check if watcher is set and active, if so, cancel it.
		if self.watcher:
			if self.watcher.isAlive():
				self.watcher.cancel()

		# delete player/monitor
		del self.Player
		del self.Monitor

		# check if sync thread is running, if so, join it.
		if self.syncThread.isAlive():
			self.syncThread.join()

	def doWatching(self):
		# check if we're still playing a video
		if not xbmc.Player().isPlayingVideo():
			self.watcher = None
			return

		# call watching method
		self.scrobbler.watching()

		# start a new timer thread
		self.watcher = threading.Timer(self._interval, self.doWatching)
		self.watcher.name = "trakt-watching"
		self.watcher.start()

	def doManualRating(self):
		data = json.loads(utilities.getProperty('traktManualRateData'))

		action = data['action']
		media_type = data['media_type']
		summaryInfo = None

		if not utilities.isValidMediaType(media_type):
			utilities.Debug("doManualRating(): Invalid media type '%s' passed for manual %s." % (media_type, action))
			return

		if not data['action'] in ['rate', 'unrate']:
			utilities.Debug("doManualRating(): Unknown action passed.")
			return
			
		if 'dbid' in data:
			utilities.Debug("Getting data for manual %s of library '%s' with ID of '%s'" % (action, media_type, data['dbid']))
		elif 'remoteitd' in data:
			if 'season' in data:
				utilities.Debug("Getting data for manual %s of non-library '%s' S%02dE%02d, with ID of '%s'." % (action, media_type, data['season'], data['episode'], data['remoteid']))
			else:
				utilities.Debug("Getting data for manual %s of non-library '%s' with ID of '%s'" % (action, media_type, data['remoteid']))

		if utilities.isEpisode(media_type):
			result = {}
			if 'dbid' in data:
				result = utilities.getEpisodeDetailsFromXbmc(data['dbid'], ['showtitle', 'season', 'episode', 'tvshowid'])
				if not result:
					utilities.Debug("doManualRating(): No data was returned from XBMC, aborting manual %s." % action)
					return
			else:
				result['tvdb_id'] = data['remoteid']
				result['season'] = data['season']
				result['episode'] = data['episode']

			summaryInfo = globals.traktapi.getEpisodeSummary(result['tvdb_id'], result['season'], result['episode'])
		elif utilities.isShow(media_type):
			result = {}
			if 'dbid' in data:
				result = utilities.getShowDetailsFromXBMC(data['dbid'], ['imdbnumber'])
				if not result:
					utilities.Debug("doManualRating(): No data was returned from XBMC, aborting manual %s." % action)
					return
			else:
				result['imdbnumber'] = data['remoteid']

			summaryInfo = globals.traktapi.getShowSummary(result['imdbnumber'])
		elif utilities.isMovie(media_type):
			result = {}
			if 'dbid' in data:
				result = utilities.getMovieDetailsFromXbmc(data['dbid'], ['imdbnumber', 'title', 'year'])
				if not result:
					utilities.Debug("doManualRating(): No data was returned from XBMC, aborting manual %s." % action)
					return
			else:
				result['imdbnumber'] = data['remoteid']

			summaryInfo = globals.traktapi.getMovieSummary(result['imdbnumber'])
		
		if not summaryInfo is None:
			if action == 'rate':
				if not 'rating' in data:
					rateMedia(media_type, summaryInfo)
				else:
					rateMedia(media_type, summaryInfo, rating=data['rating'])
			elif action == 'unrate':
				rateMedia(media_type, summaryInfo, unrate=True)
		else:
			utilities.Debug("doManualRating(): Summary info was empty, possible problem retrieving data from trakt.tv")

	def doSync(self, manual=False):
		self.syncThread = syncThread(manual)
		self.syncThread.start()

class syncThread(threading.Thread):

	_isManual = False

	def __init__(self, isManual=False):
		threading.Thread.__init__(self)
		self.name = "trakt-sync"
		self._isManual = isManual

	def run(self):
		sync = Sync(show_progress=self._isManual, api=globals.traktapi)
		sync.sync()

class traktMonitor(xbmc.Monitor):

	def __init__(self, *args, **kwargs):
		xbmc.Monitor.__init__(self)
		self.action = kwargs['action']
		utilities.Debug("[traktMonitor] Initalized.")

	# called when database gets updated and return video or music to indicate which DB has been changed
	def onDatabaseUpdated(self, database):
		if database == 'video':
			utilities.Debug("[traktMonitor] onDatabaseUpdated(database: %s)" % database)
			data = {'action': 'databaseUpdated'}
			self.action(data)

	# called when database update starts and return video or music to indicate which DB is being updated
	def onDatabaseScanStarted(self, database):
		if database == "video":
			utilities.Debug("[traktMonitor] onDatabaseScanStarted(database: %s)" % database)
			data = {'action': 'scanStarted'}
			self.action(data)

	def onSettingsChanged(self):
		data = {'action': 'settingsChanged'}
		self.action(data)

class traktPlayer(xbmc.Player):

	_playing = False
	plIndex = None

	def __init__(self, *args, **kwargs):
		xbmc.Player.__init__(self)
		self.action = kwargs['action']
		utilities.Debug("[traktPlayer] Initalized.")

	# called when xbmc starts playing a file
	def onPlayBackStarted(self):
		xbmc.sleep(1000)
		self.type = None
		self.id = None

		# only do anything if we're playing a video
		if self.isPlayingVideo():
			# get item data from json rpc
			result = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'Player.GetItem', 'params': {'playerid': 1}, 'id': 1})
			utilities.Debug("[traktPlayer] onPlayBackStarted() - %s" % result)

			# check for exclusion
			_filename = self.getPlayingFile()
			if utilities.checkScrobblingExclusion(_filename):
				utilities.Debug("[traktPlayer] onPlayBackStarted() - '%s' is in exclusion settings, ignoring." % _filename)
				return

			self.type = result['item']['type']

			data = {'action': 'started'}

			# check type of item
			if self.type == 'unknown':
				# do a deeper check to see if we have enough data to perform scrobbles
				utilities.Debug("[traktPlayer] onPlayBackStarted() - Started playing a non-library file, checking available data.")
				
				season = xbmc.getInfoLabel('VideoPlayer.Season')
				episode = xbmc.getInfoLabel('VideoPlayer.Episode')
				showtitle = xbmc.getInfoLabel('VideoPlayer.TVShowTitle')
				year = xbmc.getInfoLabel('VideoPlayer.Year')

				if season and episode and showtitle:
					# we have season, episode and show title, can scrobble this as an episode
					self.type = 'episode'
					data['type'] = 'episode'
					data['season'] = int(season)
					data['episode'] = int(episode)
					data['showtitle'] = showtitle
					data['title'] = xbmc.getInfoLabel('VideoPlayer.Title')
					if year.isdigit():
						data['year'] = year
					utilities.Debug("[traktPlayer] onPlayBackStarted() - Playing a non-library 'episode' - %s - S%02dE%02d - %s." % (data['showtitle'], data['season'], data['episode'], data['title']))
				elif year and not season and not showtitle:
					# we have a year and no season/showtitle info, enough for a movie
					self.type = 'movie'
					data['type'] = 'movie'
					data['year'] = int(year)
					data['title'] = xbmc.getInfoLabel('VideoPlayer.Title')
					utilities.Debug("[traktPlayer] onPlayBackStarted() - Playing a non-library 'movie' - %s (%d)." % (data['title'], data['year']))
				else:
					utilities.Debug("[traktPlayer] onPlayBackStarted() - Non-library file, not enough data for scrobbling, skipping.")
					return

			elif self.type == 'episode' or self.type == 'movie':
				# get library id
				self.id = result['item']['id']
				data['id'] = self.id
				data['type'] = self.type

				if self.type == 'episode':
					utilities.Debug("[traktPlayer] onPlayBackStarted() - Doing multi-part episode check.")
					result = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodeDetails', 'params': {'episodeid': self.id, 'properties': ['tvshowid', 'season', 'episode']}, 'id': 1})
					if result:
						utilities.Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
						tvshowid = int(result['episodedetails']['tvshowid'])
						season = int(result['episodedetails']['season'])
						episode = int(result['episodedetails']['episode'])
						episode_index = episode - 1

						result = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': tvshowid, 'season': season, 'properties': ['episode', 'file'], 'sort': {'method': 'episode'}}, 'id': 1})
						if result:
							utilities.Debug("[traktPlayer] onPlayBackStarted() - %s" % result)
							# make sure episodes array exists in results
							if 'episodes' in result:
								multi = []
								for i in range(episode_index, result['limits']['total']):
									if result['episodes'][i]['file'] == result['episodes'][episode_index]['file']:
										multi.append(result['episodes'][i]['episodeid'])
									else:
										break
								if len(multi) > 1:
									data['multi_episode_data'] = multi
									data['multi_episode_count'] = len(multi)
									utilities.Debug("[traktPlayer] onPlayBackStarted() - This episode is part of a multi-part episode.")
								else:
									utilities.Debug("[traktPlayer] onPlayBackStarted() - This is a single episode.")

			else:
				utilities.Debug("[traktPlayer] onPlayBackStarted() - Video type '%s' unrecognized, skipping." % self.type)
				return

			pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
			plSize = len(pl)
			if plSize > 1:
				pos = pl.getposition()
				if not self.plIndex is None:
					utilities.Debug("[traktPlayer] onPlayBackStarted() - User manually skipped to next (or previous) video, forcing playback ended event.")
					self.onPlayBackEnded()
				self.plIndex = pos
				utilities.Debug("[traktPlayer] onPlayBackStarted() - Playlist contains %d item(s), and is currently on item %d" % (plSize, (pos + 1)))

			self._playing = True

			# send dispatch
			self.action(data)

	# called when xbmc stops playing a file
	def onPlayBackEnded(self):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackEnded() - %s" % self.isPlayingVideo())
			self._playing = False
			self.plIndex = None
			data = {'action': 'ended'}
			self.action(data)

	# called when user stops xbmc playing a file
	def onPlayBackStopped(self):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackStopped() - %s" % self.isPlayingVideo())
			self._playing = False
			self.plIndex = None
			data = {'action': 'stopped'}
			self.action(data)

	# called when user pauses a playing file
	def onPlayBackPaused(self):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackPaused() - %s" % self.isPlayingVideo())
			data = {'action': 'paused'}
			self.action(data)

	# called when user resumes a paused file
	def onPlayBackResumed(self):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackResumed() - %s" % self.isPlayingVideo())
			data = {'action': 'resumed'}
			self.action(data)

	# called when user queues the next item
	def onQueueNextItem(self):
		if self._playing:
			utilities.Debug("[traktPlayer] onQueueNextItem() - %s" % self.isPlayingVideo())

	# called when players speed changes. (eg. user FF/RW)
	def onPlayBackSpeedChanged(self, speed):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackSpeedChanged(speed: %s) - %s" % (str(speed), self.isPlayingVideo()))

	# called when user seeks to a time
	def onPlayBackSeek(self, time, offset):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackSeek(time: %s, offset: %s) - %s" % (str(time), str(offset), self.isPlayingVideo()))
			data = {'action': 'seek', 'time': time, 'offset': offset}
			self.action(data)

	# called when user performs a chapter seek
	def onPlayBackSeekChapter(self, chapter):
		if self._playing:
			utilities.Debug("[traktPlayer] onPlayBackSeekChapter(chapter: %s) - %s" % (str(chapter), self.isPlayingVideo()))
			data = {'action': 'seekchapter', 'chapter': chapter}
			self.action(data)
