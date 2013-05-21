# -*- coding: utf-8 -*-

import xbmc
import xbmcaddon
import xbmcgui
import utilities as utils
import copy
from time import time
from traktapi import traktAPI

__addon__ = xbmcaddon.Addon("script.trakt")

TAG_PREFIX = "trakt.tv - "
PRIVACY_LIST = ['public', 'friends', 'private']

def isTaggingEnabled():
	return utils.getSettingAsBool('tagging_enable')
def isWatchlistsEnabled():
	return utils.getSettingAsBool('tagging_watchlists')
def isRatingsEnabled():
	return utils.getSettingAsBool('tagging_ratings')
def getMinRating():
	return utils.getSettingAsInt('tagging_ratings_min')

def tagToList(tag):
	return tag.replace(TAG_PREFIX, "", 1)
def listToTag(list):
	return "%s%s" % (TAG_PREFIX, list)
def ratingToTag(rating):
	return "%sRating: %s" % (TAG_PREFIX, rating)
def isTraktList(tag):
	return True if tag.startswith(TAG_PREFIX) else False

def hasTraktWatchlistTag(tags):
	watchlist_tag = False
	for tag in tags:
		if isTraktList(tag):
			_tag = tagToList(tag)
			if _tag.lower() == "watchlist":
				watchlist_tag = True
				break
	return watchlist_tag
def getTraktRatingTag(tags):
	for tag in tags:
		if isTraktList(tag):
			_tag = tagToList(tag)
			if _tag.lower().startswith("rating:"):
				return tag
	return None
def hasTraktRatingTag(tags):
	return not getTraktRatingTag(tags) is None
def isTraktRatingTag(tag):
	if isTraktList(tag):
		_tag = tagToList(tag)
		return _tag.lower().startswith("rating:")
	return False

def xbmcSetTags(id, type, title, tags):
	if not (utils.isMovie(type) or utils.isShow(type)):
		return

	req = None
	if utils.isMovie(type):
		req = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid" : id, "tag": tags}}
	elif utils.isShow(type):
		req = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails", "params": {"tvshowid" : id, "tag": tags}}

	if utils.getSettingAsBool('simulate_tagging'):
		utils.Debug("[Tagger] %s" % str(req))
		return True
	else:
		result = utils.xbmcJsonRequest(req)
		if result == "OK":
			utils.Debug("[Tagger] XBMC tags for '%s' were updated with '%s'." % (title, str(tags)))
			return True

	return False

