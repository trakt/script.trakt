# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import utilities
from utilities import Debug, notification
import copy

def findInListIndex(list, key, value):
	x = [i for i in range(len(list)) if list[i][key] == value]
	if len(x) > 0:
		return x[0]
	return -1

def findInList(list, key, value):
	result = [item for item in list if item[key] == value]
	if len(result) > 0:
		return result[0]
	return False

def findAllInList(list, key, value):
	return [item for item in list if item[key] == value]

progress = xbmcgui.DialogProgress()

class Sync():

	def __init__(self, show_progress=False, api=None):
		self.traktapi = api
		self.show_progress = show_progress
		self.notify = utilities.getSettingAsBool('show_sync_notifications')
		self.simulate = utilities.getSettingAsBool('simulate_sync')
		if self.simulate:
			Debug("[Sync] Sync is configured to be simulated.")

		if self.show_progress:
			progress.create('%s %s' % (utilities.getString(1400), utilities.getString(1402)), line1=' ', line2=' ', line3=' ')

	def isCanceled(self):
		if self.show_progress and progress.iscanceled():
			Debug("[Sync] Sync was canceled by user.")
			return True
		elif xbmc.abortRequested:
			Debug('XBMC abort requested')
			return True
		else:
			return False

	''' begin code for episode sync '''
	def traktLoadShows(self):
		Debug('[Episodes Sync] Getting episode collection from trakt.tv')
		shows = self.traktapi.getShowLibrary()
		if not isinstance(shows, list):
			Debug("[Episodes Sync] Invalid trakt.tv show list, possible error getting data from trakt, aborting trakt.tv collection update.")
			return False

		Debug('[Episodes Sync] Getting watched episodes from trakt.tv')
		watched_shows = self.traktapi.getWatchedEpisodeLibrary()
		if not isinstance(watched_shows, list):
			Debug("[Episodes Sync] Invalid trakt.tv watched show list, possible error getting data from trakt, aborting trakt.tv watched update.")
			return False

		# reformat show array
		for show in shows:
			y = {}
			w = {}
			watched = findInList(watched_shows, 'tvdb_id', show['tvdb_id'])
			for s in show['seasons']:
				y[s['season']] = s['episodes']
				w[s['season']] = []
			if watched:
				for s in watched['seasons']:
					w[s['season']] = s['episodes']
			show['seasons'] = y
			show['watched'] = w
			show['in_collection'] = True
		for watched_show in watched_shows:
			show = findInList(shows, 'tvdb_id', watched_show['tvdb_id'])
			if not show:
				y = {}
				w = {}
				for s in watched_show['seasons']:
					w[s['season']] = s['episodes']
					y[s['season']] = []
				watched_show['seasons'] = y
				watched_show['watched'] = w
				watched_show['in_collection'] = False
				shows.append(watched_show)
		return shows

	def xbmcLoadShowList(self):
		Debug("[Episodes Sync] Getting show data from XBMC")
		data = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
		if not data:
			Debug("[Episodes Sync] xbmc json request was empty.")
			return None
		
		if not 'tvshows' in data:
			Debug('[Episodes Sync] Key "tvshows" not found')
			return None

		shows = data['tvshows']
		Debug("[Episodes Sync] XBMC JSON Result: '%s'" % str(shows))

		# reformat show array
		for show in shows:
			show['in_collection'] = True
			show['tvdb_id'] = ""
			show['imdb_id'] = ""
			id = show['imdbnumber']
			if id.startswith("tt"):
				show['imdb_id'] = id
			if id.isdigit():
				show['tvdb_id'] = id
			del(show['imdbnumber'])
			del(show['label'])
		return shows

	def xbmcLoadShows(self):
		tvshows = self.xbmcLoadShowList()
		if tvshows is None:
			return None
			
		Debug("[Episodes Sync] Getting episode data from XBMC")
		for show in tvshows:
			data = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': show['tvshowid'], 'properties': ['season', 'episode', 'playcount', 'uniqueid']}, 'id': 0})
			episodes = data['episodes']
			show['seasons'] = {}
			show['watched'] = {}
			for e in episodes:
				_season = e['season']
				_episode = e['episode']
				if not _season in show['seasons']:
					show['seasons'][_season] = {}
					show['watched'][_season] = []
				if not _episode in show['seasons'][_season]:
					show['seasons'][_season][_episode] = {'id': e['episodeid'], 'episode_tvdb_id': e['uniqueid']['unknown']}
				if e['playcount'] > 0:
					if not _episode in show['watched'][_season]:
						show['watched'][_season].append(_episode)
		return tvshows

	def countEpisodes(self, shows, watched=False, collection=True, all=False):
		count = 0
		p = 'watched' if watched else 'seasons'
		for show in shows:
			if all:
				for s in show[p]:
					count += len(show[p][s])
			else:
				if 'in_collection' in show and not show['in_collection'] == collection:
					continue
				for s in show[p]:
					count += len(show[p][s])
		return count
		
	def getShowAsString(self, show, short=False):
		p = []
		if 'seasons' in show:
			for season in show['seasons']:
				s = ""
				if short:
					s = ", ".join(["S%02dE%02d" % (season, i) for i in show['seasons'][season]])
				else:
					episodes = ", ".join([str(i) for i in show['seasons'][season]])
					s = "Season: %d, Episodes: %s" % (season, episodes)
				p.append(s)
		else:
			p = ["All"]
		return "%s [tvdb: %s] - %s" % (show['title'], show['tvdb_id'], ", ".join(p))

	def traktFormatShow(self, show):
		data = {'title': show['title'], 'tvdb_id': show['tvdb_id'], 'year': show['year'], 'episodes': []}
		if 'imdb_id' in show:
			data['imdb_id'] = show['imdb_id']
		for season in show['seasons']:
			for episode in show['seasons'][season]:
				data['episodes'].append({'season': season, 'episode': episode})
		return data

	def findShow(self, show, shows):
		result = False
		if show['tvdb_id'].isdigit():
			result = findInList(shows, 'tvdb_id', show['tvdb_id'])
		if not result and show['imdb_id'].startswith("tt"):
			result = findInList(shows, 'imdb_id', show['imdb_id'])
		return result

	def compareShows(self, shows_col1, shows_col2, watched=False, restrict=False):
		shows = []
		p = 'watched' if watched else 'seasons'
		for show_col1 in shows_col1:
			show_col2 = self.findShow(show_col1, shows_col2)
			if show_col2:
				season_diff = {}
				show_col2_seasons = show_col2[p]
				for season in show_col1[p]:
					a = show_col1[p][season]
					if season in show_col2_seasons:
						b = show_col2_seasons[season]
						diff = list(set(a).difference(set(b)))
						if len(diff) > 0:
							if restrict:
								t = list(set(show_col2['seasons'][season]).intersection(set(diff)))
								if len(t) > 0:
									eps = {}
									for ep in t:
										eps[ep] = show_col2['seasons'][season][ep]
									season_diff[season] = eps
							else:
								eps = {}
								for ep in diff:
									eps[ep] = ep
								season_diff[season] = eps
					else:
						if not restrict:
							season_diff[season] = a
				if len(season_diff) > 0:
					show = {'title': show_col1['title'], 'tvdb_id': show_col1['tvdb_id'], 'year': show_col1['year'], 'seasons': season_diff}
					if 'imdb_id' in show_col1 and show_col1['imdb_id']:
						show['imdb_id'] = show_col1['imdb_id']
					if 'imdb_id' in show_col2 and show_col2['imdb_id']:
						show['imdb_id'] = show_col2['imdb_id']
					if 'tvshowid' in show_col1:
						show['tvshowid'] = show_col1['tvshowid']
					if 'tvshowid' in show_col2:
						show['tvshowid'] = show_col2['tvshowid']
					shows.append(show)
			else:
				if not restrict:
					if 'in_collection' in show_col1 and show_col1['in_collection']:
						if self.countEpisodes([show_col1], watched=watched) > 0:
							show = {'title': show_col1['title'], 'tvdb_id': show_col1['tvdb_id'], 'year': show_col1['year'], 'seasons': show_col1[p]}
							if 'tvshowid' in show_col1:
								show['tvshowid'] = show_col1['tvshowid']
							shows.append(show)
		return shows

	def traktAddEpisodes(self, shows):
		if len(shows) == 0:
			Debug("[Episodes Sync] trakt.tv episode collection is up to date.")
			return

		Debug("[Episodes Sync] %i show(s) have episodes (%d) to be added to your trakt.tv collection." % (len(shows), self.countEpisodes(shows)))
		for show in shows:
			Debug("[Episodes Sync] Episodes added: %s" % self.getShowAsString(show, short=True))
		
		if self.show_progress:
			progress.update(35, line1=utilities.getString(1435), line2='%i %s' % (len(shows), utilities.getString(1436)))

		for show in shows:
			if self.isCanceled():
				return

			epCount = self.countEpisodes([show])
			title = show['title'].encode('utf-8', 'ignore')

			if self.show_progress:
				progress.update(45, line1=utilities.getString(1435), line2=title, line3='%i %s' % (epCount, utilities.getString(1437)))

			s = self.traktFormatShow(show)
			if self.simulate:
				Debug("[Episodes Sync] %s" % str(s))
			else:
				self.traktapi.addEpisode(s)

	def traktRemoveEpisodes(self, shows):
		if len(shows) == 0:
			Debug('[Episodes Sync] trakt.tv episode collection is clean')
			return

		Debug("[Episodes Sync] %i show(s) will have episodes removed from trakt.tv collection." % len(shows))
		for show in shows:
			Debug("[Episodes Sync] Episodes removed: %s" % self.getShowAsString(show, short=True))

		if self.show_progress:
			progress.update(90, line1=utilities.getString(1445), line2='%i %s' % (len(shows), utilities.getString(1446)))

		for show in shows:
			if self.isCanceled():
				return

			epCount = self.countEpisodes([show])
			title = show['title'].encode('utf-8', 'ignore')

			if self.show_progress:
				progress.update(95, line1=utilities.getString(1445), line2=title, line3='%i %s' % (epCount, utilities.getString(1447)))

			s = self.traktFormatShow(show)
			if self.simulate:
				Debug("[Episodes Sync] %s" % str(s))
			else:
				self.traktapi.removeEpisode(s)

	def traktUpdateEpisodes(self, shows):
		if len(shows) == 0:
			Debug("[Episodes Sync] trakt.tv episode playcounts are up to date.")
			return

		Debug("[Episodes Sync] %i show(s) shows are missing playcounts on trakt.tv" % len(shows))
		for show in shows:
			Debug("[Episodes Sync] Episodes updated: %s" % self.getShowAsString(show, short=True))

		if self.show_progress:
			progress.update(65, line1=utilities.getString(1438), line2='%i %s' % (len(shows), utilities.getString(1439)))

		for show in shows:
			if self.isCanceled():
				return

			epCount = self.countEpisodes([show])
			title = show['title'].encode('utf-8', 'ignore')

			if self.show_progress:
				progress.update(70, line1=utilities.getString(1438), line2=title, line3='%i %s' % (epCount, utilities.getString(1440)))

			s = self.traktFormatShow(show)
			if self.simulate:
				Debug("[Episodes Sync] %s" % str(s))
			else:
				self.traktapi.updateSeenEpisode(s)

	def xbmcUpdateEpisodes(self, shows):
		if len(shows) == 0:
			Debug("[Episodes Sync] XBMC episode playcounts are up to date.")
			return

		Debug("[Episodes Sync] %i show(s) shows are missing playcounts on XBMC" % len(shows))
		for s in ["%s" % self.getShowAsString(s, short=True) for s in shows]:
			Debug("[Episodes Sync] Episodes updated: %s" % s)

		if self.show_progress:
			progress.update(85, line1=utilities.getString(1441), line2='%i %s' % (len(shows), utilities.getString(1439)))

		episodes = []
		for show in shows:
			for season in show['seasons']:
				for episode in show['seasons'][season]:
					episodes.append({'episodeid': show['seasons'][season][episode]['id'], 'playcount': 1})

		if self.show_progress:
			progress.update(85, line1=utilities.getString(1441), line2='', line3='%i %s' % (len(episodes), utilities.getString(1440)))

		#split episode list into chunks of 50
		chunked_episodes = utilities.chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": episodes[i], "id": i} for i in range(len(episodes))], 50)
		for chunk in chunked_episodes:
			if self.isCanceled():
				return
			if self.simulate:
				Debug("[Episodes Sync] %s" % str(chunk))
			else:
				utilities.xbmcJsonRequest(chunk)

	def syncEpisodes(self):
		if not self.show_progress and utilities.getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1406)), utilities.getString(1420)) #Sync started

		xbmcShows = self.xbmcLoadShows()
		if not isinstance(xbmcShows, list) and not xbmcShows:
			Debug("[Episodes Sync] XBMC show list is empty, aborting tv show Sync.")
			return

		traktShows = self.traktLoadShows()
		if not isinstance(traktShows, list):
			Debug("[Episodes Sync] Error getting trakt.tv show list, aborting tv show sync.")
			return

		if utilities.getSettingAsBool('add_episodes_to_trakt') and not self.isCanceled():
			traktShowsAdd = self.compareShows(xbmcShows, traktShows)
			self.traktAddEpisodes(traktShowsAdd)
		
		if utilities.getSettingAsBool('trakt_episode_playcount') and not self.isCanceled():
			traktShowsUpdate = self.compareShows(xbmcShows, traktShows, watched=True)
			self.traktUpdateEpisodes(traktShowsUpdate)

		if utilities.getSettingAsBool('xbmc_episode_playcount') and not self.isCanceled():
			xbmcShowsUpadate = self.compareShows(traktShows, xbmcShows, watched=True, restrict=True)
			self.xbmcUpdateEpisodes(xbmcShowsUpadate)

		if utilities.getSettingAsBool('clean_trakt_episodes') and not self.isCanceled():
			raktShowsRemove = self.compareShows(traktShows, xbmcShows)
			self.traktRemoveEpisodes(raktShowsRemove)

		if not self.show_progress and utilities.getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1406)), utilities.getString(1421)) #Sync complete

		if not self.isCanceled() and self.show_progress:
			progress.update(100, line1=utilities.getString(1442), line2=' ', line3=' ')
			progress.close()

		Debug("[Episodes Sync] Shows on trakt.tv (%d), shows in XBMC (%d)." % (len(findAllInList(traktShows, 'in_collection', True)), len(xbmcShows)))
		Debug("[Episodes Sync] Episodes on trakt.tv (%d), episodes in XBMC (%d)." % (self.countEpisodes(traktShows), self.countEpisodes(xbmcShows)))
		Debug("[Episodes Sync] Complete.")

	''' begin code for movie sync '''
	def traktLoadMovies(self):
		Debug("[Movies Sync] Getting movie collection from trakt.tv")
		movies = self.traktapi.getMovieLibrary()
		if not isinstance(movies, list):
			Debug("[Movies Sync] Invalid trakt.tv movie list, possible error getting data from trakt, aborting trakt.tv collection update.")
			return False

		Debug("[Movies Sync] Getting seen movies from trakt.tv")
		watched_movies = self.traktapi.getWatchedMovieLibrary()
		if not isinstance(watched_movies, list):
			Debug("[Movies Sync] Invalid trakt.tv movie seen list, possible error getting data from trakt, aborting trakt.tv watched update.")
			return False

		# reformat movie arrays
		for movie in movies:
			movie['plays'] = 0
			movie['in_collection'] = True
			if movie['imdb_id'] is None:
				movie['imdb_id'] = ""
			if movie['tmdb_id'] is None:
				movie['tmdb_id'] = ""
		for movie in watched_movies:
			m = findInList(movies, 'imdb_id', movie['imdb_id'])
			if m:
				m['plays'] = movie['plays']
			else:
				movie['in_collection'] = False
				if movie['imdb_id'] is None:
					movie['imdb_id'] = ""
				if movie['tmdb_id'] is None:
					movie['tmdb_id'] = ""
				movies.append(movie)

		return movies

	def xbmcLoadMovies(self):
		Debug("[Movies Sync] Getting movie data from XBMC")
		data = utilities.xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year', 'playcount', 'lastplayed']}})
		if not data:
			Debug("[Movies Sync] XBMC JSON request was empty.")
			return
		
		if not 'movies' in data:
			Debug('[Movies Sync] Key "movies" not found')
			return

		movies = data['movies']
		Debug("[Movies Sync] XBMC JSON Result: '%s'" % str(movies))

		# reformat movie array
		for movie in movies:
			movie['last_played'] = utilities.sqlDateToUnixDate(movie['lastplayed'])
			movie['plays'] = movie.pop('playcount')
			movie['imdb_id'] = ""
			movie['tmdb_id'] = 0
			id = movie['imdbnumber']
			if id.startswith("tt"):
				movie['imdb_id'] = id
			if id.isdigit():
				movie['tmdb_id'] = int(id)
			del(movie['imdbnumber'])
			del(movie['lastplayed'])
			del(movie['label'])
		return movies

	def sanitizeMovieData(self, movie):
		data = copy.deepcopy(movie)
		if 'in_collection' in data:
			del(data['in_collection'])
		if 'movieid' in data:
			del(data['movieid'])
		if not data['tmdb_id']:
			del(data['tmdb_id'])
		return data

	def countMovies(self, movies, collection=True):
		if len(movies) > 0:
			if 'in_collection' in movies[0]:
				return len(findAllInList(movies, 'in_collection', collection))
			else:
				return len(movies)
		return 0

	def findMovie(self, movie, movies):
		result = False
		if movie['imdb_id'].startswith("tt"):
			result = findInList(movies, 'imdb_id', movie['imdb_id'])
		if not result and movie['tmdb_id'] > 0:
			result = findInList(movies, 'tmdb_id', movie['tmdb_id'])
		return result

	def compareMovies(self, movies_col1, movies_col2, watched=False, restrict=False):
		movies = []
		for movie_col1 in movies_col1:
			movie_col2 = self.findMovie(movie_col1, movies_col2)
			if movie_col2:
				if watched:
					if (movie_col2['plays'] == 0) and (movie_col1['plays'] > movie_col2['plays']):
						if 'movieid' not in movie_col1:
							movie_col1['movieid'] = movie_col2['movieid']
						movies.append(movie_col1)
				else:
					if 'in_collection' in movie_col2 and not movie_col2['in_collection']:
						movies.append(movie_col1)
			else:
				if not restrict:
					if watched and (movie_col1['plays'] > 0):
						movies.append(movie_col1)
					elif not watched:
						movies.append(movie_col1)
		return movies

	def traktAddMovies(self, movies):
		if len(movies) == 0:
			Debug("[Movies Sync] trakt.tv movie collection is up to date.")
			return
		
		titles = ", ".join(["%s (%s)" % (m['title'], m['imdb_id']) for m in movies])
		Debug("[Movies Sync] %i movie(s) will be added to trakt.tv collection." % len(movies))
		Debug("[Movies Sync] Movies added: %s" % titles)

		if self.show_progress:
			progress.update(45, line2='%i %s' % (len(movies), utilities.getString(1426)))

		params = {'movies': [self.sanitizeMovieData(movie) for movie in movies]}
		if self.simulate:
			Debug("[Movies Sync] %s" % str(params))
		else:
			self.traktapi.addMovie(params)

	def traktRemoveMovies(self, movies):
		if len(movies) == 0:
			Debug("[Movies Sync] trakt.tv movie collection is clean.")
			return
		
		titles = ", ".join(["%s (%s)" % (m['title'], m['imdb_id']) for m in movies])
		Debug("[Movies Sync] %i movie(s) will be removed from trakt.tv collection." % len(movies))
		Debug("[Movies Sync] Movies removed: %s" % titles)

		if self.show_progress:
			progress.update(95, line2='%i %s' % (len(movies), utilities.getString(1444)))
		
		params = {'movies': [self.sanitizeMovieData(movie) for movie in movies]}
		if self.simulate:
			Debug("[Movies Sync] %s" % str(params))
		else:
			self.traktapi.removeMovie(params)

	def traktUpdateMovies(self, movies):
		if len(movies) == 0:
			Debug("[Movies Sync] trakt.tv movie playcount is up to date")
			return
		
		titles = ", ".join(["%s (%s)" % (m['title'], m['imdb_id']) for m in movies])
		Debug("[Movies Sync] %i movie(s) playcount will be updated on trakt.tv" % len(movies))
		Debug("[Movies Sync] Movies updated: %s" % titles)

		if self.show_progress:
			progress.update(75, line2='%i %s' % (len(movies), utilities.getString(1428)))

		# Send request to update playcounts on trakt.tv
		params = {'movies': [self.sanitizeMovieData(movie) for movie in movies]}
		if self.simulate:
			Debug("[Movies Sync] %s" % str(params))
		else:
			self.traktapi.updateSeenMovie(params)

	def xbmcUpdateMovies(self, movies):
		if len(movies) == 0:
			Debug("[Movies Sync] XBMC movie playcount is up to date.")
			return
		
		titles = ", ".join(["%s (%s)" % (m['title'], m['imdb_id']) for m in movies])
		Debug("[Movies Sync] %i movie(s) playcount will be updated in XBMC" % len(movies))
		Debug("[Movies Sync] Movies updated: %s" % titles)
		if self.show_progress:
			progress.update(90, line2='%i %s' % (len(movies), utilities.getString(1430)))

		#split movie list into chunks of 50
		chunked_movies = utilities.chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": movies[i]['movieid'], "playcount": movies[i]['plays']}, "id": i} for i in range(len(movies))], 50)
		for chunk in chunked_movies:
			if self.isCanceled():
				return
			if self.simulate:
				Debug("[Movies Sync] %s" % str(chunk))
			else:
				utilities.xbmcJsonRequest(chunk)

	def syncMovies(self):
		if not self.show_progress and utilities.getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1402)), utilities.getString(1420)) #Sync started

		xbmcMovies = self.xbmcLoadMovies()
		if not isinstance(xbmcMovies, list) and not xbmcMovies:
			Debug("[Movies Sync] XBMC movie list is empty, aborting movie Sync.")
			return

		traktMovies = self.traktLoadMovies()
		if not isinstance(traktMovies, list):
			Debug("[Movies Sync] Error getting trakt.tv movie list, aborting movie Sync.")
			return

		if utilities.getSettingAsBool('add_movies_to_trakt') and not self.isCanceled():
			traktMoviesToAdd = self.compareMovies(xbmcMovies, traktMovies)
			self.traktAddMovies(traktMoviesToAdd)
		
		if utilities.getSettingAsBool('trakt_movie_playcount') and not self.isCanceled():
			traktMoviesToUpdate = self.compareMovies(xbmcMovies, traktMovies, watched=True)
			self.traktUpdateMovies(traktMoviesToUpdate)

		if utilities.getSettingAsBool('xbmc_movie_playcount') and not self.isCanceled():
			xbmcMoviesToUpdate = self.compareMovies(traktMovies, xbmcMovies, watched=True, restrict=True)
			self.xbmcUpdateMovies(xbmcMoviesToUpdate)

		if utilities.getSettingAsBool('clean_trakt_movies') and not self.isCanceled():
			traktMoviesToRemove = self.compareMovies(traktMovies, xbmcMovies)
			self.traktRemoveMovies(traktMoviesToRemove)

		if not self.isCanceled() and self.show_progress:
			progress.update(100, line1=utilities.getString(1431), line2=' ', line3=' ')
			progress.close()

		if not self.show_progress and utilities.getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (utilities.getString(1400), utilities.getString(1402)), utilities.getString(1421)) #Sync complete
		
		Debug("[Movies Sync] Movies on trakt.tv (%d), movies in XBMC (%d)." % (len(traktMovies), self.countMovies(xbmcMovies)))
		Debug("[Movies Sync] Complete.")

	def syncCheck(self, media_type):
		if media_type == 'movies':
			return utilities.getSettingAsBool('add_movies_to_trakt') or utilities.getSettingAsBool('trakt_movie_playcount') or utilities.getSettingAsBool('xbmc_movie_playcount') or utilities.getSettingAsBool('clean_trakt_movies')
		else:
			return utilities.getSettingAsBool('add_episodes_to_trakt') or utilities.getSettingAsBool('trakt_episode_playcount') or utilities.getSettingAsBool('xbmc_episode_playcount') or utilities.getSettingAsBool('clean_trakt_episodes')

		return False

	def sync(self):
		Debug("[Sync] Starting synchronization with trakt.tv")

		if self.syncCheck('movies'):
			self.syncMovies()
		else:
			Debug("[Sync] Movie sync is disabled, skipping.")

		if self.syncCheck('episodes'):
			self.syncEpisodes()
		else:
			Debug("[Sync] Episode sync is disabled, skipping.")

		Debug("[Sync] Finished synchronization with trakt.tv")
	