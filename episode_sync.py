# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
from utilities import xbmcJsonRequest, Debug, notification, chunks, getSettingAsBool, getString

add_episodes_to_trakt = getSettingAsBool('add_episodes_to_trakt')
trakt_episode_playcount = getSettingAsBool('trakt_episode_playcount')
xbmc_episode_playcount = getSettingAsBool('xbmc_episode_playcount')
clean_trakt_episodes = getSettingAsBool('clean_trakt_episodes')

progress = xbmcgui.DialogProgress()

def compare_show(xbmc_show, trakt_show):
	missing = []
	trakt_seasons = [x['season'] for x in trakt_show['seasons']]

	for xbmc_episode in xbmc_show['episodes']:
		if xbmc_episode['season'] not in trakt_seasons:
			missing.append(xbmc_episode)
		else:
			for trakt_season in trakt_show['seasons']:
				if xbmc_episode['season'] == trakt_season['season']:
					if xbmc_episode['episode'] not in trakt_season['episodes']:
						missing.append(xbmc_episode)

	return missing

def compare_show_watched_trakt(xbmc_show, trakt_show):
	missing = []

	for xbmc_episode in xbmc_show['episodes']:
		if xbmc_episode['playcount']:
			if xbmc_episode['season'] not in [x['season'] for x in trakt_show['seasons']]:
				missing.append(xbmc_episode)
			else:
				for trakt_season in trakt_show['seasons']:
					if xbmc_episode['season'] == trakt_season['season']:
						if xbmc_episode['episode'] not in trakt_season['episodes']:
							missing.append(xbmc_episode)

	return missing

def compare_show_watched_xbmc(xbmc_show, trakt_show):
	missing = []

	for xbmc_episode in xbmc_show['episodes']:
		if not xbmc_episode['playcount']:
			for trakt_season in trakt_show['seasons']:
				if xbmc_episode['season'] == trakt_season['season']:
					if xbmc_episode['episode'] in trakt_season['episodes']:
						missing.append(xbmc_episode)

	return missing

