# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcaddon
from utilities import traktJsonRequest, xbmcJsonRequest, Debug, notification


__setting__   = xbmcaddon.Addon('script.trakt').getSetting
__getstring__ = xbmcaddon.Addon('script.trakt').getLocalizedString

add_episodes_to_trakt   = __setting__('add_episodes_to_trakt') == 'true'
trakt_episode_playcount = __setting__('trakt_episode_playcount') == 'true'
xbmc_episode_playcount  = __setting__('xbmc_episode_playcount') == 'true'

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
	def __init__(self, show_progress=False):
		self.xbmc_shows = []
		self.trakt_shows = {'collection': [], 'watched': []}
		self.notify = __setting__('show_sync_notifications') == 'true'
		self.show_progress = show_progress

		if self.show_progress:
			progress.create('%s %s' % (__getstring__(1400), __getstring__(1406)), line1=' ', line2=' ', line3=' ')

	def GetFromXBMC(self):
		Debug('[Episodes Sync] Getting episodes from XBMC')
		if self.show_progress:
			progress.update(5, line1=__getstring__(1432), line2=' ', line3=' ')

		shows = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber']}, 'id': 0})['tvshows']

		if self.show_progress:
			progress.update(10, line1=__getstring__(1433), line2=' ', line3=' ')

		for show in shows:
			show['episodes'] = []

			episodes = xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': show['tvshowid'], 'properties': ['season', 'episode', 'playcount', 'uniqueid']}, 'id': 0})
			if 'episodes' in episodes:
				episodes = episodes['episodes']

				show['episodes'] = [x for x in episodes if type(x) == type(dict())]

		self.xbmc_shows = [x for x in shows if x['episodes']]

	def GetCollectionFromTrakt(self):
		Debug('[Episodes Sync] Getting episode collection from trakt.tv')
		if self.show_progress:
			progress.update(15, line1=__getstring__(1434), line2=' ', line3=' ')

		self.trakt_shows['collection'] = traktJsonRequest('POST', '/user/library/shows/collection.json/%%API_KEY%%/%%USERNAME%%/min')

	def AddToTrakt(self):
		Debug('[Episodes Sync] Checking for episodes missing from trakt.tv collection')
		if self.show_progress:
			progress.update(30, line1=__getstring__(1435), line2=' ', line3=' ')

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
					
				if xbmc_show['imdbnumber'].isdigit():
					show['tvdb_id'] = xbmc_show['imdbnumber']
				else:
					show['imdb_id'] = xbmc_show['imdbnumber']

				add_to_trakt.append(show)

		if add_to_trakt:
			Debug('[Episodes Sync] %i shows(s) have episodes added to trakt.tv collection' % len(add_to_trakt))
			if self.show_progress:
				progress.update(35, line1=__getstring__(1435), line2='%i %s' % (len(add_to_trakt), __getstring__(1436)))

			for show in add_to_trakt:
				if self.show_progress:
					progress.update(45, line1=__getstring__(1435), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), __getstring__(1437)))

				traktJsonRequest('POST', '/show/episode/library/%%API_KEY%%', show)

		else:
			Debug('[Episodes Sync] trakt.tv episode collection is up to date')

	def GetWatchedFromTrakt(self):
		Debug('[Episodes Sync] Getting watched episodes from trakt.tv')
		if self.show_progress:
			progress.update(60, line1=__getstring__(1438), line2=' ', line3=' ')

		self.trakt_shows['watched'] = traktJsonRequest('POST', '/user/library/shows/watched.json/%%API_KEY%%/%%USERNAME%%/min')

	def UpdatePlaysTrakt(self):
		Debug('[Episodes Sync] Cecking watched episodes on trakt.tv')
		if self.show_progress:
			progress.update(70, line1=__getstring__(1438), line2=' ', line3=' ')

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
				Debug('[Episodes Sync] Failed to find %s on trakt.tv' % xbmc_show['title'])


			if missing:
				show = {'title': xbmc_show['title'], 'episodes': [{'episode': x['episode'], 'season': x['season'], 'episode_tvdb_id': x['uniqueid']['unknown']} for x in missing]}
					
				if xbmc_show['imdbnumber'].isdigit():
					show['tvdb_id'] = xbmc_show['imdbnumber']
				else:
					show['imdb_id'] = xbmc_show['imdbnumber']

				update_playcount.append(show)

		if update_playcount:
			Debug('[Episodes Sync] %i shows(s) shows are missing playcounts on trakt.tv' % len(update_playcount))
			if self.show_progress:
				progress.update(75, line1=__getstring__(1438), line2='%i %s' % (len(update_playcount), __getstring__(1439)))

			for show in update_playcount:
				if self.show_progress:
					progress.update(80, line1=__getstring__(1438), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), __getstring__(1440)))

				traktJsonRequest('POST', '/show/episode/seen/%%API_KEY%%', show)

		else:
			Debug('[Episodes Sync] trakt.tv episode playcounts are up to date')

	def UpdatePlaysXBMC(self):
		Debug('[Episodes Sync] Checking watched episodes on XBMC')
		if self.show_progress:
			progress.update(90, line1=__getstring__(1441), line2=' ', line3=' ')

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
				Debug('[Episodes Sync] Failed to find %s on trakt.tv' % xbmc_show['title'])


			if missing:
				show = {'title': xbmc_show['title'], 'episodes': [{'episodeid': x['episodeid'], 'playcount': 1} for x in missing]}
				update_playcount.append(show)

		if update_playcount:
			Debug('[Episodes Sync] %i shows(s) shows are missing playcounts on XBMC' % len(update_playcount))
			if self.show_progress:
				progress.update(92, line1=__getstring__(1441), line2='%i %s' % (len(update_playcount), __getstring__(1439)))

			for show in update_playcount:
				if self.show_progress:
					progress.update(95, line1=__getstring__(1441), line2=show['title'].encode('utf-8', 'ignore'), line3='%i %s' % (len(show['episodes']), __getstring__(1440)))

				for episode in show['episodes']:
					xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.SetEpisodeDetails', 'params': episode, 'id': 0})

		else:
			Debug('[Episodes Sync] XBMC episode playcounts are up to date')

	def Run(self):
		if not self.show_progress: #Service VideoLibrary.OnScanFinished
			if __setting__('sync_on_update') == 'true':
				if self.notify:
					notification('%s %s' % (__getstring__(1400), __getstring__(1406)), __getstring__(1420)) #Sync started

				self.GetFromXBMC()

				if add_episodes_to_trakt:
					self.GetCollectionFromTrakt()
					self.AddToTrakt()

				if trakt_episode_playcount or xbmc_episode_playcount:
					self.GetWatchedFromTrakt()

				if trakt_episode_playcount:
					self.UpdatePlaysTrakt()

				if xbmc_episode_playcount:
					self.UpdatePlaysXBMC()

				if self.notify:
					notification('%s %s' % (__getstring__(1400), __getstring__(1406)), __getstring__(1421)) #Sync complete

		else: #Manual
			self.GetFromXBMC()

			if not progress.iscanceled() and add_episodes_to_trakt:
				self.GetCollectionFromTrakt()
				self.AddToTrakt()

			if trakt_episode_playcount or xbmc_episode_playcount:
				if not progress.iscanceled():
					self.GetWatchedFromTrakt()

			if not progress.iscanceled() and trakt_episode_playcount:
				self.UpdatePlaysTrakt()

			if not progress.iscanceled() and xbmc_episode_playcount:
				self.UpdatePlaysXBMC()

			if not progress.iscanceled():
				progress.update(100, line1=__getstring__(1442), line2=' ', line3=' ')
				xbmc.sleep(1000)
				progress.close()

		Debug('[Episodes Sync] Complete')