class Tagger():

	traktSlugs = None
	traktSlugsLast = 0

	def __init__(self, api=None):
		if api is None:
			api = traktAPI(loadSettings=False)
		self.traktapi = api
		self.updateSettings()

	def updateSettings(self):
		self._enabled = utils.getSettingAsBool('tagging_enable')
		self._watchlists = utils.getSettingAsBool('tagging_watchlists')
		self._ratings = utils.getSettingAsBool('tagging_ratings')
		self._ratingMin = utils.getSettingAsInt('tagging_ratings_min')
		self.simulate = utils.getSettingAsBool('simulate_tagging')
		if self.simulate:
			utils.Debug("[Tagger] Tagging is configured to be simulated.")

	def xbmcLoadData(self, tags=False):
		data = {'movies': [], 'tvshows': []}

		props = ['title', 'imdbnumber', 'year']
		if tags:
			props.append('tag')
		m = {'method': 'VideoLibrary.GetMovies', 'props': props}
		s = {'method': 'VideoLibrary.GetTVShows', 'props': props}
		params = {'movies': m, 'tvshows': s}

		for type in params:
			utils.Debug("[Tagger] Getting '%s' from XBMC." % type)
			xbmc_data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': params[type]['method'], 'params': {'properties': params[type]['props']}})
			if not xbmc_data:
				utils.Debug("[Tagger] XBMC JSON request was empty.")
				return False

			if not type in xbmc_data:
				utils.Debug("[Tagger] Key '%s' not found." % type)
				return False

			data[type] = xbmc_data[type]
			utils.Debug("[Tagger] XBMC JSON Result: '%s'" % str(data[type]))

			db_field = 'tmdb_id' if type == 'movies' else 'tvdb_id'

			for item in data[type]:
				item['type'] = 'movie' if type == 'movies' else 'show'
				id = item['imdbnumber']
				item['imdb_id'] = id if id.startswith("tt") else ""
				item[db_field] = unicode(id) if id.isdigit() else ""
				del(item['imdbnumber'])
				del(item['label'])

		data['shows'] = data.pop('tvshows')
		self.xbmcData = data
		return True

	def xbmcBuildTagList(self):
		data = {}

		for type in ['movies', 'shows']:
			for index in range(len(self.xbmcData[type])):
				item = self.xbmcData[type][index]
				for tag in item['tag']:
					if isTraktList(tag):
						listName = tagToList(tag)
						if not listName in data:
							data[listName] = {'movies': [], 'shows': []}
						data[listName][type].append(index)

		return data

	def getTraktLists(self, force=False):
		if force or self.traktSlugs is None or (time() - self.traktSlugsLast) > (60 * 10):
			utils.Debug("[Tagger] Getting lists from trakt.tv")
			data = self.traktapi.getUserLists()

			if not isinstance(data, list):
				utils.Debug("[Tagger] Invalid trakt.tv lists, possible error getting data from trakt, aborting trakt.tv collection update.")
				return False

			lists = {}
			for item in data:
				lists[item['name']] = item['slug']

			self.traktSlugs = lists
			self.traktSlugsLast = time()
		else:
			utils.Debug("[Tagger] Using cached lists.")

		return self.traktSlugs

	def getTraktListData(self):
		data = {}

		utils.Debug("[Tagger] Getting list data from trakt.tv")
		lists = self.getTraktLists(force=True)
		if not lists:
			utils.Debug("[Tagger] No lists at trakt.tv, nothing to retrieve.")
			return {}

		for listName in lists:
			slug = lists[listName]
			data[listName] = {'movies': [], 'shows': []}

			utils.Debug("[Tagger] Getting list data for list slug '%s'." % slug)
			listdata = self.traktapi.getUserList(slug)

			if not isinstance(listdata, dict):
				utils.Debug("[Tagger] Invalid trakt.tv list data, possible error getting data from trakt.")
				return None

			for item in listdata['items']:
				type = 'movies' if item['type'] == 'movie' else 'shows'
				f = utils.findMovie if type == 'movies' else utils.findShow

				i = f(item[item['type']], self.xbmcData[type], returnIndex=True)
				if not i is None:
					data[listName][type].append(i)

		return data

	def getTraktWatchlistData(self):
		data = {}

		utils.Debug("[Tagger] Getting watchlist data from trakt.tv")
		w = {}
		w['movies']	= self.traktapi.getWatchlistMovies()
		w['shows'] = self.traktapi.getWatchlistShows()

		if isinstance(w['movies'], list) and isinstance(w['shows'], list):
			data['Watchlist'] = {'movies': [], 'shows': []}

			for type in w:
				f = utils.findMovie if type == 'movies' else utils.findShow
				for item in w[type]:
					i = f(item, self.xbmcData[type], returnIndex=True)
					if not i is None:
						data['Watchlist'][type].append(i)

		else:
			utils.Debug("[Tagger] There was a problem getting your watchlists.")
			return None

		return data

	def getTraktRatingData(self):
		data = {}

		utils.Debug("[Tagger] Getting rating data from trakt.tv")
		r = {}
		r['movies'] = self.traktapi.getRatedMovies()
		r['shows'] = self.traktapi.getRatedShows()

		if isinstance(r['movies'], list) and isinstance(r['shows'], list):

			for i in range(self._ratingMin, 11):
				listName = "Rating: %s" % i
				data[listName] = {'movies': [], 'shows': []}

			for type in r:
				f = utils.findMovie if type == 'movies' else utils.findShow
				for item in r[type]:
					if item['rating_advanced'] >= self._ratingMin:
						i = f(item, self.xbmcData[type], returnIndex=True)
						if not i is None:
							listName = "Rating: %s" % item['rating_advanced']
							data[listName][type].append(i)

		else:
			utils.Debug("[Tagger] There was a problem getting your rated movies or shows.")
			return None

		return data

	def sanitizeTraktParams(self, data):
		newData = copy.deepcopy(data)
		for item in newData:
			if 'imdb_id' in item and not item['imdb_id']:
				del(item['imdb_id'])
			if 'tmdb_id' in item and not item['tmdb_id']:
				del(item['tmdb_id'])
			if 'tvdb_id' in item and not item['tvdb_id']:
				del(item['tvdb_id'])
			if 'tvshowid' in item:
				del(item['tvshowid'])
			if 'movieid' in item:
				del(item['movieid'])
			if 'tag' in item:
				del(item['tag'])
		return newData

	def isListOnTrakt(self, list):
		lists = self.getTraktLists()
		return list in lists

	def getSlug(self, list):
		if self.isListOnTrakt(list):
			return self.getTraktLists[list]
		return None

	def xbmcUpdateTags(self, data):
		chunked = utils.chunks([{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid" : movie, "tag": data['movies'][movie]}} for movie in data['movies']], 50)
		chunked.extend(utils.chunks([{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails", "params": {"tvshowid" : show, "tag": data['shows'][show]}} for show in data['shows']], 50))
		for chunk in chunked:
			if self.simulate:
				utils.Debug("[Tagger] %s" % str(chunk))
			else:
				utils.xbmcJsonRequest(chunk)

	def traktListAddItem(self, list, data):
		if not list:
			utils.Debug("[Tagger] No list provided.")
			return

		if not data:
			utils.Debug("[Tagger] Nothing to add to trakt lists")
			return

		params = {}
		params['items'] = self.sanitizeTraktParams(data)

		if self.simulate:
			utils.Debug("[Tagger] '%s' adding '%s'" % (list, str(params)))
		else:
			if self.isListOnTrakt(list):
				slug = self.traktSlugs[list]
				params['slug'] = slug
			else:
				list_privacy = utils.getSettingAsInt('tagging_list_privacy')
				allow_shouts = utils.getSettingAsBool('tagging_list_allowshouts')

				utils.Debug("[Tagger] Creating new list '%s'" % list)
				result = self.traktapi.userListAdd(list, PRIVACY_LIST[list_privacy], allow_shouts=allow_shouts)

				if result and 'status' in result and result['status'] == 'success':
					slug = result['slug']
					params['slug'] = slug
					self.traktSlugs[list] = slug
				else:
					utils.Debug("[Tagger] There was a problem create the list '%s' on trakt.tv" % list)
					return

			utils.Debug("[Tagger] Adding to list '%s', items '%s'" % (list, str(params['items'])))
			self.traktapi.userListItemAdd(params)

	def traktListRemoveItem(self, list, data):
		if not list:
			utils.Debug("[Tagger] No list provided.")
			return

		if not data:
			utils.Debug("[Tagger] Nothing to remove from trakt list.")
			return

		if not self.isListOnTrakt(list):
			utils.Debug("[Tagger] Trying to remove items from non-existant list '%s'." % list)

		slug = self.traktSlugs[list]
		params = {'slug': slug}
		params['items'] = self.sanitizeTraktParams(data)

		if self.simulate:
			utils.Debug("[Tagger] '%s' removing '%s'" % (list, str(params)))
		else:
			self.traktapi.userListItemDelete(params)

	def updateWatchlist(self, data, remove=False):
		movie_params = []
		show_params = []

		for item in data:
			if utils.isMovie(item['type']):
				movie = {}
				movie['title'] = item['title']
				if 'imdb_id' in item:
					movie['imdb_id'] = item['imdb_id']
				if 'tmdb_id' in data:
					movie['tmdb_id'] = item['tmdb_id']
				movie['year'] = item['year']
				movie_params.append(movie)

			elif utils.isShow(item['type']):
				show = {}
				show['title'] = item['title']
				if 'imdb_id' in item:
					show['imdb_id'] = item['imdb_id']
				if 'tvdb_id' in item:
					show['tvdb_id'] = item['tvdb_id']
				show_params.append(show)

		if movie_params:
			params = {'movies': movie_params}
			if self.simulate:
				utils.Debug("[Tagger] Movie watchlist %s '%s'." % ("remove" if remove else "add", str(params)))

			else:
				if not remove:
					self.traktapi.watchlistAddMovies(params)
				else:
					self.traktapi.watchlistRemoveMovies(params)

		if show_params:
			params = {'shows': show_params}
			if self.simulate:
				utils.Debug("[Tagger] Show watchlist %s '%s'." % ("remove" if remove else "add", str(params)))

			else:
				if not remove:
					self.traktapi.watchlistAddShows(params)
				else:
					self.traktapi.watchlistRemoveShows(params)

	def isAborted(self):
		if xbmc.abortRequested:
			utils.Debug("[Tagger] XBMC abort requested, stopping.")
			return true

	def updateTagsFromTrakt(self):
		if not self._enabled:
			utils.Debug("[Tagger] Tagging is not enabled, aborting.")
			return

		utils.Debug("[Tagger] Starting List/Tag synchronization.")
		if utils.getSettingAsBool('tagging_notifications'):
			utils.notification(utils.getString(1201), utils.getString(1658))

		tStart = time()
		if not self.xbmcLoadData(tags=True):
			utils.Debug("[Tagger] Problem loading XBMC data, aborting.")
			utils.notification(utils.getString(1201), utils.getString(1662))
			return
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to load data from XBMC: %0.3f seconds." % tTaken)

		tStart = time()
		xbmc_lists = self.xbmcBuildTagList()
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to load build list from XBMC data: %0.3f seconds." % tTaken)

		if self.isAborted():
			return

		trakt_lists = {}

		tStart = time()
		trakt_lists = self.getTraktListData()
		if trakt_lists is None:
			utils.Debug("[Tagger] Problem getting list data, aborting.")
			utils.notification(utils.getString(1201), utils.getString(1663))
			return

		if self.isAborted():
			return

		if self._watchlists:
			watchlist = self.getTraktWatchlistData()
			if watchlist is None:
				utils.Debug("[Tagger] Problem getting watchlist data, aborting.")
				utils.notification(utils.getString(1201), utils.getString(1664))
				return
			trakt_lists['Watchlist'] = watchlist['Watchlist']

		if self.isAborted():
			return

		if self._ratings:
			ratings = self.getTraktRatingData()
			if ratings is None:
				utils.Debug("[Tagger] Can not continue with managing lists, aborting.")
				utils.notification(utils.getString(1201), utils.getString(1665))
				return
			trakt_lists = dict(trakt_lists, **ratings)

		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to load data from trakt.tv: %0.3f seconds." % tTaken)

		if self.isAborted():
			return

		tStart = time()
		c = 0
		tags = {'movies': {}, 'shows': {}}
		for listName in trakt_lists:
			for type in ['movies', 'shows']:
				for index in trakt_lists[listName][type]:
					if not index in tags[type]:
						tags[type][index] = []
						c = c + 1
					tags[type][index].append(listToTag(listName))
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to build xbmc tag list for (%d) items: %0.3f seconds." % (c, tTaken))

		tStart = time()
		xbmc_update = {'movies': [], 'shows': []}
		for listName in trakt_lists:
			if listName in xbmc_lists:
				for type in ['movies', 'shows']:
					s1 = set(trakt_lists[listName][type])
					s2 = set(xbmc_lists[listName][type])
					if not s1 == s2:
						xbmc_update[type].extend(list(s1.difference(s2)))
						xbmc_update[type].extend(list(s2.difference(s1)))
			else:
				xbmc_update['movies'].extend(trakt_lists[listName]['movies'])
				xbmc_update['shows'].extend(trakt_lists[listName]['shows'])

		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to compare data: %0.3f seconds." % tTaken)

		sStart = time()
		old_tags = {'movies': {}, 'shows': {}}
		c = 0
		for type in ['movies', 'shows']:
			for item in self.xbmcData[type]:
				t = []
				for old_tag in item['tag']:
					if not isTraktList(old_tag):
						t.append(old_tag)
				id_field = 'movieid' if type == 'movies' else 'tvshowid'
				id = item[id_field]
				if t:
					old_tags[type][id] = t
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to build list of old tags for (%d) items: %0.3f seconds." % (c, tTaken))
		
		sStart = time()
		xbmcTags = {'movies': {}, 'shows': {}}
		c = 0
		for type in xbmcTags:
			xbmc_update[type] = list(set(xbmc_update[type]))
			for index in xbmc_update[type]:
				t = []
				if index in tags[type]:
					t = tags[type][index]
				if index in old_tags[type]:
					t.extend(old_tags[type][index])
				id_field = 'movieid' if type == 'movies' else 'tvshowid'
				id = self.xbmcData[type][index][id_field]
				xbmcTags[type][id] = t
				c = c + 1

		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to build list of changes for (%d) items: %0.3f seconds." % (c, tTaken))

		# update xbmc tags from trakt lists
		utils.Debug("[Tagger] Updating XBMC tags from trakt.tv list(s).")
		tStart = time()
		self.xbmcUpdateTags(xbmcTags)
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to update changed xbmc tags: %0.3f seconds." % tTaken)

		if utils.getSettingAsBool('tagging_notifications'):
			utils.notification(utils.getString(1201), utils.getString(1659))
		utils.Debug("[Tagger] Tags have been updated.")

	def manageLists(self):
		utils.notification(utils.getString(1201), utils.getString(1661))
		utils.Debug("[Tagger] Starting to manage lists.")

		tStart = time()
		if not self.xbmcLoadData():
			utils.Debug("[Tagger] Problem loading XBMC data, aborting.")
			utils.notification(utils.getString(1201), utils.getString(1662))
			return
		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to load data from XBMC: %0.3f seconds." % tTaken)

		selected = {}

		tStart = time()
		selected = self.getTraktListData()

		if selected is None:
			utils.Debug("[Tagger] Problem getting list data, aborting.")
			utils.notification(utils.getString(1201), utils.getString(1663))
			return

		if self._watchlists:
			watchlist = self.getTraktWatchlistData()
			if watchlist is None:
				utils.Debug("[Tagger] Problem getting watchlist data, aborting.")
				utils.notification(utils.getString(1201), utils.getString(1664))
				return
			selected['Watchlist'] = watchlist['Watchlist']

		tTaken = time() - tStart
		utils.Debug("[Tagger] Time to load data from trakt.tv: %0.3f seconds." % tTaken)

		d = traktManageListsDialog(lists=self.traktSlugs, xbmc_data=self.xbmcData, selected=selected)
		d.doModal()
		_button = d.button
		_dirty = d.dirty
		_newSelected = d.selected
		del d

		if _button == BUTTON_OK:
			if _dirty:
				newSelected = _newSelected

				tags = {'movies': {}, 'shows': {}}
				ratingTags = {'movies': {}, 'shows': {}}
				tagUpdates = {'movies': [], 'shows': []}
				traktUpdates = {}

				# build all tags
				tStart = time()
				c = 0
				for listName in newSelected:
					for type in ['movies', 'shows']:
						for index in newSelected[listName][type]:
							if not index in tags[type]:
								tags[type][index] = []
							tags[type][index].append(listToTag(listName))
							c = c + 1
				tTaken = time() - tStart
				utils.Debug("[Tagger] Time to build xbmc tag list for (%d) items: %0.3f seconds." % (c, tTaken))

				# check if we rating tags are enabled
				c = 0
				if self._ratings:
					tStart = time()

					ratings = self.getTraktRatingData()
					if ratings is None:
						utils.Debug("[Tagger] Can not continue with managing lists, aborting.")
						utils.notification(utils.getString(1201), utils.getString(1665))
						return

					c = 0
					for listName in ratings:
						for type in ['movies', 'shows']:
							for index in ratings[listName][type]:
								if not index in ratingTags[type]:
									ratingTags[type][index] = []
								ratingTags[type][index].append(listToTag(listName))
								c = c + 1

					tTaken = time() - tStart
					utils.Debug("[Tagger] Time to get and build rating tag list for (%d) items: %0.3f seconds." % (c, tTaken))

				# build lists of changes
				tStart = time()
				for listName in newSelected:
					if listName in selected:
						for type in ['movies', 'shows']:
							s1 = set(newSelected[listName][type])
							s2 = set(selected[listName][type])
							if not s1 == s2:
								toAdd = list(s1.difference(s2))
								toRemove = list(s2.difference(s1))
								tagUpdates[type].extend(toAdd)
								tagUpdates[type].extend(toRemove)
								if not listName in traktUpdates:
									traktUpdates[listName] = {'movies': {'add': [], 'remove': []}, 'shows': {'add': [], 'remove': []}}
								traktUpdates[listName][type] = {'add': toAdd, 'remove': toRemove}
					else:
						tagUpdates['movies'].extend(newSelected[listName]['movies'])
						tagUpdates['shows'].extend(newSelected[listName]['shows'])
						traktUpdates[listName] = {}
						traktUpdates[listName]['movies'] = {'add': newSelected[listName]['movies'], 'remove': []}
						traktUpdates[listName]['shows'] = {'add': newSelected[listName]['shows'], 'remove': []}

				# build xmbc update list
				xbmcTags = {'movies': {}, 'shows': {}}
				c = 0
				for type in xbmcTags:
					tagUpdates[type] = list(set(tagUpdates[type]))
					f = utils.getMovieDetailsFromXbmc if type == 'movies' else utils.getShowDetailsFromXBMC
					for index in tagUpdates[type]:
						t = []
						if index in tags[type]:
							t = tags[type][index]
						if index in ratingTags[type]:
							t.extend(ratingTags[type][index])
						id_field = 'movieid' if type == 'movies' else 'tvshowid'
						id = self.xbmcData[type][index][id_field]

						result = f(id, ['tag'])
						for old_tag in result['tag']:
							if not isTraktList(old_tag):
								t.append(old_tag)

						xbmcTags[type][id] = t
						c = c + 1

				tTaken = time() - tStart
				utils.Debug("[Tagger] Time to build list of changes for (%d) items: %0.3f seconds." % (c, tTaken))

				# update tags in xbmc
				tStart = time()
				self.xbmcUpdateTags(xbmcTags)
				tTaken = time() - tStart
				utils.Debug("[Tagger] Time to update changed xbmc tags: %0.3f seconds." % tTaken)

				# update trakt.tv
				tStart = time()
				for listName in traktUpdates:
					data = {'add': [], 'remove': []}
					for type in ['movies', 'shows']:
						data['add'].extend([self.xbmcData[type][index] for index in traktUpdates[listName][type]['add']])
						data['remove'].extend([self.xbmcData[type][index] for index in traktUpdates[listName][type]['remove']])

					if data['add']:
						if listName.lower() == 'watchlist':
							self.updateWatchlist(data['add'])
						else:
							self.traktListAddItem(listName, data['add'])
					if data['remove']:
						if listName.lower() == 'watchlist':
							self.updateWatchlist(data['remove'], remove=True)
						else:
							self.traktListRemoveItem(listName, data['remove'])

				tTaken = time() - tStart
				utils.Debug("[Tagger] Time to update trakt.tv with changes: %0.3f seconds." % tTaken)
				utils.Debug("[Tagger] Finished managing lists.")
				utils.notification(utils.getString(1201), utils.getString(1666))

	def itemLists(self, data):

		lists = self.getTraktLists()

		if not isinstance(lists, dict):
			utils.Debug("[Tagger] Error getting lists from trakt.tv.")
			return

		d = traktItemListsDialog(lists=lists, data=data)
		d.doModal()
		if not d.selectedLists is None:
			non_trakt_tags = [tag for tag in data['tag'] if not isTraktList(tag)]
			old_trakt_tags = [tagToList(tag) for tag in data['tag'] if isTraktList(tag)]
			new_trakt_tags = d.selectedLists

			if set(old_trakt_tags) == set(new_trakt_tags):
				utils.Debug("[Tagger] '%s' had no changes made to the lists it belongs to." % data['title'])

			else:
				s1 = set(old_trakt_tags)
				s2 = set(new_trakt_tags)

				_changes = {}
				_changes['add'] = list(s2.difference(s1))
				_changes['remove'] = list(s1.difference(s2))
				
				for _op in _changes:
					debug_str = "[Tagger] Adding '%s' to '%s'." if _op == 'add' else "[Tagger] Removing: '%s' from '%s'."
					f = self.traktListAddItem if _op == 'add' else self.traktListRemoveItem
					for _list in _changes[_op]:
						if _list.lower() == "watchlist":
							utils.Debug(debug_str % (data['title'], _list))
							remove = _op == 'remove'
							self.updateWatchlist([data], remove=remove)
						elif _list.lower().startswith("rating:"):
							pass
						else:
							utils.Debug(debug_str % (data['title'], _list))
							f(_list, [data])

				tags = non_trakt_tags
				tags.extend([listToTag(l) for l in new_trakt_tags])

				s = utils.getFormattedItemName(data['type'], data)
				id_field = "movieid" if data['type'] == 'movie' else "tvshowid"
				if xbmcSetTags(data[id_field], data['type'], s, tags):
					utils.notification(utils.getString(1201), utils.getString(1657) % s)

		else:
			utils.Debug("[Tagger] Dialog was cancelled.")

		del d

	def manualAddToList(self, list, data):
		if list.lower().startswith("rating:"):
			utils.Debug("[Tagger] '%s' is a reserved list name." % list)
			return

		tag = listToTag(list)
		if tag in data['tag']:
			utils.Debug("[Tagger] '%s' is already in the list '%s'." % (data['title'], list))
			return

		if list.lower() == "watchlist":
			utils.Debug("[Tagger] Adding '%s' to Watchlist." % data['title'])
			self.updateWatchlist([data])
		else:
			utils.Debug("[Tagger] Adding '%s' to '%s'." % (data['title'], list))
			self.traktListAddItem(list, [data])

		data['tag'].append(tag)

		s = utils.getFormattedItemName(data['type'], data)
		id_field = "movieid" if data['type'] == 'movie' else "tvshowid"
		if xbmcSetTags(data[id_field], data['type'], s, data['tag']):
			utils.notification(utils.getString(1201), utils.getString(1657) % s)

	def manualRemoveFromList(self, list, data):
		if list.lower().startswith("rating:"):
			utils.Debug("[Tagger] '%s' is a reserved list name." % list)
			return

		tag = listToTag(list)
		if not tag in data['tag']:
			utils.Debug("[Tagger] '%s' is not in the list '%s'." % (data['title'], list))
			return

		if list.lower() == "watchlist":
			utils.Debug("[Tagger] Removing: '%s' from Watchlist." % data['title'])
			self.updateWatchlist([data], remove=True)
		else:
			utils.Debug("[Tagger] Removing: '%s' from '%s'." % (data['title'], list))
			self.traktListRemoveItem(list, [data])

		data['tag'].remove(tag)

		s = utils.getFormattedItemName(data['type'], data)
		id_field = "movieid" if data['type'] == 'movie' else "tvshowid"
		if xbmcSetTags(data[id_field], data['type'], s, data['tag']):
			utils.notification(utils.getString(1201), utils.getString(1657) % s)

TRAKT_LISTS				= 4
BUTTON_ADD_LIST			= 15
BUTTON_OK				= 16
BUTTON_CANCEL			= 17
LABEL					= 25
ACTION_PREVIOUS_MENU2	= 92
ACTION_PARENT_DIR		= 9
ACTION_PREVIOUS_MENU	= 10 
ACTION_SELECT_ITEM		= 7
ACTION_MOUSE_LEFT_CLICK	= 100
ACTION_CLOSE_LIST		= [ACTION_PREVIOUS_MENU2, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]
ACTION_ITEM_SELECT		= [ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK]

class traktItemListsDialog(xbmcgui.WindowXMLDialog):

	selectedLists = None

	def __new__(cls, lists, data):
		return super(traktItemListsDialog, cls).__new__(cls, "traktListDialog.xml", __addon__.getAddonInfo('path'), lists=lists, data=data) 

	def __init__(self, *args, **kwargs):
		data = kwargs['data']
		lists = kwargs['lists']
		self.data = data
		self.lists = lists
		self.hasRating = False
		self.tags = {}
		for tag in data['tag']:
			if isTraktList(tag):
				t = tagToList(tag)
				if t.startswith("Rating:"):
					self.hasRating = True
					self.ratingTag = t
					continue
				self.tags[t] = True

		for tag in lists:
			if not tag in self.tags:
				self.tags[tag] = False

		if (not 'Watchlist' in self.tags) and utils.getSettingAsBool('tagging_watchlists'):
			self.tags['Watchlist'] = False

		super(traktItemListsDialog, self).__init__()

	def onInit(self):
		self.setInfoLabel(utils.getFormattedItemName(self.data['type'], self.data))
		self.list = self.getControl(TRAKT_LISTS)
		self.populateList()
		self.setFocus(self.list)

	def onAction(self, action):
		if not action.getId() in ACTION_ITEM_SELECT:
			if action in ACTION_CLOSE_LIST:
				self.close()
		if action in ACTION_ITEM_SELECT:
			cID = self.getFocusId() 
			if cID == TRAKT_LISTS:
				item = self.list.getSelectedItem()
				selected = not item.isSelected()
				item.select(selected)
				self.tags[item.getLabel()] = selected

	def onClick(self, control):
		if control == BUTTON_ADD_LIST:
			keyboard = xbmc.Keyboard("", utils.getString(1654))
			keyboard.doModal()
			if keyboard.isConfirmed() and keyboard.getText():
				new_list = keyboard.getText().strip()
				if new_list:
					if new_list.lower() == "watchlist" or new_list.lower().startswith("rating:"):
						utils.Debug("[Tagger] Dialog: Tried to add a reserved list name '%s'." % new_list)
						utils.notification(utils.getString(1650), utils.getString(1655) % new_list)
						return

					if new_list not in self.tags:
						utils.Debug("[Tagger] Dialog: Adding list '%s', and selecting it." % new_list)
					else:
						utils.Debug("[Tagger] Dialog: '%s' already in list, selecting it." % new_list)
						utils.notification(utils.getString(1650), utils.getString(1656) % new_list)

					self.tags[new_list] = True
					self.populateList()

		elif control == BUTTON_OK:
			data = []
			for i in range(0, self.list.size()):
				item = self.list.getListItem(i)
				if item.isSelected():
					data.append(item.getLabel())
			if self.hasRating:
				data.append(self.ratingTag)
			self.selectedLists = data
			self.close()

		elif control == BUTTON_CANCEL:
			self.close()

	def setInfoLabel(self, text):
		pl = self.getControl(LABEL)
		pl.setLabel(text)

	def populateList(self):
		self.list.reset()
		if 'Watchlist' in self.tags:
			item = xbmcgui.ListItem('Watchlist')
			item.select(self.tags['Watchlist'])
			self.list.addItem(item)

		for tag in sorted(self.tags.iterkeys()):
			if tag.lower() == "watchlist":
				continue
			item = xbmcgui.ListItem(tag)
			item.select(self.tags[tag])
			self.list.addItem(item)

class traktManageListsDialog(xbmcgui.WindowXMLDialog):

	dirty = False
	button = None

	def __new__(cls, lists, xbmc_data, selected):
		return super(traktManageListsDialog, cls).__new__(cls, "traktListDialog.xml", __addon__.getAddonInfo('path'), lists=lists, xbmc_data=xbmc_data, selected=selected)

	def __init__(self, *args, **kwargs):
		self.lists = kwargs['lists']
		self.xbmc_data = kwargs['xbmc_data']
		self.movies = self.xbmc_data['movies']
		self.movieList = {}
		for i in range(len(self.movies)):
			t = "%s (%d)" % (self.movies[i]['title'], self.movies[i]['year'])
			self.movieList[t] = i

		self.shows = self.xbmc_data['shows']
		self.showList = {}
		for i in range(len(self.shows)):
			self.showList[self.shows[i]['title']] = i

		self.selected = copy.deepcopy(kwargs['selected'])

		super(traktManageListsDialog, self).__init__()

	def onInit(self):
		self.list = self.getControl(TRAKT_LISTS)
		self.setInfoLabel(utils.getString(1660))
		self.level = 1
		self.populateLists()
		self.setFocus(self.list)

	def onAction(self, action):
		if not action.getId() in ACTION_ITEM_SELECT:
			if action in ACTION_CLOSE_LIST:
				if self.level > 1:
					self.goBackLevel()
					return
				else:
					self.close()
		if action in ACTION_ITEM_SELECT:
			cID = self.getFocusId() 
			if cID == TRAKT_LISTS:
				item = self.list.getSelectedItem()

				if item.getLabel() == "..":
					self.goBackLevel()
					return

				if self.level == 1:
					self.selectedList = item.getLabel()
					self.setInfoLabel(item.getLabel())
					self.setAddListEnabled(False)
					self.level = 2
					self.populateTypes()
					utils.Debug("[Tagger] Dialog: Selected '%s' moving to level 2." % self.selectedList)

				elif self.level == 2:
					self.mediaType = "movies" if item.getLabel() == "Movies" else "shows"
					self.setInfoLabel("%s - %s" % (self.selectedList, item.getLabel()))
					utils.Debug("[Tagger] Dialog: Selected '%s' moving to level 3." % item.getLabel())
					self.level = 3
					self.populateItems(self.mediaType)

				elif self.level == 3:
					selected = item.isSelected()
					id = int(item.getProperty('id'))
					if selected:
						self.selected[self.selectedList][self.mediaType].remove(id)
					else:
						self.selected[self.selectedList][self.mediaType].append(id)
					self.dirty = True
					item.select(not selected)
					s = "removing from" if selected else "adding to"
					utils.Debug("[Tagger] Dialog: Selected '%s' [%s] %s '%s'." % (item.getLabel(), item.getProperty('id'), s, self.selectedList))

	def goBackLevel(self):
		if self.level == 1:
			pass
		elif self.level == 2:
			self.setAddListEnabled(True)
			self.setInfoLabel(utils.getString(1660))
			self.level = 1
			self.populateLists()
			utils.Debug("[Tagger] Dialog: Going back a level, to level 1.")
		elif self.level == 3:
			self.setInfoLabel(self.selectedList)
			self.level = 2
			self.populateTypes()
			utils.Debug("[Tagger] Dialog: Going back a level, to level 2.")

	def onClick(self, control):
		self.button = control
		if control == BUTTON_ADD_LIST:
			keyboard = xbmc.Keyboard("", utils.getString(1654))
			keyboard.doModal()
			if keyboard.isConfirmed() and keyboard.getText():
				list = keyboard.getText().strip()
				if list:
					if list.lower() == "watchlist" or list.lower().startswith("rating:"):
						utils.Debug("[Tagger] Dialog: Tried to add a reserved list name '%s'." % list)
						utils.notification(utils.getString(1650), utils.getString(1655) % list)
						return
					if list not in self.lists:
						utils.Debug("[Tagger] Dialog: Adding list '%s'." % list)
						self.lists[list] = ""
						self.selected[list] = {'movies': [], 'shows': []}
						self.populateLists()
					else:
						utils.Debug("[Tagger] Dialog: '%s' already in list." % list)
						utils.notification(utils.getString(1650), utils.getString(1656) % list)

		elif control in [BUTTON_OK, BUTTON_CANCEL]:
			self.close()

	def setAddListEnabled(self, enabled):
		btn = self.getControl(BUTTON_ADD_LIST)
		btn.setEnabled(enabled)
	
	def setInfoLabel(self, text):
		pl = self.getControl(LABEL)
		pl.setLabel(text)

	def populateLists(self):
		self.list.reset()
		if utils.getSettingAsBool('tagging_watchlists'):
			item = xbmcgui.ListItem('Watchlist')
			self.list.addItem(item)

		for list in sorted(self.lists.iterkeys()):
			if list.lower() == "watchlist":
				continue
			item = xbmcgui.ListItem(list)
			self.list.addItem(item)

	def populateTypes(self):
		self.list.reset()
		items = ["..", "Movies", "TV Shows"]
		for l in items:
			item = xbmcgui.ListItem(l)
			self.list.addItem(l)

	def populateItems(self, type):
		self.list.reset()
		item = xbmcgui.ListItem('..')
		self.list.addItem(item)

		items = None
		if type == "movies":
			items = self.movieList
		else:
			items = self.showList

		for title in sorted(items.iterkeys()):
			item = xbmcgui.ListItem(title)
			item.setProperty('id', str(items[title]))
			if items[title] in self.selected[self.selectedList][type]:
				item.select(True)
			self.list.addItem(item)
