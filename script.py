# -*- coding: utf-8 -*-

import utilities as utils
import xbmc
import sys
import queue
import tagging
import time
from traktContextMenu import traktContextMenu

try:
    import simplejson as json
except ImportError:
    import json


def getMediaType():

    if xbmc.getCondVisibility('Container.Content(tvshows)'):
        return "show"
    elif xbmc.getCondVisibility('Container.Content(seasons)'):
        return "season"
    elif xbmc.getCondVisibility('Container.Content(episodes)'):
        return "episode"
    elif xbmc.getCondVisibility('Container.Content(movies)'):
        return "movie"
    else:
        return None


def getArguments():
    data = None
    default_actions = {0: "sync", 1: "managelists"}
    default = utils.getSettingAsInt('default_action')
    if len(sys.argv) == 1:
        data = {'action': default_actions[default]}
    else:
        data = {}
        for item in sys.argv:
            values = item.split("=")
            if len(values) == 2:
                data[values[0].lower()] = values[1]
        data['action'] = data['action'].lower()

    return data


def Main():

    args = getArguments()
    data = {}

    if args['action'] == 'contextmenu':
        buttons = []
        media_type = getMediaType()

        if utils.getSettingAsBool('tagging_enable'):
            if utils.isMovie(media_type):
                buttons.append("itemlists")
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
                result = utils.getMovieDetailsFromXbmc(dbid, ['tag'])
                if tagging.hasTraktWatchlistTag(result['tag']):
                    buttons.append("removefromlist")
                else:
                    buttons.append("addtolist")
            elif utils.isShow(media_type):
                buttons.append("itemlists")
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
                result = utils.getShowDetailsFromXBMC(dbid, ['tag'])
                if tagging.hasTraktWatchlistTag(result['tag']):
                    buttons.append("removefromlist")
                else:
                    buttons.append("addtolist")

        if media_type in ['movie', 'show', 'episode']:
            buttons.append("rate")

        if media_type in ['movie', 'show', 'season', 'episode']:
            buttons.append("togglewatched")

        if utils.getSettingAsBool('tagging_enable'):
            buttons.append("managelists")
            buttons.append("updatetags")
        buttons.append("sync")

        contextMenu = traktContextMenu(media_type=media_type, buttons=buttons)
        contextMenu.doModal()
        _action = contextMenu.action
        del contextMenu

        if _action is None:
            return

        utils.Debug("'%s' selected from trakt.tv action menu" % _action)
        args['action'] = _action
        if _action in ['addtolist', 'removefromlist']:
            args['list'] = "watchlist"

    if args['action'] == 'sync':
        data = {'action': 'manualSync'}
        data['silent'] = False
        if 'silent' in args:
            data['silent'] = (args['silent'].lower() == 'true')
        data['library'] = "all"
        if 'library' in args and args['library'] in ['episodes', 'movies']:
            data['library'] = args['library']

    elif args['action'] == 'loadsettings':
        data = {'action': 'loadsettings', 'force': True}
        utils.notification(utils.getString(1201), utils.getString(1111))

    elif args['action'] == 'settings':
        data = {'action': 'settings'}

    elif args['action'] in ['rate', 'unrate']:
        data = {}
        data['action'] = args['action']
        media_type = None
        if 'media_type' in args and 'dbid' in args:
            media_type = args['media_type']
            try:
                data['dbid'] = int(args['dbid'])
            except ValueError:
                utils.Debug("Manual %s triggered for library item, but DBID is invalid." % args['action'])
                return
        elif 'media_type' in args and 'remoteid' in args:
            media_type = args['media_type']
            data['remoteid'] = args['remoteid']
            if 'season' in args:
                if not 'episode' in args:
                    utils.Debug("Manual %s triggered for non-library episode, but missing episode number." % args['action'])
                    return
                try:
                    data['season'] = int(args['season'])
                    data['episode'] = int(args['episode'])
                except ValueError:
                    utilities.Debug("Error parsing season or episode for manual %s" % args['action'])
                    return
        else:
            media_type = getMediaType()
            if not utils.isValidMediaType(media_type):
                utils.Debug("Error, not in video library.")
                return
            data['dbid'] = int(xbmc.getInfoLabel('ListItem.DBID'))

        if media_type is None:
            utils.Debug("Manual %s triggered on an unsupported content container." % args['action'])
        elif utils.isValidMediaType(media_type):
            data['media_type'] = media_type
            if 'dbid' in data:
                utils.Debug("Manual %s of library '%s' with an ID of '%s'." % (args['action'], media_type, data['dbid']))
                if utils.isMovie(media_type):
                    result = utils.getMovieDetailsFromXbmc(data['dbid'], ['imdbnumber', 'title', 'year'])
                    if not result:
                        utils.Debug("No data was returned from XBMC, aborting manual %s." % args['action'])
                        return
                    data['imdbnumber'] = result['imdbnumber']

                elif utils.isShow(media_type):
                    result = utils.getShowDetailsFromXBMC(data['dbid'], ['imdbnumber', 'tag'])
                    if not result:
                        utils.Debug("No data was returned from XBMC, aborting manual %s." % args['action'])
                        return
                    data['imdbnumber'] = result['imdbnumber']
                    data['tag'] = result['tag']

                elif utils.isEpisode(media_type):
                    result = utils.getEpisodeDetailsFromXbmc(data['dbid'], ['showtitle', 'season', 'episode', 'tvshowid'])
                    if not result:
                        utils.Debug("No data was returned from XBMC, aborting manual %s." % args['action'])
                        return
                    data['tvdb_id'] = result['tvdb_id']
                    data['season'] = result['season']
                    data['episode'] = result['episode']

            else:
                if 'season' in data:
                    utils.Debug("Manual %s of non-library '%s' S%02dE%02d, with an ID of '%s'." % (args['action'], media_type, data['season'], data['episode'], data['remoteid']))
                    data['tvdb_id'] = data['remoteid']
                else:
                    utils.Debug("Manual %s of non-library '%s' with an ID of '%s'." % (args['action'], media_type, data['remoteid']))
                    data['imdbnumber'] = data['remoteid']

            if args['action'] == 'rate' and 'rating' in args:
                if args['rating'] in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                    data['rating'] = int(args['rating'])

            data = {'action': 'manualRating', 'ratingData': data}

        else:
            utils.Debug("Manual %s of '%s' is unsupported." % (args['action'], media_type))

    elif args['action'] == 'togglewatched':
        media_type = getMediaType()
        if media_type in ['movie', 'show', 'season', 'episode']:
            data = {}
            data['media_type'] = media_type
            if utils.isMovie(media_type):
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
                result = utils.getMovieDetailsFromXbmc(dbid, ['imdbnumber', 'title', 'year', 'playcount'])
                if result:
                    if result['playcount'] == 0:
                        data['id'] = result['imdbnumber']
                    else:
                        utils.Debug("Movie alread marked as watched in XBMC.")
                else:
                    utils.Debug("Error getting movie details from XBMC.")
                    return

            elif utils.isEpisode(media_type):
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
                result = utils.getEpisodeDetailsFromXbmc(dbid, ['showtitle', 'season', 'episode', 'tvshowid', 'playcount'])
                if result:
                    if result['playcount'] == 0:
                        data['id'] = result['tvdb_id']
                        data['season'] = result['season']
                        data['episode'] = result['episode']
                    else:
                        utils.Debug("Episode already marked as watched in XBMC.")
                else:
                    utils.Debug("Error getting episode details from XBMC.")
                    return

            elif utils.isSeason(media_type):
                showID = None
                showTitle = xbmc.getInfoLabel('ListItem.TVShowTitle')
                result = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
                if result and 'tvshows' in result:
                    for show in result['tvshows']:
                        if show['title'] == showTitle:
                            showID = show['tvshowid']
                            data['id'] = show['imdbnumber']
                            break
                else:
                    utils.Debug("Error getting TV shows from XBMC.")
                    return

                season = xbmc.getInfoLabel('ListItem.Season')
                if season == "":
                    season = 0
                else:
                    season = int(season)

                result = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': showID, 'season': season, 'properties': ['season', 'episode', 'playcount']}, 'id': 0})
                if result and 'episodes' in result:
                    episodes = []
                    for episode in result['episodes']:
                        if episode['playcount'] == 0:
                            episodes.append(episode['episode'])

                    if len(episodes) == 0:
                        utils.Debug("'%s - Season %d' is already marked as watched." % (showTitle, season))
                        return

                    data['season'] = season
                    data['episodes'] = episodes
                else:
                    utils.Debug("Error getting episodes from '%s' for Season %d" % (showTitle, season))
                    return

            elif utils.isShow(media_type):
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
                result = utils.getShowDetailsFromXBMC(dbid, ['year', 'imdbnumber'])
                if not result:
                    utils.Debug("Error getting show details from XBMC.")
                    return
                showTitle = result['label']
                data['id'] = result['imdbnumber']
                result = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': dbid, 'properties': ['season', 'episode', 'playcount']}, 'id': 0})
                if result and 'episodes' in result:
                    i = 0
                    s = {}
                    for e in result['episodes']:
                        season = str(e['season'])
                        if not season in s:
                            s[season] = []
                        if e['playcount'] == 0:
                            s[season].append(e['episode'])
                            i = i + 1

                    if i == 0:
                        utils.Debug("'%s' is already marked as watched." % showTitle)
                        return

                    data['seasons'] = dict((k, v) for k, v in s.iteritems() if v)
                else:
                    utils.Debug("Error getting episode details for '%s' from XBMC." % showTitle)
                    return

            if len(data) > 1:
                utils.Debug("Marking '%s' with the following data '%s' as watched on trakt.tv" % (media_type, str(data)))
                data['action'] = 'markWatched'

        # execute toggle watched action
        xbmc.executebuiltin("Action(ToggleWatched)")

    elif args['action'] == 'updatetags':
        data = {'action': 'updatetags'}

    elif args['action'] == 'managelists':
        data = {'action': 'managelists'}

    elif args['action'] == 'timertest':
        utils.Debug("Timing JSON requests.")
        import time
        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': 254, 'properties': ['tag']}, 'id': 1})
        #data = utils.getShowDetailsFromXBMC(254, ['tag', 'imdbnumber'])
        e = time.time() - t
        utils.Debug("VideoLibrary.GetTVShowDetails with tags: %0.3f seconds." % e)

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': 634, 'properties': ['tag']}, 'id': 1})
        #data = utils.getMovieDetailsFromXbmc(634, ['tag', 'imdbnumber', 'title', 'year'])
        e = time.time() - t
        utils.Debug("VideoLibrary.GetMovieDetails with tags: %0.3f seconds." % e)

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['tag', 'title', 'imdbnumber', 'year']}, 'id': 0})
        e = time.time() - t
        utils.Debug("VideoLibrary.GetTVShows with tags: %0.3f seconds, %d items at %0.5f seconds per item" % (e, len(data['tvshows']), e / len(data['tvshows'])))

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['tag', 'title', 'imdbnumber', 'year']}})
        e = time.time() - t
        utils.Debug("VideoLibrary.GetMovies with tags: %0.3f seconds, %d items at %0.5f seconds per item" % (e, len(data['movies']), e / len(data['movies'])))

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
        e = time.time() - t
        utils.Debug("VideoLibrary.GetTVShows without tags: %0.3f seconds, %d items at %0.5f seconds per item" % (e, len(data['tvshows']), e / len(data['tvshows'])))

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year']}})
        e = time.time() - t
        utils.Debug("VideoLibrary.GetMovies without tags: %0.3f seconds, %d items at %0.5f seconds per item" % (e, len(data['movies']), e / len(data['movies'])))

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': 254, 'properties': ['imdbnumber']}, 'id': 1})
        #data = utils.getShowDetailsFromXBMC(254, ['imdbnumber'])
        e = time.time() - t
        utils.Debug("VideoLibrary.GetTVShowDetails without tags: %0.3f seconds." % e)

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': 634, 'properties': ['imdbnumber', 'title', 'year']}, 'id': 1})
        #data = utils.getMovieDetailsFromXbmc(634, ['imdbnumber', 'title', 'year'])
        e = time.time() - t
        utils.Debug("VideoLibrary.GetMovieDetails without tags: %0.3f seconds." % e)

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
        data = data['tvshows']
        for item in data:
            item_data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': item['tvshowid'], 'properties': ['tag']}, 'id': 1})
            item['tag'] = item_data['tvshowdetails']['tag']
        e = time.time() - t
        utils.Debug("VideoLibrary.GetTVShows with tags from loop: %0.3f seconds, %d items at %0.5f seconds per item" % (e, len(data), e / len(data)))

        t = time.time()
        data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovies', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
        data = data['movies']
        for item in data:
            item_data = utils.xbmcJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': item['movieid'], 'properties': ['tag']}, 'id': 1})
            item['tag'] = item_data['moviedetails']['tag']
        e = time.time() - t
        utils.Debug("VideoLibrary.GetMovies with tags from: %0.3f seconds, %d items at %0.5f seconds per item." % (e, len(data), e / len(data)))

    elif args['action'] in ['itemlists', 'addtolist', 'removefromlist']:
        data = {}
        data['action'] = args['action']
        media_type = None
        dbid = None
        if 'media_type' in args and 'dbid' in args:
            media_type = args['media_type']
            try:
                dbid = int(args['dbid'])
            except ValueError:
                utils.Debug("'%s' triggered for library item, but DBID is invalid." % args['action'])
                return
        else:
            media_type = getMediaType()
            if not media_type in ['movie', 'show']:
                utils.Debug("Error, not in video library.")
                return
            try:
                dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
            except ValueError:
                utils.Debug("'%s' triggered for library item, but there is a problem with ListItem.DBID." % args['action'])
                return

        if not media_type in ['movie', 'show']:
            utils.Debug("'%s' is not a valid media type for '%s'." % (media_type, args['action']))
            return

        if args['action'] in ['addtolist', 'removefromlist']:
            if 'list' in args:
                data['list'] = args['list']
            else:
                utils.Debug("'%s' requires a list parameter." % data['action'])

        data['type'] = media_type

        if utils.isMovie(media_type):
            result = utils.getMovieDetailsFromXbmc(dbid, ['imdbnumber', 'title', 'year', 'tag'])
            if not result:
                utils.Debug("Error getting movie details from XBMC.")
                return
            data['tag'] = result['tag']
            data['movieid'] = result['movieid']
            data['title'] = result['title']
            data['year'] = result['year']
            if result['imdbnumber'].startswith("tt"):
                data['imdb_id'] = result['imdbnumber']
            elif result['imdbnumber'].isdigit():
                data['tmdb_id'] = result['imdbnumber']

        elif utils.isShow(media_type):
            result = utils.getShowDetailsFromXBMC(dbid, ['imdbnumber', 'title', 'tag'])
            if not result:
                utils.Debug("Error getting show details from XBMC.")
                return
            data['tag'] = result['tag']
            data['tvshowid'] = result['tvshowid']
            data['title'] = result['title']
            if result['imdbnumber'].startswith("tt"):
                data['imdb_id'] = result['imdbnumber']
            elif result['imdbnumber'].isdigit():
                data['tvdb_id'] = result['imdbnumber']

    q = queue.SqliteQueue()
    if 'action' in data:
        utils.Debug("Queuing for dispatch: %s" % data)
        q.append(data)

if __name__ == '__main__':
    Main()