class SyncEpisodes():
	def __init__(self, show_progress=False, api=None):
		self.traktapi = api
		self.xbmc_shows = []
		self.trakt_shows = {'collection': [], 'watched': []}
		self.notify = getSettingAsBool('show_sync_notifications')
		self.show_progress = show_progress

		if self.show_progress:
			progress.create('%s %s' % (getString(1400), getString(1406)), line1=' ', line2=' ', line3=' ')

	def Canceled(self):
		if self.show_progress and progress.iscanceled():
			Debug("[Episodes Sync] Sync was canceled by user.")
			return True
		elif xbmc.abortRequested:
			Debug('XBMC abort requested')
			return True
		else:
			return False

	def GetFromXBMC(self):
		Debug("[Episodes Sync] Getting episodes from XBMC")
		if self.show_progress:
			progress.update(5, line1=getString(1432), line2=' ', line3=' ')

		shows = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber']}, 'id': 0})

		# sanity check, test for empty result
		if not shows:
			Debug("[Episodes Sync] xbmc json request was empty.")
			return

		# test to see if tvshows key exists in xbmc json request
		if 'tvshows' in shows:
			shows = shows['tvshows']
			Debug("[Episodes Sync] XBMC JSON Result: '%s'" % str(shows))
		else:
			Debug("[Episodes Sync] Key 'tvshows' not found")
			return

		if self.show_progress:
			progress.update(10, line1=getString(1433), line2=' ', line3=' ')

		for show in shows:
			if self.Canceled():
				return
			show['episodes'] = []

			episodes = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': show['tvshowid'], 'properties': ['season', 'episode', 'playcount', 'uniqueid']}, 'id': 0})
			if 'episodes' in episodes:
				episodes = episodes['episodes']

				show['episodes'] = [x for x in episodes if type(x) == type(dict())]

		self.xbmc_shows = [x for x in shows if x['episodes']]

	def GetCollectionFromTrakt(self):
		Debug('[Episodes Sync] Getting episode collection from trakt.tv')
		if self.show_progress:
			progress.update(15, line1=getString(1434), line2=' ', line3=' ')

		self.trakt_shows['collection'] = self.traktapi.getShowLibrary()

	def AddToTrakt(self):
		Debug("[Episodes Sync] Checking for episodes missing from trakt.tv collection.")
		if self.show_progress:
			progress.update(30, line1=getString(1435), line2=' ', line3=' ')

		add_to_trakt = []
		trakt_imdb_index = {}
		trakt_tvdb_index = {}
		trakt_title_index = {}

		for i in range(len(self.trakt_shows['collection'])):
			if 'imdb_id' in self.trakt_shows['collection'][i]:
				trakt_imdb_index[self.trakt_shows['collection'][i]['imdb_id']] = i

			if 'tvdb_id' in self.trakt_shows['collection'][i]:
				trakt_tvdb_index[self.trakt_shows['collection'][i]['tvdb_id']] = i

			trakt_title_index[self.trakt_shows['collection'][i]['title']] = i

		for xbmc_show in self.xbmc_shows:
			missing = []

			#IMDB ID
			if xbmc_show['imdbnumber'].startswith('tt'):
				if xbmc_show['imdbnumber'] not in trakt_imdb_index.keys():
					missing = xbmc_show['episodes']

				else:
					trakt_show = self.trakt_shows['collection'][trakt_imdb_index[xbmc_show['imdbnumber']]]
					missing = compare_show(xbmc_show, trakt_show)

			#TVDB ID
			elif xbmc_show['imdbnumber'].isdigit():
				if xbmc_show['imdbnumber'] not in trakt_tvdb_index.keys():
					missing = xbmc_show['episodes']

				else:
					trakt_show = self.trakt_shows['collection'][trakt_tvdb_index[xbmc_show['imdbnumber']]]
					missing = compare_show(xbmc_show, trakt_show)

			#Title
			else:
				if xbmc_show['title'] not in trakt_title_index.keys():
					missing = xbmc_show['episodes']

				else:
					trakt_show = self.trakt_shows['collection'][trakt_title_index[xbmc_show['title']]]
					missing = compare_show(xbmc_show, trakt_show)

			if missing:
				show = {'title': xbmc_show['title'], 'episodes': [{'episode': x['episode'], 'season': x['season'], 'episode_tvdb_id': x['uniqueid']['unknown']} for x in missing]}
				Debug("[Episodes Sync][AddToTrakt] %s" % show)

				if xbmc_show['imdbnumber'].isdigit():
					show['tvdb_id'] = xbmc_show['imdbnumber']
				else:
					show['imdb_id'] = xbmc_show['imdbnumber']

				add_to_trakt.append(show)

		if add_to_trakt:
			Debug("[Episodes Sync] %i shows(s) have episodes added to trakt.tv collection." % len(add_to_trakt))
			if self.show_progress:
				progress.update(35, line1=getString(1435), line2='%i %s' % (len(add_to_trakt), getString(1436)))

			for show in add_to_trakt:
				if self.Canceled():
					return
				if self.show_progress:
					progress.update(45, line1=getString(1435), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), getString(1437)))

				self.traktapi.addEpisode(show)

		else:
			Debug("[Episodes Sync] trakt.tv episode collection is up to date.")

	def GetWatchedFromTrakt(self):
		Debug('[Episodes Sync] Getting watched episodes from trakt.tv')
		if self.show_progress:
			progress.update(50, line1=getString(1438), line2=' ', line3=' ')

		self.trakt_shows['watched'] = self.traktapi.getWatchedEpisodeLibrary()

	def UpdatePlaysTrakt(self):
		Debug("[Episodes Sync] Checking watched episodes on trakt.tv")
		if self.show_progress:
			progress.update(60, line1=getString(1438), line2=' ', line3=' ')

		update_playcount = []
		trakt_imdb_index = {}
		trakt_tvdb_index = {}
		trakt_title_index = {}

		for i in range(len(self.trakt_shows['watched'])):
			if 'imdb_id' in self.trakt_shows['watched'][i]:
				trakt_imdb_index[self.trakt_shows['watched'][i]['imdb_id']] = i

			if 'tvdb_id' in self.trakt_shows['watched'][i]:
				trakt_tvdb_index[self.trakt_shows['watched'][i]['tvdb_id']] = i

			trakt_title_index[self.trakt_shows['watched'][i]['title']] = i

		xbmc_shows_watched = []
		for show in self.xbmc_shows:
			watched_episodes = [x for x in show['episodes'] if x['playcount']]
			if watched_episodes:
				xbmc_shows_watched.append(show)

		for xbmc_show in xbmc_shows_watched:
			missing = []
			trakt_show = {}

			#IMDB ID
			if xbmc_show['imdbnumber'].startswith('tt') and xbmc_show['imdbnumber'] in trakt_imdb_index.keys():
				trakt_show = self.trakt_shows['watched'][trakt_imdb_index[xbmc_show['imdbnumber']]]

			#TVDB ID
			elif xbmc_show['imdbnumber'].isdigit() and xbmc_show['imdbnumber'] in trakt_tvdb_index.keys():
				trakt_show = self.trakt_shows['watched'][trakt_tvdb_index[xbmc_show['imdbnumber']]]

			#Title
			else:
				if xbmc_show['title'] in trakt_title_index.keys():
					trakt_show = self.trakt_shows['watched'][trakt_title_index[xbmc_show['title']]]

			if trakt_show:
				missing = compare_show_watched_trakt(xbmc_show, trakt_show)
			else:
				missing = [x for x in xbmc_show['episodes'] if x['playcount']]

			if missing:
				show = {'title': xbmc_show['title'], 'episodes': [{'episode': x['episode'], 'season': x['season'], 'episode_tvdb_id': x['uniqueid']['unknown']} for x in missing]}
				Debug("[Episodes Sync][UpdatePlaysTrakt] %s" % show)

				if xbmc_show['imdbnumber'].isdigit():
					show['tvdb_id'] = xbmc_show['imdbnumber']
				else:
					show['imdb_id'] = xbmc_show['imdbnumber']

				update_playcount.append(show)

		if update_playcount:
			Debug("[Episodes Sync] %i shows(s) shows are missing playcounts on trakt.tv" % len(update_playcount))
			if self.show_progress:
				progress.update(65, line1=getString(1438), line2='%i %s' % (len(update_playcount), getString(1439)))

			for show in update_playcount:
				if self.Canceled():
					return
				if self.show_progress:
					progress.update(70, line1=getString(1438), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), getString(1440)))

				self.traktapi.updateSeenEpisode(show)

		else:
			Debug("[Episodes Sync] trakt.tv episode playcounts are up to date.")

	def UpdatePlaysXBMC(self):
		Debug("[Episodes Sync] Checking watched episodes on XBMC")
		if self.show_progress:
			progress.update(80, line1=getString(1441), line2=' ', line3=' ')

		update_playcount = []
		trakt_imdb_index = {}
		trakt_tvdb_index = {}
		trakt_title_index = {}

		for i in range(len(self.trakt_shows['watched'])):
			if 'imdb_id' in self.trakt_shows['watched'][i]:
				trakt_imdb_index[self.trakt_shows['watched'][i]['imdb_id']] = i

			if 'tvdb_id' in self.trakt_shows['watched'][i]:
				trakt_tvdb_index[self.trakt_shows['watched'][i]['tvdb_id']] = i

			trakt_title_index[self.trakt_shows['watched'][i]['title']] = i

		for xbmc_show in self.xbmc_shows:
			missing = []
			trakt_show = None

			#IMDB ID
			if xbmc_show['imdbnumber'].startswith('tt') and xbmc_show['imdbnumber'] in trakt_imdb_index.keys():
				trakt_show = self.trakt_shows['watched'][trakt_imdb_index[xbmc_show['imdbnumber']]]

			#TVDB ID
			elif xbmc_show['imdbnumber'].isdigit() and xbmc_show['imdbnumber'] in trakt_tvdb_index.keys():
				trakt_show = self.trakt_shows['watched'][trakt_tvdb_index[xbmc_show['imdbnumber']]]

			#Title
			else:
				if xbmc_show['title'] in trakt_title_index.keys():
					trakt_show = self.trakt_shows['watched'][trakt_title_index[xbmc_show['title']]]

			if trakt_show:
				missing = compare_show_watched_xbmc(xbmc_show, trakt_show)
			else:
				Debug("[Episodes Sync] '%s' has not been watched or scrobbled on trakt.tv yet, skipping." % xbmc_show['title'])


			if missing:
				show = {'title': xbmc_show['title'], 'episodes': [{'episodeid': x['episodeid'], 'playcount': 1} for x in missing]}
				update_playcount.append(show)

		if update_playcount:
			Debug("[Episodes Sync] %i shows(s) shows are missing playcounts on XBMC" % len(update_playcount))
			if self.show_progress:
				progress.update(85, line1=getString(1441), line2='%i %s' % (len(update_playcount), getString(1439)))

			for show in update_playcount:
				if self.show_progress:
					progress.update(85, line1=getString(1441), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), getString(1440)))

				#split episode list into chunks of 50
				chunked_episodes = chunks([{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": show['episodes'][i], "id": i} for i in range(len(show['episodes']))], 50)
				for chunk in chunked_episodes:
					if self.Canceled():
						return
					xbmcJsonRequest(chunk)

		else:
			Debug("[Episodes Sync] XBMC episode playcounts are up to date.")

	def RemoveFromTrakt(self):
		Debug("[Movies Sync] Cleaning trakt tvshow collection.")
		if self.show_progress:
			progress.update(90, line1=getString(1445), line2=' ', line3=' ')

		def convert_seasons(show):
			episodes = []
			if 'seasons' in show and show['seasons']:
				for season in show['seasons']:
					for episode in season['episodes']:
						episodes.append({'season': season['season'], 'episode': episode})
			return episodes

		remove_from_trakt = []
		indices = {'imdb_id': {}, 'tvdb_id': {}, 'title': {}}

		for i in range(len(self.xbmc_shows)):
			if self.xbmc_shows[i]['imdbnumber'].startswith('tt'):
				indices['imdb_id'][self.xbmc_shows[i]['imdbnumber']] = i

			if self.xbmc_shows[i]['imdbnumber'].isdigit():
				indices['tvdb_id'][self.xbmc_shows[i]['imdbnumber']] = i

			indices['title'][self.xbmc_shows[i]['title']] = i

		for trakt_show in self.trakt_shows['collection']:
			matched = False
			remove = []

			if 'tvdb_id' in trakt_show:
				if trakt_show['tvdb_id'] in indices['tvdb_id']:
					matched = 'tvdb_id'

			if not matched and 'imdb_id' in trakt_show:
				if trakt_show['imdb_id'] in indices['imdb_id']:
					matched = 'imdb_id'

			if not matched:
				if trakt_show['title'] in indices['title']:
					matched = 'title'

			if matched:
				xbmc_show = self.xbmc_shows[indices[matched][trakt_show[matched]]]
				trakt_episodes = convert_seasons(trakt_show)
				xbmc_episodes = [{'season': x['season'], 'episode': x['episode']} for x in xbmc_show['episodes']]

				for episode in trakt_episodes:
					if episode not in xbmc_episodes:
						remove.append(episode)

			else:
				remove = convert_seasons(trakt_show)

			if remove:
				show = {'title': trakt_show['title'], 'year': trakt_show['year'], 'episodes': remove}
				if matched:
					show[matched] = trakt_show[matched]
				else:
					show['tvdb_id'] = trakt_show['tvdb_id']
				remove_from_trakt.append(show)

		if remove_from_trakt:
			Debug("[Episodes Sync] %i show(s) will have episodes removed from trakt.tv collection." % len(remove_from_trakt))
			if self.show_progress:
				progress.update(90, line1=getString(1445), line2='%i %s' % (len(remove_from_trakt), getString(1446)))

			for show in remove_from_trakt:
				if self.Canceled():
					return

				if self.show_progress:
					progress.update(95, line1=getString(1445), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), getString(1447)))

				self.traktapi.removeEpisode(show)

		else:
			Debug('[Episodes Sync] trakt.tv episode collection is clean')

	def Run(self):
		if not self.show_progress and getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (getString(1400), getString(1406)), getString(1420)) #Sync started

		self.GetFromXBMC()

		# sanity check, test for non-empty xbmc movie list
		if self.xbmc_shows:

			if not self.Canceled() and add_episodes_to_trakt:
				self.GetCollectionFromTrakt()
				if not self.Canceled():
					self.AddToTrakt()

			if trakt_episode_playcount or xbmc_episode_playcount:
				if not self.Canceled():
					self.GetWatchedFromTrakt()

			if not self.Canceled() and trakt_episode_playcount:
				self.UpdatePlaysTrakt()

			if xbmc_episode_playcount:
				if not self.Canceled():
					self.UpdatePlaysXBMC()

			if clean_trakt_episodes:
				if not self.Canceled() and not add_episodes_to_trakt:
					self.GetCollectionFromTrakt()
				if not self.Canceled():
					self.RemoveFromTrakt()

		else:
			Debug("[Episodes Sync] XBMC Show list is empty, aborting Episodes Sync.")

		if not self.show_progress and getSettingAsBool('sync_on_update') and self.notify:
			notification('%s %s' % (getString(1400), getString(1406)), getString(1421)) #Sync complete

		if not self.Canceled() and self.show_progress:
			progress.update(100, line1=getString(1442), line2=' ', line3=' ')
			progress.close()

		Debug("[Episodes Sync] Complete.")