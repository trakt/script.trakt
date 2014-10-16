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

    traktLists = None
    traktListData = None
    traktListsLast = 0

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
        if force or self.traktListData is None or self.traktLists is None or (time() - self.traktListsLast) > (60 * 10):
            utils.Debug("[Tagger] Getting lists from trakt.tv")
            data = self.traktapi.getUserLists()

            if not isinstance(data, list):
                utils.Debug("[Tagger] Invalid trakt.tv lists, possible error getting data from trakt.")
                return False

            lists = {}
            list_data = {}
            hidden_lists = utils.getSettingAsList('tagging_hidden_lists')

            for item in data:
                lists[item['name']] = item['slug']
                del(item['url'])
                list_data[item['slug']] = copy.deepcopy(item)
                list_data[item['slug']]['hide'] = item['slug'] in hidden_lists

            self.traktLists = lists
            self.traktListData = list_data
            self.traktListsLast = time()
        else:
            utils.Debug("[Tagger] Using cached lists.")

        return self.traktLists

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
                slug = self.traktLists[list]
                params['slug'] = slug
            else:
                list_privacy = utils.getSettingAsInt('tagging_list_privacy')
                allow_shouts = utils.getSettingAsBool('tagging_list_allowshouts')

                utils.Debug("[Tagger] Creating new list '%s'" % list)
                result = self.traktapi.userListAdd(list, PRIVACY_LIST[list_privacy], allow_shouts=allow_shouts)

                if result and 'status' in result and result['status'] == 'success':
                    slug = result['slug']
                    params['slug'] = slug
                    self.traktLists[list] = slug
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

        slug = self.traktLists[list]
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

        for list_name in xbmc_lists:
            if not list_name in trakt_lists:
                xbmc_update['movies'].extend(xbmc_lists[listName]['movies'])
                xbmc_update['shows'].extend(xbmc_lists[listName]['shows'])

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

        d = traktManageListsDialog(lists=self.traktListData, xbmc_data=self.xbmcData, selected=selected)
        d.doModal()
        _button = d.button
        _dirty = d.dirty
        _newSelected = d.selected
        _listData = d.listData
        del d

        if _button == BUTTON_OK:
            if _dirty:
                newSelected = _newSelected

                tags = {'movies': {}, 'shows': {}}
                ratingTags = {'movies': {}, 'shows': {}}
                tagUpdates = {'movies': [], 'shows': []}
                traktUpdates = {}

                # apply changes and create new lists first.
                tStart = time()
                _lists_changed = []
                _lists_added = []
                keys_ignore = ['hide', 'slug', 'url']
                for slug in _listData:
                    if not slug in self.traktListData:
                        _lists_added.append(slug)
                        continue
                    for key in _listData[slug]:
                        if key in keys_ignore:
                            continue
                        if not _listData[slug][key] == self.traktListData[slug][key]:
                            _lists_changed.append(slug)
                            break

                _old_hidden = [slug for slug in self.traktListData if self.traktListData[slug]['hide']]
                _new_hidden = [slug for slug in _listData if _listData[slug]['hide']]
                if not set(_new_hidden) == set(_old_hidden):
                    utils.Debug("[Tagger] Updating hidden lists to '%s'." % str(_new_hidden))
                    utils.setSettingFromList('tagging_hidden_lists', _new_hidden)

                if _lists_changed:
                    for slug in _lists_changed:
                        params = {}
                        params['slug'] = slug
                        for key in _listData[slug]:
                            if key in keys_ignore:
                                continue
                            params[key] = _listData[slug][key]

                        if self.simulate:
                            utils.Debug("[Tagger] Update list '%s' with params: %s" % (slug, str(params)))
                        else:
                            result = self.traktapi.userListUpdate(params)
                            if result and 'status' in result and result['status'] == 'success':
                                new_slug = result['slug']
                                if not slug == new_slug:
                                    new_list_name = _listData[slug]['name']
                                    old_list_name = self.traktListData[slug]['name']
                                    self.traktLists[new_list_name] = new_slug
                                    del(self.traktLists[old_list_name])
                                    selected[new_list_name] = selected.pop(old_list_name)
                                    _listData[new_slug] = _listData.pop(slug)
                                    _listData[new_slug]['slug'] = new_slug

                if _lists_added:
                    for list_name in _lists_added:
                        list_data = _listData[list_name]
                        result = self.traktapi.userListAdd(list_name, list_data['privacy'], list_data['description'], list_data['allow_shouts'], list_data['show_numbers'])

                        if result and 'status' in result and result['status'] == 'success':
                            slug = result['slug']
                            self.traktLists[list_name] = slug
                            _listData[slug] = _listData.pop(list_name)
                        else:
                            utils.Debug("[Tagger] There was a problem create the list '%s' on trakt.tv" % list)

                tTaken = time() - tStart
                utils.Debug("[Tagger] Time to update trakt.tv list settings: %0.3f seconds." % tTaken)

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

                self.traktLists = None
                self.traktListData = None

    def itemLists(self, data):

        lists = self.getTraktLists()

        if not isinstance(lists, dict):
            utils.Debug("[Tagger] Error getting lists from trakt.tv.")
            return

        d = traktItemListsDialog(list_data=self.traktListData, data=data)
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
GROUP_LIST_SETTINGS		= 100
LIST_PRIVACY_SETTING	= 111
LIST_OTHER_SETTINGS		= 141
BUTTON_EDIT_DESC		= 113
BUTTON_RENAME			= 114
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

    def __new__(cls, list_data, data):
        return super(traktItemListsDialog, cls).__new__(cls, "traktListDialog.xml", __addon__.getAddonInfo('path'), list_data=list_data, data=data) 

    def __init__(self, *args, **kwargs):
        data = kwargs['data']
        list_data = kwargs['list_data']
        self.data = data
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
        utils.Debug(str(list_data))
        for slug in list_data:
            list_name = list_data[slug]['name']
            hidden = list_data[slug]['hide']
            if not hidden and not list_name in self.tags:
                self.tags[list_name] = False

        if (not 'Watchlist' in self.tags) and utils.getSettingAsBool('tagging_watchlists'):
            self.tags['Watchlist'] = False

        super(traktItemListsDialog, self).__init__()

    def onInit(self):
        grp = self.getControl(GROUP_LIST_SETTINGS)
        grp.setEnabled(False)
        grp.setVisible(False)
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
    selectedList = None

    def __new__(cls, lists, xbmc_data, selected):
        return super(traktManageListsDialog, cls).__new__(cls, "traktListDialog.xml", __addon__.getAddonInfo('path'), lists=lists, xbmc_data=xbmc_data, selected=selected)

    def __init__(self, *args, **kwargs):
        self.listData = copy.deepcopy(kwargs['lists'])
        self.lists = {}
        for l in self.listData:
            list_data = self.listData[l]
            self.lists[list_data['name']] = l
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
        l = self.getControl(LIST_PRIVACY_SETTING)
        lang = utils.getString
        privacy_settings = [lang(1671), lang(1672), lang(1673)]
        for i in range(len(privacy_settings)):
            l.addItem(self.newListItem(privacy_settings[i], id=PRIVACY_LIST[i]))

        l = self.getControl(LIST_OTHER_SETTINGS)
        other_settings = [lang(1674), lang(1675), lang(1676)]
        keys = ["allow_shouts", "show_numbers", "hide"]
        for i in range(len(other_settings)):
            l.addItem(self.newListItem(other_settings[i], id=keys[i]))

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

            elif cID == LIST_PRIVACY_SETTING:
                self.dirty = True
                l = self.getControl(cID)
                for i in range(0, l.size()):
                    item = l.getListItem(i)
                    item.select(False)
                item = l.getSelectedItem()
                item.select(True)
                key = item.getProperty('id')
                list_slug = self.lists[self.selectedList]
                list_data = self.listData[list_slug]
                old_privacy = list_data['privacy']
                list_data['privacy'] = key
                utils.Debug("[Tagger] Dialog: Changing privacy from '%s' to '%s' for '%s'." % (old_privacy, key, self.selectedList))

            elif cID == LIST_OTHER_SETTINGS:
                self.dirty = True
                l = self.getControl(cID)
                item = l.getSelectedItem()
                selected = not item.isSelected()
                item.select(selected)
                key = item.getProperty('id')
                list_slug = self.lists[self.selectedList]
                list_data = self.listData[list_slug]
                list_data[key] = selected
                utils.Debug("[Tagger] Dialog: Changing %s for '%s' to '%s'" % (key, self.selectedList, str(selected)))

    def getKeyboardInput(self, title="", default=""):
        kbd = xbmc.Keyboard(default, title)
        kbd.doModal()
        if kbd.isConfirmed() and kbd.getText():
            return kbd.getText().strip()
        return None

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
            list = self.getKeyboardInput(title=utils.getString(1654))
            if list:
                if list.lower() == "watchlist" or list.lower().startswith("rating:"):
                    utils.Debug("[Tagger] Dialog: Tried to add a reserved list name '%s'." % list)
                    utils.notification(utils.getString(1650), utils.getString(1655) % list)
                    return
                if list not in self.lists:
                    utils.Debug("[Tagger] Dialog: Adding list '%s'." % list)
                    self.lists[list] = list
                    self.selected[list] = {'movies': [], 'shows': []}
                    data = {}
                    data['name'] = list
                    data['slug'] = list
                    list_privacy = utils.getSettingAsInt('tagging_list_privacy')
                    data['privacy'] = PRIVACY_LIST[list_privacy]
                    data['allow_shouts'] = utils.getSettingAsBool('tagging_list_allowshouts')
                    data['show_numbers'] = False
                    data['hide'] = False
                    data['description'] = ""
                    self.listData[list] = data
                    self.populateLists()
                else:
                    utils.Debug("[Tagger] Dialog: '%s' already in list." % list)
                    utils.notification(utils.getString(1650), utils.getString(1656) % list)

        elif control == BUTTON_EDIT_DESC:
            list_slug = self.lists[self.selectedList]
            list_data = self.listData[list_slug]
            new_description = self.getKeyboardInput(title=utils.getString(1669), default=list_data['description'])
            if new_description:
                utils.Debug("[Tagger] Dialog: Setting new description for list '%s', '%s'." % (self.selectedList, new_description))
                self.dirty = True
                list_data['description'] = new_description

        elif control == BUTTON_RENAME:
            list_slug = self.lists[self.selectedList]
            list_data = self.listData[list_slug]
            new_name = self.getKeyboardInput(title=utils.getString(1670), default=self.selectedList)
            if new_name:
                if new_name.lower() == "watchlist" or new_name.lower().startswith("rating:"):
                    utils.Debug("[Tagger] Dialog: Tried to rename '%s' to a reserved list name '%s'." % (self.selectedList, new_name))
                    utils.notification(utils.getString(1650), utils.getString(1655) % new_name)
                    return

                if new_name in self.lists:
                    utils.Debug("[Tagger] Dialog: Already contains '%s'." % new_name)
                    utils.notification(utils.getString(1650), utils.getString(1677) % new_name)
                    return

                old_name = self.selectedList
                self.selectedList = new_name
                list_data['name'] = new_name
                self.setInfoLabel(new_name)
                self.lists[new_name] = self.lists.pop(old_name)
                self.selected[new_name] = self.selected.pop(old_name)
                self.dirty = True
                utils.Debug("[Tagger] Dialog: Renamed '%s' to '%s'." % (old_name, new_name))

        elif control in [BUTTON_OK, BUTTON_CANCEL]:
            self.close()

    def setAddListEnabled(self, enabled):
        btn = self.getControl(BUTTON_ADD_LIST)
        btn.setEnabled(enabled)

    def setListEditGroupEnabled(self, enabled):
        new_height = 138 if enabled else 380
        self.list.setHeight(new_height)
        grp = self.getControl(GROUP_LIST_SETTINGS)
        grp.setEnabled(enabled)
        grp.setVisible(enabled)
        d = {'public': 0, 'friends': 1, 'private': 2}

        if enabled:
            list_slug = self.lists[self.selectedList]
            list_data = self.listData[list_slug]
            l = self.getControl(LIST_PRIVACY_SETTING)
            for i in range(0, l.size()):
                item = l.getListItem(i)
                item.select(True if d[list_data['privacy']] == i else False)

            l = self.getControl(LIST_OTHER_SETTINGS)
            item = l.getListItem(0)
            item.select(list_data['allow_shouts'])
            item = l.getListItem(1)
            item.select(list_data['show_numbers'])
            item = l.getListItem(2)
            item.select(list_data['hide'])

    def newListItem(self, label, selected=False, *args, **kwargs):
        item = xbmcgui.ListItem(label)
        item.select(selected)
        for key in kwargs:
            item.setProperty(key, str(kwargs[key]))
        return item

    def setInfoLabel(self, text):
        pl = self.getControl(LABEL)
        pl.setLabel(text)

    def populateLists(self):
        self.list.reset()
        self.setListEditGroupEnabled(False)
        if utils.getSettingAsBool('tagging_watchlists'):
            self.list.addItem(self.newListItem("Watchlist"))

        selected_item = 0
        sorted_lists = sorted(self.lists.iterkeys())
        if "Watchlist" in sorted_lists:
            sorted_lists.remove("Watchlist")
        for index in range(len(sorted_lists)):
            if sorted_lists[index] == self.selectedList:
                selected_item = index + 1
            self.list.addItem(self.newListItem(sorted_lists[index]))
        self.list.selectItem(selected_item)

        self.setFocus(self.list)

    def populateTypes(self):
        self.list.reset()
        if not self.selectedList.lower() == "watchlist":
            self.setListEditGroupEnabled(True)
        items = ["..", "Movies", "TV Shows"]
        for l in items:
            self.list.addItem(self.newListItem(l))

        self.setFocus(self.list)

    def populateItems(self, type):
        self.list.reset()
        self.setListEditGroupEnabled(False)
        self.list.addItem("..")

        items = None
        if type == "movies":
            items = self.movieList
        else:
            items = self.showList

        for title in sorted(items.iterkeys()):
            selected = True if items[title] in self.selected[self.selectedList][type] else False
            self.list.addItem(self.newListItem(title, selected=selected, id=str(items[title])))

        self.setFocus(self.list)
