# -*- coding: utf-8 -*-

import copy
import xbmc
import xbmcgui
import utilities
from utilities import Debug, notification

progress = xbmcgui.DialogProgress()

class Sync():

	def __init__(self, show_progress=False, run_silent=False, library="all", api=None):
		self.traktapi = api
		self.show_progress = show_progress
		self.run_silent = run_silent
		self.library = library
		if self.show_progress and self.run_silent:
			Debug("[Sync] Sync is being run silently.")
		self.sync_on_update = utilities.getSettingAsBool('sync_on_update')
		self.notify = utilities.getSettingAsBool('show_sync_notifications')
		self.notify_during_playback = not (xbmc.Player().isPlayingVideo() and utilities.getSettingAsBool("hide_notifications_playback"))

	def __isCanceled(self):
		if self.show_progress and not self.run_silent and progress.iscanceled():
			Debug("[Sync] Sync was canceled by user.")
			return True
		elif xbmc.abortRequested:
			Debug('Kodi abort requested')
			return True
		else:
			return False

	def __updateProgress(self, *args, **kwargs):
		if self.show_progress and not self.run_silent:
			kwargs['percent'] = args[0]
			progress.update(**kwargs)

	''' begin code for episode sync '''
	def __kodiLoadShows(self):
		self.__updateProgress(1, line1=utilities.getString(1480), line2=utilities.getString(1481))

		Debug("[Episodes Sync] Getting show data from Kodi")
		data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
		if data['limits']['total'] == 0:
			Debug("[Episodes Sync] Kodi json request was empty.")
			return None

		tvshows = utilities.kodiRpcToTraktMediaObjects(data)
		Debug("[Episode Sync] Getting shows from kodi finished %s" % tvshows)

		if tvshows is None:
			return None
		self.__updateProgress(2, line2=utilities.getString(1482))
		result = {'shows': []}
		i = 0
		x = float(len(tvshows))
		Debug("[Episodes Sync] Getting episode data from Kodi")
		for show_col1 in tvshows:
			i += 1
			y = ((i / x) * 8) + 2
			self.__updateProgress(int(y), line2=utilities.getString(1483) % (i, x))

			show = {'title': show_col1['title'], 'ids': {}, 'year': show_col1['year'], 'seasons': []}

			if 'ids' in show_col1 and 'tvdb' in show_col1['ids']:
				show['ids'] = {'tvdb': show_col1['ids']['tvdb']}

			data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': show_col1['tvshowid'], 'properties': ['season', 'episode', 'playcount', 'uniqueid', 'lastplayed', 'file', 'dateadded']}, 'id': 0})
			if not data:
				Debug("[Episodes Sync] There was a problem getting episode data for '%s', aborting sync." % show['title'])
				return None
			elif 'episodes' not in data:
				Debug("[Episodes Sync] '%s' has no episodes in Kodi." % show['title'])
				continue

			seasons = utilities.kodiRpcToTraktMediaObjects(data)

			show['seasons'] = seasons

			if 'tvshowid' in show_col1:
				del(show_col1['tvshowid'])
			result['shows'].append(show)

		self.__updateProgress(10, line2=utilities.getString(1484))
		return result

	def __traktLoadShows(self):
		self.__updateProgress(10, line1=utilities.getString(1485), line2=utilities.getString(1486))

		Debug('[Episodes Sync] Getting episode collection from trakt.tv')
		try:
			traktShows = {}
			traktShows = self.traktapi.getShowsCollected(traktShows)

			self.__updateProgress(12, line2=utilities.getString(1487))
			traktShows = self.traktapi.getShowsWatched(traktShows)
			traktShows = traktShows.items()
		except Exception:
			Debug("[Episodes Sync] Invalid trakt.tv show list, possible error getting data from trakt, aborting trakt.tv collection update.")
			return False

		i = 0
		x = float(len(traktShows))
		shows = {'shows': []}
		for key, show in traktShows:
			i += 1
			y = ((i / x) * 20) + 12
			self.__updateProgress(int(y), line2=utilities.getString(1488) % (i, x))

			#will keep the data in python structures - just like the KODI response
			show = show.to_dict()
			
			shows['shows'].append(show)

		self.__updateProgress(32, line2=utilities.getString(1489))

		return shows

	def __traktRemoveEpisodes(self, traktShows, kodiShows):
		if utilities.getSettingAsBool('clean_trakt_episodes') and not self.__isCanceled():
			removeTraktShows = copy.deepcopy(traktShows)
			removeKodiShows = copy.deepcopy(kodiShows)

			traktShowsRemove = self.__compareShows(removeTraktShows, removeKodiShows)
			self.sanitizeShows(traktShowsRemove)

			if len(traktShowsRemove['shows']) == 0:
				self.__updateProgress(48, line1=utilities.getString(1445), line2=utilities.getString(1496))
				Debug('[Episodes Sync] trakt.tv episode collection is clean, no episodes to remove.')
				return

			Debug("[Episodes Sync] %i show(s) will have episodes removed from trakt.tv collection." % len(traktShowsRemove['shows']))
			for show in traktShowsRemove['shows']:
				Debug("[Episodes Sync] Episodes removed: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(33, line1=utilities.getString(1445), line2=utilities.getString(1497) % self.__countEpisodes(traktShowsRemove), line3=" ")

			Debug("[traktRemoveEpisodes] Shows to remove %s" % traktShowsRemove)
			result = self.traktapi.removeFromCollection(traktShowsRemove)
			Debug("[traktRemoveEpisodes] Result %s" % result)

			self.__updateProgress(48, line2=utilities.getString(1498) % self.__countEpisodes(traktShowsRemove), line3=" ")

	def __traktUpdateEpisodes(self, kodiShows, traktShows):
		if utilities.getSettingAsBool('trakt_episode_playcount') and not self.__isCanceled():
			updateTraktTraktShows = copy.deepcopy(traktShows)
			updateTraktKodiShows = copy.deepcopy(kodiShows)

			traktShowsUpdate = self.__compareShows(updateTraktKodiShows, updateTraktTraktShows, watched=True)
			self.sanitizeShows(traktShowsUpdate)
			Debug("traktShowsUpdate %s" % traktShowsUpdate)

			if len(traktShowsUpdate['shows']) == 0:
				self.__updateProgress(65, line1=utilities.getString(1438), line2=utilities.getString(1492))
				Debug("[Episodes Sync] trakt.tv episode playcounts are up to date.")
				return

			Debug("[Episodes Sync] %i show(s) are missing playcounts on trakt.tv" % len(traktShowsUpdate['shows']))
			for show in traktShowsUpdate['shows']:
				Debug("[Episodes Sync] Episodes updated: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(49, line1=utilities.getString(1438), line2=utilities.getString(1437) % (len(traktShowsUpdate['shows'])), line3="")

			i = 0
			x = float(len(traktShowsUpdate['shows']))
			for show in traktShowsUpdate['shows']:
				if self.__isCanceled():
					return
				epCount = self.__countEpisodes([show])
				title = show['title'].encode('utf-8', 'ignore')
				i += 1
				y = ((i / x) * 16) + 49
				self.__updateProgress(int(y), line2=title, line3=utilities.getString(1440) % epCount)

				s = { 'shows': [show]}
				Debug("[traktUpdateEpisodes] Shows to update %s" % s)
				result = self.traktapi.addToHistory(s)
				Debug("[traktUpdateEpisodes] Result %s" % result)

			self.__updateProgress(65, line2=utilities.getString(1439) % (len(traktShowsUpdate['shows'])), line3="")

	def __kodiUpdateEpisodes(self, traktShows, kodiShows):
		if utilities.getSettingAsBool('kodi_episode_playcount') and not self.__isCanceled():
			updateKodiTraktShows = copy.deepcopy(traktShows)
			updateKodiKodiShows = copy.deepcopy(kodiShows)

			kodiShowsUpadate = self.__compareShows(updateKodiTraktShows, updateKodiKodiShows, watched=True, restrict=True)

			if len(kodiShowsUpadate['shows']) == 0:
				self.__updateProgress(82, line1=utilities.getString(1441), line2=utilities.getString(1493))
				Debug("[Episodes Sync] Kodi episode playcounts are up to date.")
				return

			Debug("[Episodes Sync] %i show(s) shows are missing playcounts on Kodi" % len(kodiShowsUpadate['shows']))
			for s in ["%s" % self.__getShowAsString(s, short=True) for s in kodiShowsUpadate['shows']]:
				Debug("[Episodes Sync] Episodes updated: %s" % s)

			Debug("kodiShowsUpadate: %s" % kodiShowsUpadate)
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
				y = ((i / x) * 16) + 66
				self.__updateProgress(int(y), line2=utilities.getString(1494) % ((i)*chunksize if (i)*chunksize < x else x, x))

				Debug("[Episodes Sync] chunk %s" % str(chunk))
				result = utilities.kodiJsonRequest(chunk)
				Debug("[Episodes Sync] result %s" % str(result))

			self.__updateProgress(82, line2=utilities.getString(1495) % len(episodes))

	def __traktAddEpisodes(self, kodiShows, traktShows):
		if utilities.getSettingAsBool('add_episodes_to_trakt') and not self.__isCanceled():
			addTraktShows = copy.deepcopy(traktShows)
			addKodiShows = copy.deepcopy(kodiShows)

			tmpTraktShowsAdd = self.__compareShows(addKodiShows, addTraktShows)
			traktShowsAdd = copy.deepcopy(tmpTraktShowsAdd)
			self.sanitizeShows(traktShowsAdd)
			Debug("traktShowsAdd %s" % traktShowsAdd)

			if len(traktShowsAdd['shows']) == 0:
				self.__updateProgress(98, line1=utilities.getString(1435), line2=utilities.getString(1490))
				Debug("[Episodes Sync] trakt.tv episode collection is up to date.")
				return
			Debug("[Episodes Sync] %i show(s) have episodes (%d) to be added to your trakt.tv collection." % (len(traktShowsAdd['shows']), self.__countEpisodes(traktShowsAdd)))
			for show in traktShowsAdd['shows']:
				Debug("[Episodes Sync] Episodes added: %s" % self.__getShowAsString(show, short=True))

			self.__updateProgress(82, line1=utilities.getString(1435), line2=utilities.getString(1434) % (len(traktShowsAdd['shows'])), line3=" ")

			#split episode list into chunks of 50
			chunksize = 1
			chunked_episodes = utilities.chunks(traktShowsAdd['shows'], chunksize)
			i = 0
			x = float(len(traktShowsAdd['shows']))
			for chunk in chunked_episodes:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 82
				self.__updateProgress(int(y), line2=utilities.getString(1436) % ((i)*chunksize if (i)*chunksize < x else x, x))

				request = {'shows': chunk}
				Debug("[traktAddEpisodes] Shows to add %s" % request)
				result = self.traktapi.addToCollection(request)
				Debug("[traktAddEpisodes] Result %s" % result)

			self.__updateProgress(98, line2=utilities.getString(1491) % self.__countEpisodes(traktShowsAdd))

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

	def __getEpisodes(self, seasons, watched=False):
		data = {}
		for season in seasons:
			episodes = {}
			for episode in season['episodes']:
				if watched and 'watched' in episode and episode['watched'] == 0:
						continue
				elif 'collected' in episode and episode['collected'] == 0:
						continue
				episodes[episode['number']] = episode
			data[season['number']] = episodes

		return data

	#always return shows_col1 if you have enrich it, but don't return shows_col2
	def __compareShows(self, shows_col1, shows_col2, watched=False, restrict=False):
		shows = []
		for show_col1 in shows_col1['shows']:
			if show_col1:
				show_col2 = utilities.findMediaObject(show_col1, shows_col2['shows'])
				#Debug("show_col1 %s" % show_col1)
				#Debug("show_col2 %s" % show_col2)

				if show_col2:
					season_diff = {}
					# format the data to be easy to compare trakt and KODI data
					season_col1 = self.__getEpisodes(show_col1['seasons'], watched)
					season_col2 = self.__getEpisodes(show_col2['seasons'], watched)
					for season in season_col1:
						a = season_col1[season]
						if season in season_col2:
							b = season_col2[season]
							diff = list(set(a).difference(set(b)))
							if len(diff) > 0:
								if restrict:
									# get all the episodes that we have in Kodi, watched or not - update kodi
									_seasons = self.__getEpisodes(show_col2['seasons'], False)
									t = list(set(_seasons[season]).intersection(set(diff)))
									if len(t) > 0:
										eps = {}
										for ep in t:
											eps[ep] = a[ep]
											if 'episodeid' in _seasons[season][ep]['ids']:
												if 'ids' in eps:
													eps[ep]['ids']['episodeid'] = _seasons[season][ep]['ids']['episodeid']
												else:
													eps[ep]['ids'] = {'episodeid': _seasons[season][ep]['ids']['episodeid']}
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
					if len(season_diff) > 0:
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
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1406)), utilities.getString(1420)) #Sync started
		if self.show_progress and not self.run_silent:
			progress.create("%s %s" % (utilities.getString(1400), utilities.getString(1406)), line1=" ", line2=" ", line3=" ")

		kodiShows = self.__kodiLoadShows()
		if not isinstance(kodiShows, list) and not kodiShows:
			Debug("[Episodes Sync] Kodi show list is empty, aborting tv show Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		traktShows = self.__traktLoadShows()
		if not traktShows:
			Debug("[Episodes Sync] Error getting trakt.tv show list, aborting tv show sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		self.__traktRemoveEpisodes(traktShows, kodiShows)

		self.__traktUpdateEpisodes(kodiShows, traktShows)
		
		self.__kodiUpdateEpisodes(traktShows, kodiShows)

		self.__traktAddEpisodes(kodiShows, traktShows)


		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1406)), utilities.getString(1421)) #Sync complete

		if self.show_progress and not self.run_silent:
			self.__updateProgress(100, line1=" ", line2=utilities.getString(1442), line3=" ")
			progress.close()

		Debug("[Episodes Sync] Shows on trakt.tv (%d), shows in Kodi (%d)." % (len(traktShows['shows']), len(kodiShows['shows'])))

		Debug("[Episodes Sync] Episodes on trakt.tv (%d), episodes in Kodi (%d)." % (self.__countEpisodes(traktShows), self.__countEpisodes(kodiShows)))
		Debug("[Episodes Sync] Complete.")

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
		self.__updateProgress(1, line2=utilities.getString(1460))

		Debug("[Movies Sync] Getting movie data from Kodi")
		data = utilities.kodiJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year', 'playcount', 'lastplayed', 'file', 'dateadded']}})
		if data['limits']['total'] == 0:
			Debug("[Movies Sync] Kodi JSON request was empty.")
			return

		kodi_movies = utilities.kodiRpcToTraktMediaObjects(data)

		self.__updateProgress(10, line2=utilities.getString(1461))

		return kodi_movies

	def __traktLoadMovies(self):
		self.__updateProgress(10, line2=utilities.getString(1462))

		Debug("[Movies Sync] Getting movie collection from trakt.tv")

		traktMovies = {}
		traktMovies = self.traktapi.getMoviesCollected(traktMovies)

		self.__updateProgress(21, line2=utilities.getString(1463))
		traktMovies = self.traktapi.getMoviesWatched(traktMovies)
		traktMovies = traktMovies.items()

		self.__updateProgress(32, line2=utilities.getString(1466))
		movies = []
		for key, movie in traktMovies:
			movie = movie.to_dict()
			
			movies.append(movie)

		return movies

	def __traktRemoveMovies(self, traktMovies, kodiMovies):

		if utilities.getSettingAsBool('clean_trakt_movies') and not self.__isCanceled():
			removeTraktMovies = copy.deepcopy(traktMovies)
			removeKodiMovies = copy.deepcopy(kodiMovies)

			Debug("[Movies Sync] Starting to remove.")
			traktMoviesToRemove = self.__compareMovies(removeTraktMovies, removeKodiMovies)
			self.sanitizeMovies(traktMoviesToRemove)
			Debug("[Movies Sync] Compared movies, found %s to remove." % len(traktMoviesToRemove))

			if len(traktMoviesToRemove) == 0:
				self.__updateProgress(48, line2=utilities.getString(1474))
				Debug("[Movies Sync] trakt.tv movie collection is clean, no movies to remove.")
				return

			titles = ", ".join(["%s" % (m['title']) for m in traktMoviesToRemove])
			Debug("[Movies Sync] %i movie(s) will be removed from trakt.tv collection." % len(traktMoviesToRemove))
			Debug("[Movies Sync] Movies removed: %s" % titles)

			self.__updateProgress(33, line2=utilities.getString(1444) % len(traktMoviesToRemove))

			moviesToRemove = {'movies': traktMoviesToRemove}

			self.traktapi.removeFromCollection(moviesToRemove)

			self.__updateProgress(48, line2=utilities.getString(1475) % len(traktMoviesToRemove))


	def __traktUpdateMovies(self, kodiMovies, traktMovies):

		if utilities.getSettingAsBool('trakt_movie_playcount') and not self.__isCanceled():
			updateTraktTraktMovies = copy.deepcopy(traktMovies)
			updateTraktKodiMovies = copy.deepcopy(kodiMovies)

			traktMoviesToUpdate = self.__compareMovies(updateTraktKodiMovies, updateTraktTraktMovies, watched=True)
			self.sanitizeMovies(traktMoviesToUpdate)

			if len(traktMoviesToUpdate) == 0:
				self.__updateProgress(65, line2=utilities.getString(1469))
				Debug("[Movies Sync] trakt.tv movie playcount is up to date")
				return

			titles = ", ".join(["%s" % (m['title']) for m in traktMoviesToUpdate])
			Debug("[Movies Sync] %i movie(s) playcount will be updated on trakt.tv" % len(traktMoviesToUpdate))
			Debug("[Movies Sync] Movies updated: %s" % titles)

			self.__updateProgress(49, line2=utilities.getString(1428) % len(traktMoviesToUpdate))
			# Send request to update playcounts on trakt.tv
			chunksize = 200
			chunked_movies = utilities.chunks([movie for movie in traktMoviesToUpdate], chunksize)
			i = 0
			x = float(len(traktMoviesToUpdate))
			for chunk in chunked_movies:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 49
				self.__updateProgress(int(y), line2=utilities.getString(1478) % ((i)*chunksize if (i)*chunksize < x else x, x))

				params = {'movies': chunk}
				Debug("moviechunk: %s" % params)
				self.traktapi.addToHistory(params)

			self.__updateProgress(65, line2=utilities.getString(1470) % len(traktMoviesToUpdate))

	def __kodiUpdateMovies(self, traktMovies, kodiMovies):

		if utilities.getSettingAsBool('kodi_movie_playcount') and not self.__isCanceled():
			updateKodiTraktMovies = copy.deepcopy(traktMovies)
			updateKodiKodiMovies = copy.deepcopy(kodiMovies)

			kodiMoviesToUpdate = self.__compareMovies(updateKodiTraktMovies, updateKodiKodiMovies, watched=True, restrict=True)

			if len(kodiMoviesToUpdate) == 0:
				self.__updateProgress(82, line2=utilities.getString(1471))
				Debug("[Movies Sync] Kodi movie playcount is up to date.")
				return

			Debug("[Movies Sync] %i movie(s) playcount will be updated in Kodi" % len(kodiMoviesToUpdate))

			self.__updateProgress(66, line2=utilities.getString(1430) % len(kodiMoviesToUpdate))

			#split movie list into chunks of 50
			chunksize = 50
			chunked_movies = utilities.chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": kodiMoviesToUpdate[i]['movieid'], "playcount": kodiMoviesToUpdate[i]['plays']}, "id": i} for i in range(len(kodiMoviesToUpdate))], chunksize)
			i = 0
			x = float(len(kodiMoviesToUpdate))
			for chunk in chunked_movies:
				if self.__isCanceled():
					return
				i += 1
				y = ((i / x) * 16) + 66
				self.__updateProgress(int(y), line2=utilities.getString(1472) % ((i)*chunksize if (i)*chunksize < x else x, x))

				utilities.kodiJsonRequest(chunk)

			self.__updateProgress(82, line2=utilities.getString(1473) % len(kodiMoviesToUpdate))

	def __traktAddMovies(self, kodiMovies, traktMovies):
		if utilities.getSettingAsBool('add_movies_to_trakt') and not self.__isCanceled():
			addTraktMovies = copy.deepcopy(traktMovies)
			addKodiMovies = copy.deepcopy(kodiMovies)

			traktMoviesToAdd = self.__compareMovies(addKodiMovies, addTraktMovies)
			self.sanitizeMovies(traktMoviesToAdd)
			Debug("[Movies Sync] Compared movies, found %s to add." % len(traktMoviesToAdd))

			if len(traktMoviesToAdd) == 0:
				self.__updateProgress(98, line2=utilities.getString(1467))
				Debug("[Movies Sync] trakt.tv movie collection is up to date.")
				return

			Debug("[Movies Sync] %i movie(s) will be added to trakt.tv collection." % len(traktMoviesToAdd))

			self.__updateProgress(83, line2=utilities.getString(1426) % len(traktMoviesToAdd))

			moviesToAdd = {'movies': traktMoviesToAdd}
			Debug("Movies to add: %s" % moviesToAdd)
			self.traktapi.addToCollection(moviesToAdd)

			self.__updateProgress(98, line2=utilities.getString(1468) % len(traktMoviesToAdd))

	def __syncMovies(self):
		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1402)), utilities.getString(1420)) #Sync started
		if self.show_progress and not self.run_silent:
			progress.create("%s %s" % (utilities.getString(1400), utilities.getString(1402)), line1=" ", line2=" ", line3=" ")

		kodiMovies = self.__kodiLoadMovies()
		if not isinstance(kodiMovies, list) and not kodiMovies:
			Debug("[Movies Sync] Kodi movie list is empty, aborting movie Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return
		try:
			traktMovies = self.__traktLoadMovies()
		except Exception:
			Debug("[Movies Sync] Error getting trakt.tv movie list, aborting movie Sync.")
			if self.show_progress and not self.run_silent:
				progress.close()
			return

		self.__traktRemoveMovies(traktMovies, kodiMovies)

		self.__traktUpdateMovies(kodiMovies, traktMovies)

		self.__kodiUpdateMovies(traktMovies, kodiMovies)

		self.__traktAddMovies(kodiMovies, traktMovies)

		if self.show_progress and not self.run_silent:
			self.__updateProgress(100, line1=utilities.getString(1431), line2=" ", line3=" ")
			progress.close()

		if not self.show_progress and self.sync_on_update and self.notify and self.notify_during_playback:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1402)), utilities.getString(1421)) #Sync complete
		
		Debug("[Movies Sync] Movies on trakt.tv (%d), movies in Kodi (%d)." % (self.__countMovies(traktMovies), len(kodiMovies)))
		Debug("[Movies Sync] Complete.")

	def __compareMovies(self, movies_col1, movies_col2, watched=False, restrict=False):
		movies = []

		for movie_col1 in movies_col1:
			if movie_col1:
				movie_col2 = utilities.findMediaObject(movie_col1, movies_col2)
				#Debug("movie_col1 %s" % movie_col1)
				#Debug("movie_col2 %s" % movie_col2)

				if movie_col2:  #match found
					if watched: #are we looking for watched items
						if movie_col2['watched'] == 0 and movie_col1['watched'] == 1:
							if 'movieid' not in movie_col1:
								movie_col1['movieid'] = movie_col2['movieid']
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
		if media_type == 'movies':
			return utilities.getSettingAsBool('add_movies_to_trakt') or utilities.getSettingAsBool('trakt_movie_playcount') or utilities.getSettingAsBool('kodi_movie_playcount') or utilities.getSettingAsBool('clean_trakt_movies')
		else:
			return utilities.getSettingAsBool('add_episodes_to_trakt') or utilities.getSettingAsBool('trakt_episode_playcount') or utilities.getSettingAsBool('kodi_episode_playcount') or utilities.getSettingAsBool('clean_trakt_episodes')

	def sync(self):
		Debug("[Sync] Starting synchronization with trakt.tv")

		if self.__syncCheck('movies'):
			if self.library in ["all", "movies"]:
				self.__syncMovies()
			else:
				Debug("[Sync] Movie sync is being skipped for this manual sync.")
		else:
			Debug("[Sync] Movie sync is disabled, skipping.")

		if self.__syncCheck('episodes'):
			if self.library in ["all", "episodes"]:
				if not (self.__syncCheck('movies') and self.__isCanceled()):
					self.__syncEpisodes()
				else:
					Debug("[Sync] Episode sync is being skipped because movie sync was canceled.")
			else:
				Debug("[Sync] Episode sync is being skipped for this manual sync.")
		else:
			Debug("[Sync] Episode sync is disabled, skipping.")

		Debug("[Sync] Finished synchronization with trakt.tv")
	
