# -*- coding: utf-8 -*-

import copy
import xbmc
import xbmcgui
import utilities
import logging
from utilities import notification

progress = xbmcgui.DialogProgress()
logger = logging.getLogger(__name__)

class Sync():


	def __init__(self, show_progress=False, run_silent=False, library="all", api=None):
		self.traktapi = api
		self.show_progress = show_progress
		self.run_silent = run_silent
		self.library = library
		if self.show_progress and self.run_silent:
			logger.debug("Sync is being run silently.")
		self.sync_on_update = utilities.getSettingAsBool('sync_on_update')
		self.notify = utilities.getSettingAsBool('show_sync_notifications')
		self.notify_during_playback = not (xbmc.Player().isPlayingVideo() and utilities.getSettingAsBool("hide_notifications_playback"))

	def __isCanceled(self):
		if self.show_progress and not self.run_silent and progress.iscanceled():
			logger.debug("Sync was canceled by user.")
			return True
		elif xbmc.abortRequested:
			logger.debug('Kodi abort requested')
			return True
		else:
			return False

	def __updateProgress(self, *args, **kwargs):
		if self.show_progress and not self.run_silent:
			kwargs['percent'] = args[0]
			progress.update(**kwargs)

	''' begin code for episode sync '''
	def __kodiLoadShows(self):
		self.__updateProgress(1, line1=utilities.getString(32094), line2=utilities.getString(32095))

		logger.debug("[Episodes Sync] Getting show data from Kodi")
		data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
		if data['limits']['total'] == 0:
			logger.debug("[Episodes Sync] Kodi json request was empty.")
			return None, None

		tvshows = utilities.kodiRpcToTraktMediaObjects(data)
		logger.debug("[Episode Sync] Getting shows from kodi finished %s" % tvshows)

		if tvshows is None:
			return None, None
		self.__updateProgress(2, line2=utilities.getString(32096))
		resultCollected = {'shows': []}
		resultWatched = {'shows': []}
		i = 0
		x = float(len(tvshows))
		logger.debug("[Episodes Sync] Getting episode data from Kodi")
		for show_col1 in tvshows:
			i += 1
			y = ((i / x) * 8) + 2
			self.__updateProgress(int(y), line2=utilities.getString(32097) % (i, x))

			show = {'title': show_col1['title'], 'ids': {}, 'year': show_col1['year'], 'seasons': []}

			if 'ids' in show_col1 and 'tvdb' in show_col1['ids']:
				show['ids'] = {'tvdb': show_col1['ids']['tvdb']}

			data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': show_col1['tvshowid'], 'properties': ['season', 'episode', 'playcount', 'uniqueid', 'lastplayed', 'file', 'dateadded', 'runtime']}, 'id': 0})
			if not data:
				logger.debug("[Episodes Sync] There was a problem getting episode data for '%s', aborting sync." % show['title'])
				return None, None
			elif 'episodes' not in data:
				logger.debug("[Episodes Sync] '%s' has no episodes in Kodi." % show['title'])
				continue

			if 'tvshowid' in show_col1:
				del(show_col1['tvshowid'])

			showWatched = copy.deepcopy(show)
			data2 = copy.deepcopy(data)
			show['seasons'] = utilities.kodiRpcToTraktMediaObjects(data)

			showWatched['seasons'] = utilities.kodiRpcToTraktMediaObjects(data2, 'watched')

			resultCollected['shows'].append(show)
			resultWatched['shows'].append(showWatched)

		self.__updateProgress(10, line2=utilities.getString(32098))
		return resultCollected, resultWatched

	def __traktLoadShows(self):
		self.__updateProgress(10, line1=utilities.getString(32099), line2=utilities.getString(32100))

		logger.debug('[Episodes Sync] Getting episode collection from trakt.tv')
		try:
			traktShowsCollected = {}
			traktShowsCollected = self.traktapi.getShowsCollected(traktShowsCollected)
			traktShowsCollected = traktShowsCollected.items()

			self.__updateProgress(12, line2=utilities.getString(32101))
			traktShowsWatched = {}
			traktShowsWatched = self.traktapi.getShowsWatched(traktShowsWatched)
			traktShowsWatched = traktShowsWatched.items()
		except Exception:
			logger.debug("[Episodes Sync] Invalid trakt.tv show list, possible error getting data from trakt, aborting trakt.tv collection update.")
			return False, False

		i = 0
		x = float(len(traktShowsCollected))
		showsCollected = {'shows': []}
		for key, show in traktShowsCollected:
			i += 1
			y = ((i / x) * 20) + 6
			self.__updateProgress(int(y), line2=utilities.getString(32102) % (i, x))

			#will keep the data in python structures - just like the KODI response
			show = show.to_dict()
			
			showsCollected['shows'].append(show)

		i = 0
		x = float(len(traktShowsWatched))
		showsWatched = {'shows': []}
		for key, show in traktShowsWatched:
			i += 1
			y = ((i / x) * 26) + 6
			self.__updateProgress(int(y), line2=utilities.getString(32102) % (i, x))

			#will keep the data in python structures - just like the KODI response
			show = show.to_dict()

			showsWatched['shows'].append(show)

		self.__updateProgress(32, line2=utilities.getString(32103))

		return showsCollected, showsWatched

	def __traktLoadShowsPlaybackProgress(self):
		if utilities.getSettingAsBool('trakt_episode_playback') and not self.__isCanceled():
			self.__updateProgress(10, line1=utilities.getString(1485), line2=utilities.getString(32119))

			logger.debug('[Playback Sync] Getting playback progress from trakt.tv')
			try:
				traktProgressMovies, traktProgressShows = self.traktapi.getPlaybackProgress()
			except Exception:
				logger.debug("[Playback Sync] Invalid trakt.tv progress list, possible error getting data from trakt, aborting trakt.tv playback update.")
				return False, False

			i = 0
			x = float(len(traktProgressShows))
			showsProgress = {'shows': []}
			for show in traktProgressShows:
				i += 1
				y = ((i / x) * 20) + 6
				self.__updateProgress(int(y), line2=utilities.getString(32120) % (i, x))

				#will keep the data in python structures - just like the KODI response
				show = show.to_dict()

				showsProgress['shows'].append(show)

			self.__updateProgress(32, line2=utilities.getString(32121))

			return showsProgress

	def __addEpisodesToTraktCollection(self, kodiShows, traktShows):
		if utilities.getSettingAsBool('add_episodes_to_trakt') and not self.__isCanceled():
			addTraktShows = copy.deepcopy(traktShows)
			addKodiShows = copy.deepcopy(kodiShows)

			tmpTraktShowsAdd = self.__compareShows(addKodiShows, addTraktShows)
			traktShowsAdd = copy.deepcopy(tmpTraktShowsAdd)
			self.sanitizeShows(traktShowsAdd)
			#logger.debug("traktShowsAdd %s" % traktShowsAdd)

			if len(traktShowsAdd['shows']) == 0:
				self.__updateProgress(48, line1=utilities.getString(32068), line2=utilities.getString(32104))
				logger.debug("[Episodes Sync] trakt.tv episode collection is up to date.")
				return
			logger.debug("[Episodes Sync] %i show(s) have episodes (%d) to be added to your trakt.tv collection." % (len(traktShowsAdd['shows']), self.__countEpisodes(traktShowsAdd)))
			for show in traktShowsAdd['shows']:
				logger.debug("[Episodes Sync] Episodes added: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(33, line1=utilities.getString(32068), line2=utilities.getString(32067) % (len(traktShowsAdd['shows'])), line3=" ")

			#split episode list into chunks of 50
			chunksize = 1
			chunked_episodes = utilities.chunks(traktShowsAdd['shows'], chunksize)
			errorcount = 0
			i = 0
			x = float(len(traktShowsAdd['shows']))
			for chunk in chunked_episodes:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 33
				self.__updateProgress(int(y), line2=utilities.getString(32069) % ((i)*chunksize if (i)*chunksize < x else x, x))

				request = {'shows': chunk}
				logger.debug("[traktAddEpisodes] Shows to add %s" % request)
				try:
					self.traktapi.addToCollection(request)
				except Exception as ex:
					message = utilities.createError(ex)
					logging.fatal(message)
					errorcount += 1

			logger.debug("[traktAddEpisodes] Finished with %d error(s)" % errorcount)
			self.__updateProgress(49, line2=utilities.getString(32105) % self.__countEpisodes(traktShowsAdd))

	def __deleteEpisodesFromTraktCollection(self, traktShows, kodiShows):
		if utilities.getSettingAsBool('clean_trakt_episodes') and not self.__isCanceled():
			removeTraktShows = copy.deepcopy(traktShows)
			removeKodiShows = copy.deepcopy(kodiShows)

			traktShowsRemove = self.__compareShows(removeTraktShows, removeKodiShows)
			self.sanitizeShows(traktShowsRemove)

			if len(traktShowsRemove['shows']) == 0:
				self.__updateProgress(65, line1=utilities.getString(32077), line2=utilities.getString(32110))
				logger.debug('[Episodes Sync] trakt.tv episode collection is clean, no episodes to remove.')
				return

			logger.debug("[Episodes Sync] %i show(s) will have episodes removed from trakt.tv collection." % len(traktShowsRemove['shows']))
			for show in traktShowsRemove['shows']:
				logger.debug("[Episodes Sync] Episodes removed: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(50, line1=utilities.getString(32077), line2=utilities.getString(32111) % self.__countEpisodes(traktShowsRemove), line3=" ")

			logger.debug("[traktRemoveEpisodes] Shows to remove %s" % traktShowsRemove)
			try:
				self.traktapi.removeFromCollection(traktShowsRemove)
			except Exception as ex:
				message = utilities.createError(ex)
				logging.fatal(message)

			self.__updateProgress(65, line2=utilities.getString(32112) % self.__countEpisodes(traktShowsRemove), line3=" ")

	def __addEpisodesToTraktWatched(self, kodiShows, traktShows):
		if utilities.getSettingAsBool('trakt_episode_playcount') and not self.__isCanceled():
			updateTraktTraktShows = copy.deepcopy(traktShows)
			updateTraktKodiShows = copy.deepcopy(kodiShows)

			traktShowsUpdate = self.__compareShows(updateTraktKodiShows, updateTraktTraktShows, watched=True)
			self.sanitizeShows(traktShowsUpdate)
			#logger.debug("traktShowsUpdate %s" % traktShowsUpdate)

			if len(traktShowsUpdate['shows']) == 0:
				self.__updateProgress(82, line1=utilities.getString(32071), line2=utilities.getString(32106))
				logger.debug("[Episodes Sync] trakt.tv episode playcounts are up to date.")
				return

			logger.debug("[Episodes Sync] %i show(s) are missing playcounts on trakt.tv" % len(traktShowsUpdate['shows']))
			for show in traktShowsUpdate['shows']:
				logger.debug("[Episodes Sync] Episodes updated: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(66, line1=utilities.getString(32071), line2=utilities.getString(32070) % (len(traktShowsUpdate['shows'])), line3="")
			errorcount = 0
			i = 0
			x = float(len(traktShowsUpdate['shows']))
			for show in traktShowsUpdate['shows']:
				if self.__isCanceled():
					return
				epCount = self.__countEpisodes([show])
				title = show['title'].encode('utf-8', 'ignore')
				i += 1
				y = ((i / x) * 16) + 66
				self.__updateProgress(int(y), line2=title, line3=utilities.getString(32073) % epCount)

				s = {'shows': [show]}
				logger.debug("[traktUpdateEpisodes] Shows to update %s" % s)
				try:
					self.traktapi.addToHistory(s)
				except Exception as ex:
					message = utilities.createError(ex)
					logging.fatal(message)
					errorcount += 1

			logger.debug("[traktUpdateEpisodes] Finished with %d error(s)" % errorcount)
			self.__updateProgress(82, line2=utilities.getString(32072) % (len(traktShowsUpdate['shows'])), line3="")

	def __addEpisodesToKodiWatched(self, traktShows, kodiShows, kodiShowsCollected):
		if utilities.getSettingAsBool('kodi_episode_playcount') and not self.__isCanceled():
			updateKodiTraktShows = copy.deepcopy(traktShows)
			updateKodiKodiShows = copy.deepcopy(kodiShows)

			kodiShowsUpadate = self.__compareShows(updateKodiTraktShows, updateKodiKodiShows, watched=True, restrict=True, collected=kodiShowsCollected)

			if len(kodiShowsUpadate['shows']) == 0:
				self.__updateProgress(98, line1=utilities.getString(32074), line2=utilities.getString(32107))
				logger.debug("[Episodes Sync] Kodi episode playcounts are up to date.")
				return

			logger.debug("[Episodes Sync] %i show(s) shows are missing playcounts on Kodi" % len(kodiShowsUpadate['shows']))
			for s in ["%s" % self.__getShowAsString(s, short=True) for s in kodiShowsUpadate['shows']]:
				logger.debug("[Episodes Sync] Episodes updated: %s" % s)

			#logger.debug("kodiShowsUpadate: %s" % kodiShowsUpadate)
			episodes = []
			for show in kodiShowsUpadate['shows']:
				for season in show['seasons']:
					for episode in season['episodes']:
						episodes.append({'episodeid': episode['ids']['episodeid'], 'playcount': episode['plays']})

			#split episode list into chunks of 50
			chunksize = 50
			chunked_episodes = utilities.chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": episodes[i], "id": i} for i in range(len(episodes))], chunksize)
			i = 0
			x = float(len(episodes))
			for chunk in chunked_episodes:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 82
				self.__updateProgress(int(y), line2=utilities.getString(32108) % ((i)*chunksize if (i)*chunksize < x else x, x))

				logger.debug("[Episodes Sync] chunk %s" % str(chunk))
				result = utilities.kodiJsonRequest(chunk)
				logger.debug("[Episodes Sync] result %s" % str(result))

			self.__updateProgress(98, line2=utilities.getString(32109) % len(episodes))

	def __addEpisodeProgressToKodi(self, traktShows, kodiShows):
		if utilities.getSettingAsBool('trakt_episode_playback') and traktShows and not self.__isCanceled():
			updateKodiTraktShows = copy.deepcopy(traktShows)
			updateKodiKodiShows = copy.deepcopy(kodiShows)
			kodiShowsUpadate = self.__compareShows(updateKodiTraktShows, updateKodiKodiShows, restrict=True, playback=True)

			if len(kodiShowsUpadate['shows']) == 0:
				self.__updateProgress(98, line1=utilities.getString(1441), line2=utilities.getString(32129))
				logger.debug("[Episodes Sync] Kodi episode playbacks are up to date.")
				return

			logger.debug("[Episodes Sync] %i show(s) shows are missing playbacks on Kodi" % len(kodiShowsUpadate['shows']))
			for s in ["%s" % self.__getShowAsString(s, short=True) for s in kodiShowsUpadate['shows']]:
				logger.debug("[Episodes Sync] Episodes updated: %s" % s)

			episodes = []
			for show in kodiShowsUpadate['shows']:
				for season in show['seasons']:
					for episode in season['episodes']:
						episodes.append({'episodeid': episode['ids']['episodeid'], 'progress': episode['progress'], 'runtime': episode['runtime']})

			#need to calculate the progress in int from progress in percent from trakt
			#split episode list into chunks of 50
			chunksize = 50
			chunked_episodes = utilities.chunks([{"jsonrpc": "2.0", "id": i, "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid":episodes[i]['episodeid'], "resume": {"position": episodes[i]['runtime']/100.0*episodes[i]['progress']}}} for i in range(len(episodes))], chunksize)
			i = 0
			x = float(len(episodes))
			for chunk in chunked_episodes:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 82
				self.__updateProgress(int(y), line2=utilities.getString(32130) % ((i)*chunksize if (i)*chunksize < x else x, x))

				utilities.kodiJsonRequest(chunk)

			self.__updateProgress(98, line2=utilities.getString(32131) % len(episodes))

	def __countEpisodes(self, shows, collection=True):
		count = 0
		if 'shows' in shows:
			shows = shows['shows']
		for show in shows:
			for seasonKey in show['seasons']:
				if seasonKey is not None and 'episodes' in seasonKey:
					for episodeKey in seasonKey['episodes']:
						if episodeKey is not None:
							if 'collected' in episodeKey and not episodeKey['collected'] == collection:
								continue
							if 'number' in episodeKey and episodeKey['number']:
								count += 1
		return count

	def __getShowAsString(self, show, short=False):
		p = []
		if 'seasons' in show:
			for season in show['seasons']:
				s = ""
				if short:
					s = ", ".join(["S%02dE%02d" % (season['number'], i['number']) for i in season['episodes']])
				else:
					episodes = ", ".join([str(i) for i in show['shows']['seasons'][season]])
					s = "Season: %d, Episodes: %s" % (season, episodes)
				p.append(s)
		else:
			p = ["All"]
		if 'tvdb' in show['ids']:
			return "%s [tvdb: %s] - %s" % (show['title'], show['ids']['tvdb'], ", ".join(p))
		else:
			return "%s [tvdb: No id] - %s" % (show['title'], ", ".join(p))

	def __getEpisodes(self, seasons):
		data = {}
		for season in seasons:
			episodes = {}
			for episode in season['episodes']:
				episodes[episode['number']] = episode
			data[season['number']] = episodes

		return data

	#always return shows_col1 if you have enrich it, but don't return shows_col2
	def __compareShows(self, shows_col1, shows_col2, watched=False, restrict=False, collected=False, playback=False):
		shows = []
		for show_col1 in shows_col1['shows']:
			if show_col1:
				show_col2 = utilities.findMediaObject(show_col1, shows_col2['shows'])
				#logger.debug("show_col1 %s" % show_col1)
				#logger.debug("show_col2 %s" % show_col2)

				if show_col2:
					season_diff = {}
					# format the data to be easy to compare trakt and KODI data
					season_col1 = self.__getEpisodes(show_col1['seasons'])
					season_col2 = self.__getEpisodes(show_col2['seasons'])
					for season in season_col1:
						a = season_col1[season]
						if season in season_col2:
							b = season_col2[season]
							diff = list(set(a).difference(set(b)))
							if playback:
								t = list(set(a).intersection(set(b)))
								if len(t) > 0:
									eps = {}
									for ep in t:
										eps[ep] = a[ep]
										if 'episodeid' in season_col2[season][ep]['ids']:
											if 'ids' in eps:
												eps[ep]['ids']['episodeid'] = season_col2[season][ep]['ids']['episodeid']
											else:
												eps[ep]['ids'] = {'episodeid': season_col2[season][ep]['ids']['episodeid']}
										eps[ep]['runtime'] = season_col2[season][ep]['runtime']
									season_diff[season] = eps
							elif len(diff) > 0:
								if restrict:
									# get all the episodes that we have in Kodi, watched or not - update kodi
									collectedShow = utilities.findMediaObject(show_col1, collected['shows'])
									#logger.debug("collected %s" % collectedShow)
									collectedSeasons = self.__getEpisodes(collectedShow['seasons'])
									t = list(set(collectedSeasons[season]).intersection(set(diff)))
									if len(t) > 0:
										eps = {}
										for ep in t:
											eps[ep] = a[ep]
											if 'episodeid' in collectedSeasons[season][ep]['ids']:
												if 'ids' in eps:
													eps[ep]['ids']['episodeid'] = collectedSeasons[season][ep]['ids']['episodeid']
												else:
													eps[ep]['ids'] = {'episodeid': collectedSeasons[season][ep]['ids']['episodeid']}
										season_diff[season] = eps
								else:
									eps = {}
									for ep in diff:
										eps[ep] = a[ep]
									if len(eps) > 0:
										season_diff[season] = eps
						else:
							if not restrict:
								if len(a) > 0:
									season_diff[season] = a
					#logger.debug("season_diff %s" % season_diff)
					if len(season_diff) > 0:
						#logger.debug("Season_diff")
						show = {'title': show_col1['title'], 'ids': {}, 'year': show_col1['year'], 'seasons': []}
						if 'tvdb' in show_col1['ids']:
							show['ids'] = {'tvdb': show_col1['ids']['tvdb']}
						for seasonKey in season_diff:
							episodes = []
							for episodeKey in season_diff[seasonKey]:
								episodes.append(season_diff[seasonKey][episodeKey])
							show['seasons'].append({ 'number': seasonKey, 'episodes': episodes })
						if 'imdb' in show_col2 and show_col2['imdb']:
							show['ids']['imdb'] = show_col2['imdb']
						if 'tvshowid' in show_col2:
							show['tvshowid'] = show_col2['tvshowid']
						#logger.debug("show %s" % show)
						shows.append(show)
				else:
					if not restrict:
						if self.__countEpisodes([show_col1]) > 0:
							show = {'title': show_col1['title'], 'ids': {}, 'year': show_col1['year'], 'seasons': []}
							if 'tvdb' in show_col1['ids']:
								show['ids'] = {'tvdb': show_col1['ids']['tvdb']}
							for seasonKey in show_col1['seasons']:
								episodes = []
								for episodeKey in seasonKey['episodes']:
									if watched and (episodeKey['watched'] == 1):
										episodes.append(episodeKey)
									elif not watched:
										episodes.append(episodeKey)
								if len(episodes) > 0:
									show['seasons'].append({ 'number': seasonKey['number'], 'episodes': episodes })

							if 'tvshowid' in show_col1:
								del(show_col1['tvshowid'])
							if self.__countEpisodes([show]) > 0:
								shows.append(show)
		result = { 'shows': shows}
		return result

	def __syncEpisodes(self):
		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(32045), utilities.getString(32050)), utilities.getString(32061)) #Sync started
		if self.show_progress and not self.run_silent:
			progress.create("%s %s" % (utilities.getString(32045), utilities.getString(32050)), line1=" ", line2=" ", line3=" ")

		kodiShowsCollected, kodiShowsWatched = self.__kodiLoadShows()
		if not isinstance(kodiShowsCollected, list) and not kodiShowsCollected:
			logger.debug("[Episodes Sync] Kodi collected show list is empty, aborting tv show Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return
		if not isinstance(kodiShowsWatched, list) and not kodiShowsWatched:
			logger.debug("[Episodes Sync] Kodi watched show list is empty, aborting tv show Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		traktShowsCollected, traktShowsWatched = self.__traktLoadShows()
		if not traktShowsCollected:
			logger.debug("[Episodes Sync] Error getting trakt.tv collected show list, aborting tv show sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return
		if not traktShowsWatched:
			logger.debug("[Episodes Sync] Error getting trakt.tv watched show list, aborting tv show sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		traktShowsProgress = self.__traktLoadShowsPlaybackProgress()
		if not traktShowsProgress:
			logger.debug("[Episodes Sync] Error getting trakt.tv show playback list, skipping playback sync.")

		self.__addEpisodesToTraktCollection(kodiShowsCollected, traktShowsCollected)

		self.__deleteEpisodesFromTraktCollection(traktShowsCollected, kodiShowsCollected)

		self.__addEpisodesToTraktWatched(kodiShowsWatched, traktShowsWatched)

		self.__addEpisodesToKodiWatched(traktShowsWatched, kodiShowsWatched, kodiShowsCollected)

		self.__addEpisodeProgressToKodi(traktShowsProgress, kodiShowsCollected)

		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(32045), utilities.getString(32050)), utilities.getString(32062)) #Sync complete

		if self.show_progress and not self.run_silent:
			self.__updateProgress(100, line1=" ", line2=utilities.getString(32075), line3=" ")
			progress.close()

		logger.debug("[Episodes Sync] Shows on trakt.tv (%d), shows in Kodi (%d)." % (len(traktShowsCollected['shows']), len(kodiShowsCollected['shows'])))

		logger.debug("[Episodes Sync] Episodes on trakt.tv (%d), episodes in Kodi (%d)." % (self.__countEpisodes(traktShowsCollected), self.__countEpisodes(kodiShowsCollected)))
		logger.debug("[Episodes Sync] Complete.")

	@staticmethod
	def sanitizeShows(shows):
		# do not remove watched_at and collected_at may cause problems between the 4 sync types (would probably have to deepcopy etc)
		for show in shows['shows']:
			for season in show['seasons']:
				for episode in season['episodes']:
					if 'collected' in episode:
						del episode['collected']
					if 'watched' in episode:
						del episode['watched']
					if 'season' in episode:
						del episode['season']
					if 'plays' in episode:
						del episode['plays']
					if 'ids' in episode and 'episodeid' in episode['ids']:
						del episode['ids']['episodeid']

	''' begin code for movie sync '''
	def __kodiLoadMovies(self):
		self.__updateProgress(1, line2=utilities.getString(32079))

		logger.debug("[Movies Sync] Getting movie data from Kodi")
		data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year', 'playcount', 'lastplayed', 'file', 'dateadded', 'runtime']}})
		if data['limits']['total'] == 0:
			logger.debug("[Movies Sync] Kodi JSON request was empty.")
			return

		kodi_movies = utilities.kodiRpcToTraktMediaObjects(data)

		self.__updateProgress(10, line2=utilities.getString(32080))

		return kodi_movies

	def __traktLoadMovies(self):
		self.__updateProgress(10, line1=utilities.getString(32079), line2=utilities.getString(32081))

		logger.debug("[Movies Sync] Getting movie collection from trakt.tv")

		traktMovies = {}
		traktMovies = self.traktapi.getMoviesCollected(traktMovies)

		self.__updateProgress(17, line2=utilities.getString(32082))
		traktMovies = self.traktapi.getMoviesWatched(traktMovies)
		traktMovies = traktMovies.items()

		self.__updateProgress(24, line2=utilities.getString(32083))
		movies = []
		for key, movie in traktMovies:
			movie = movie.to_dict()
			
			movies.append(movie)

		return movies

	def __traktLoadMoviesPlaybackProgress(self):
		if utilities.getSettingAsBool('trakt_movie_playback') and not self.__isCanceled():
			self.__updateProgress(25, line2=utilities.getString(32122))

			logger.debug('[Movies Sync] Getting playback progress from trakt.tv')
			try:
				traktProgressMovies, traktProgressShows = self.traktapi.getPlaybackProgress()
			except Exception:
				logger.debug("[Movies Sync] Invalid trakt.tv playback progress list, possible error getting data from trakt, aborting trakt.tv playback update.")
				return False, False

			i = 0
			x = float(len(traktProgressMovies))
			moviesProgress = {'movies': []}
			for movie in traktProgressMovies:
				i += 1
				y = ((i / x) * 25) + 11
				self.__updateProgress(int(y), line2=utilities.getString(32123) % (i, x))

				#will keep the data in python structures - just like the KODI response
				movie = movie.to_dict()

				moviesProgress['movies'].append(movie)

			self.__updateProgress(36, line2=utilities.getString(32124))

			return moviesProgress

	def __addMoviesToTraktCollection(self, kodiMovies, traktMovies):
		if utilities.getSettingAsBool('add_movies_to_trakt') and not self.__isCanceled():
			addTraktMovies = copy.deepcopy(traktMovies)
			addKodiMovies = copy.deepcopy(kodiMovies)

			traktMoviesToAdd = self.__compareMovies(addKodiMovies, addTraktMovies)
			self.sanitizeMovies(traktMoviesToAdd)
			logger.debug("[Movies Sync] Compared movies, found %s to add." % len(traktMoviesToAdd))

			if len(traktMoviesToAdd) == 0:
				self.__updateProgress(48, line2=utilities.getString(32084))
				logger.debug("[Movies Sync] trakt.tv movie collection is up to date.")
				return

			titles = ", ".join(["%s" % (m['title']) for m in traktMoviesToAdd])
			logger.debug("[Movies Sync] %i movie(s) will be added to trakt.tv collection." % len(traktMoviesToAdd))
			logger.debug("[Movies Sync] Movies to add : %s" % titles)

			self.__updateProgress(37, line2=utilities.getString(32063) % len(traktMoviesToAdd))

			moviesToAdd = {'movies': traktMoviesToAdd}
			#logger.debug("Movies to add: %s" % moviesToAdd)
			try:
				self.traktapi.addToCollection(moviesToAdd)
			except Exception as ex:
				message = utilities.createError(ex)
				logging.fatal(message)

			self.__updateProgress(48, line2=utilities.getString(32085) % len(traktMoviesToAdd))

	def __deleteMoviesFromTraktCollection(self, traktMovies, kodiMovies):

		if utilities.getSettingAsBool('clean_trakt_movies') and not self.__isCanceled():
			removeTraktMovies = copy.deepcopy(traktMovies)
			removeKodiMovies = copy.deepcopy(kodiMovies)

			logger.debug("[Movies Sync] Starting to remove.")
			traktMoviesToRemove = self.__compareMovies(removeTraktMovies, removeKodiMovies)
			self.sanitizeMovies(traktMoviesToRemove)
			logger.debug("[Movies Sync] Compared movies, found %s to remove." % len(traktMoviesToRemove))

			if len(traktMoviesToRemove) == 0:
				self.__updateProgress(60, line2=utilities.getString(32091))
				logger.debug("[Movies Sync] trakt.tv movie collection is clean, no movies to remove.")
				return

			titles = ", ".join(["%s" % (m['title']) for m in traktMoviesToRemove])
			logger.debug("[Movies Sync] %i movie(s) will be removed from trakt.tv collection." % len(traktMoviesToRemove))
			logger.debug("[Movies Sync] Movies removed: %s" % titles)

			self.__updateProgress(49, line2=utilities.getString(32076) % len(traktMoviesToRemove))

			moviesToRemove = {'movies': traktMoviesToRemove}
			try:
				self.traktapi.removeFromCollection(moviesToRemove)
			except Exception as ex:
				message = utilities.createError(ex)
				logging.fatal(message)
			self.traktapi.removeFromCollection(moviesToRemove)

			self.__updateProgress(60, line2=utilities.getString(32092) % len(traktMoviesToRemove))


	def __addMoviesToTraktWatched(self, kodiMovies, traktMovies):

		if utilities.getSettingAsBool('trakt_movie_playcount') and not self.__isCanceled():
			updateTraktTraktMovies = copy.deepcopy(traktMovies)
			updateTraktKodiMovies = copy.deepcopy(kodiMovies)

			traktMoviesToUpdate = self.__compareMovies(updateTraktKodiMovies, updateTraktTraktMovies, watched=True)
			self.sanitizeMovies(traktMoviesToUpdate)

			if len(traktMoviesToUpdate) == 0:
				self.__updateProgress(72, line2=utilities.getString(32086))
				logger.debug("[Movies Sync] trakt.tv movie playcount is up to date")
				return

			titles = ", ".join(["%s" % (m['title']) for m in traktMoviesToUpdate])
			logger.debug("[Movies Sync] %i movie(s) playcount will be updated on trakt.tv" % len(traktMoviesToUpdate))
			logger.debug("[Movies Sync] Movies updated: %s" % titles)

			self.__updateProgress(61, line2=utilities.getString(32064) % len(traktMoviesToUpdate))
			# Send request to update playcounts on trakt.tv
			chunksize = 200
			chunked_movies = utilities.chunks([movie for movie in traktMoviesToUpdate], chunksize)
			errorcount = 0
			i = 0
			x = float(len(traktMoviesToUpdate))
			for chunk in chunked_movies:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 11) + 61
				self.__updateProgress(int(y), line2=utilities.getString(32093) % ((i)*chunksize if (i)*chunksize < x else x, x))

				params = {'movies': chunk}
				#logger.debug("moviechunk: %s" % params)
				try:
					self.traktapi.addToHistory(params)
				except Exception as ex:
					message = utilities.createError(ex)
					logging.fatal(message)
					errorcount += 1

			logger.debug("[Movies Sync] Movies updated: %d error(s)" % errorcount)
			self.__updateProgress(72, line2=utilities.getString(32087) % len(traktMoviesToUpdate))

	def __addMoviesToKodiWatched(self, traktMovies, kodiMovies):

		if utilities.getSettingAsBool('kodi_movie_playcount') and not self.__isCanceled():
			updateKodiTraktMovies = copy.deepcopy(traktMovies)
			updateKodiKodiMovies = copy.deepcopy(kodiMovies)

			kodiMoviesToUpdate = self.__compareMovies(updateKodiTraktMovies, updateKodiKodiMovies, watched=True, restrict=True)

			if len(kodiMoviesToUpdate) == 0:
				self.__updateProgress(84, line2=utilities.getString(32088))
				logger.debug("[Movies Sync] Kodi movie playcount is up to date.")
				return

			titles = ", ".join(["%s" % (m['title']) for m in kodiMoviesToUpdate])
			logger.debug("[Movies Sync] %i movie(s) playcount will be updated in Kodi" % len(kodiMoviesToUpdate))
			logger.debug("[Movies Sync] Movies to add: %s" % titles)

			self.__updateProgress(73, line2=utilities.getString(32065) % len(kodiMoviesToUpdate))

			#split movie list into chunks of 50
			chunksize = 50
			chunked_movies = utilities.chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": kodiMoviesToUpdate[i]['movieid'], "playcount": kodiMoviesToUpdate[i]['plays']}, "id": i} for i in range(len(kodiMoviesToUpdate))], chunksize)
			i = 0
			x = float(len(kodiMoviesToUpdate))
			for chunk in chunked_movies:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 11) + 73
				self.__updateProgress(int(y), line2=utilities.getString(32089) % ((i)*chunksize if (i)*chunksize < x else x, x))

				utilities.kodiJsonRequest(chunk)

			self.__updateProgress(84, line2=utilities.getString(32090) % len(kodiMoviesToUpdate))

	def __addMovieProgressToKodi(self, traktMovies, kodiMovies):

		if utilities.getSettingAsBool('trakt_movie_playback') and traktMovies and not self.__isCanceled():
			updateKodiTraktMovies = copy.deepcopy(traktMovies)
			updateKodiKodiMovies = copy.deepcopy(kodiMovies)

			kodiMoviesToUpdate = self.__compareMovies(updateKodiTraktMovies['movies'], updateKodiKodiMovies, restrict=True, playback=True)
			if len(kodiMoviesToUpdate) == 0:
				self.__updateProgress(99, line2=utilities.getString(32125))
				logger.debug("[Movies Sync] Kodi movie playbacks are up to date.")
				return

			logger.debug("[Movies Sync] %i movie(s) playbacks will be updated in Kodi" % len(kodiMoviesToUpdate))

			self.__updateProgress(85, line2=utilities.getString(32126) % len(kodiMoviesToUpdate))
			#need to calculate the progress in int from progress in percent from trakt
			#split movie list into chunks of 50
			chunksize = 50
			chunked_movies = utilities.chunks([{"jsonrpc": "2.0", "id": i, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": kodiMoviesToUpdate[i]['movieid'], "resume": {"position": kodiMoviesToUpdate[i]['runtime']/100.0*kodiMoviesToUpdate[i]['progress']}}} for i in range(len(kodiMoviesToUpdate))], chunksize)
			i = 0
			x = float(len(kodiMoviesToUpdate))
			for chunk in chunked_movies:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 14) + 85
				self.__updateProgress(int(y), line2=utilities.getString(32127) % ((i)*chunksize if (i)*chunksize < x else x, x))
				utilities.kodiJsonRequest(chunk)

			self.__updateProgress(99, line2=utilities.getString(32128) % len(kodiMoviesToUpdate))

	def __syncMovies(self):
		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(32045), utilities.getString(32046)), utilities.getString(32061)) #Sync started
		if self.show_progress and not self.run_silent:
			progress.create("%s %s" % (utilities.getString(32045), utilities.getString(32046)), line1=" ", line2=" ", line3=" ")

		kodiMovies = self.__kodiLoadMovies()
		if not isinstance(kodiMovies, list) and not kodiMovies:
			logger.debug("[Movies Sync] Kodi movie list is empty, aborting movie Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return
		try:
			traktMovies = self.__traktLoadMovies()
		except Exception:
			logger.debug("[Movies Sync] Error getting trakt.tv movie list, aborting movie Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		traktMoviesProgress = self.__traktLoadMoviesPlaybackProgress()
		if not traktMoviesProgress:
			logger.debug("[Movies Sync] Error getting trakt.tv movie playback list, skipping playback sync.")

		self.__addMoviesToTraktCollection(kodiMovies, traktMovies)

		self.__deleteMoviesFromTraktCollection(traktMovies, kodiMovies)

		self.__addMoviesToTraktWatched(kodiMovies, traktMovies)

		self.__addMoviesToKodiWatched(traktMovies, kodiMovies)

		self.__addMovieProgressToKodi(traktMoviesProgress, kodiMovies)

		if self.show_progress and not self.run_silent:
			self.__updateProgress(100, line1=utilities.getString(32066), line2=" ", line3=" ")
			progress.close()

		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(32045), utilities.getString(32046)), utilities.getString(32062)) #Sync complete
		
		logger.debug("[Movies Sync] Movies on trakt.tv (%d), movies in Kodi (%d)." % (self.__countMovies(traktMovies), len(kodiMovies)))
		logger.debug("[Movies Sync] Complete.")

	def __compareMovies(self, movies_col1, movies_col2, watched=False, restrict=False, playback=False):
		movies = []

		for movie_col1 in movies_col1:
			if movie_col1:
				movie_col2 = utilities.findMediaObject(movie_col1, movies_col2)
				logger.debug("movie_col1 %s" % movie_col1)
				logger.debug("movie_col2 %s" % movie_col2)

				if movie_col2:  #match found
					if watched: #are we looking for watched items
						if movie_col2['watched'] == 0 and movie_col1['watched'] == 1:
							if 'movieid' not in movie_col1:
								movie_col1['movieid'] = movie_col2['movieid']
							movies.append(movie_col1)
					elif playback:
						if 'movieid' not in movie_col1:
								movie_col1['movieid'] = movie_col2['movieid']
						movie_col1['runtime'] = movie_col2['runtime']
						movies.append(movie_col1)
					else:
						if 'collected' in movie_col2 and not movie_col2['collected']:
							movies.append(movie_col1)
				else: #no match found
					if not restrict:
						if 'collected' in movie_col1 and movie_col1['collected']:
							if watched and (movie_col1['watched'] == 1):
								movies.append(movie_col1)
							elif not watched:
								movies.append(movie_col1)

		return movies

	def __countMovies(self, movies, mode='collected'):
		count = 0

		if 'movies' in movies:
			movies = movies['movies']
		for movie in movies:
			if mode in movie and movie[mode] == 1:
				count += 1

		return count

	@staticmethod
	def sanitizeMovies(movies):
		# do not remove watched_at and collected_at may cause problems between the 4 sync types (would probably have to deepcopy etc)
		for movie in movies:
			if 'collected' in movie:
				del movie['collected']
			if 'watched' in movie:
				del movie['watched']
			if 'movieid' in movie:
				del movie['movieid']
			if 'plays' in movie:
				del movie['plays']

	def __syncCheck(self, media_type):
		return self.__syncCollectionCheck(media_type) or self.__syncWatchedCheck(media_type) or self.__syncPlaybackCheck(media_type)


	def __syncPlaybackCheck(self, media_type):
		if media_type == 'movies':
			return utilities.getSettingAsBool('trakt_movie_playback')
		else:
			return utilities.getSettingAsBool('trakt_episode_playback')


	def __syncCollectionCheck(self, media_type):
		if media_type == 'movies':
			return utilities.getSettingAsBool('add_movies_to_trakt') or utilities.getSettingAsBool('clean_trakt_movies')
		else:
			return utilities.getSettingAsBool('add_episodes_to_trakt') or utilities.getSettingAsBool('clean_trakt_episodes')

	def __syncWatchedCheck(self, media_type):
		if media_type == 'movies':
			return utilities.getSettingAsBool('trakt_movie_playcount') or utilities.getSettingAsBool('kodi_movie_playcount')
		else:
			return utilities.getSettingAsBool('trakt_episode_playcount') or utilities.getSettingAsBool('kodi_episode_playcount')

	def sync(self):
		logger.debug("Starting synchronization with trakt.tv")

		if self.__syncCheck('movies'):
			if self.library in ["all", "movies"]:
				self.__syncMovies()
			else:
				logger.debug("Movie sync is being skipped for this manual sync.")
		else:
			logger.debug("Movie sync is disabled, skipping.")

		if self.__syncCheck('episodes'):
			if self.library in ["all", "episodes"]:
				if not (self.__syncCheck('movies') and self.__isCanceled()):
					self.__syncEpisodes()
				else:
					logger.debug("Episode sync is being skipped because movie sync was canceled.")
			else:
				logger.debug("Episode sync is being skipped for this manual sync.")
		else:
			logger.debug("Episode sync is disabled, skipping.")

		logger.debug("[Sync] Finished synchronization with trakt.tv")
