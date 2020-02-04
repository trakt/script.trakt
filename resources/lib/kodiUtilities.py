# -*- coding: utf-8 -*-
#

import xbmc
import xbmcgui
import xbmcaddon
import json
import re
import sys
import logging
from resources.lib import utilities


# read settings
__addon__ = xbmcaddon.Addon('script.trakt')

logger = logging.getLogger(__name__)

REGEX_URL = '(^https?://)(.+)'

def notification(header: str, message: str, time=5000, icon=__addon__.getAddonInfo('icon')):
    xbmc.executebuiltin("XBMC.Notification(%s,%s,%i,%s)" % (header, message, time, icon))

def showSettings():
    __addon__.openSettings()

def getSetting(setting):
    return __addon__.getSetting(setting).strip()

def setSetting(setting, value):
    __addon__.setSetting(setting, str(value))

def getSettingAsBool(setting):
    return getSetting(setting).lower() == "true"

def getSettingAsFloat(setting):
    try:
        return float(getSetting(setting))
    except ValueError:
        return 0

def getSettingAsInt(setting):
    try:
        return int(getSettingAsFloat(setting))
    except ValueError:
        return 0

def getString(string_id):
    return __addon__.getLocalizedString(string_id)

def kodiJsonRequest(params):
    data = json.dumps(params)
    request = xbmc.executeJSONRPC(data)

    response = json.loads(request)

    try:
        if 'result' in response:
            return response['result']
        return None
    except KeyError:
        logger.warn("[%s] %s" % (params['method'], response['error']['message']))
        return None

# check exclusion settings for filename passed as argument
def checkExclusion(fullpath: str) -> bool:

    if not fullpath:
        return True

    # Live TV exclusion
    if fullpath.startswith("pvr://") and getSettingAsBool('ExcludeLiveTV'):
        logger.debug("checkExclusion(): Video is playing via Live TV, which is currently set as excluded location.")
        return True

    # HTTP exclusion
    if fullpath.startswith(("http://", "https://")) and getSettingAsBool('ExcludeHTTP'):
        logger.debug("checkExclusion(): Video is playing via HTTP source, which is currently set as excluded location.")
        return True

    # Plugin exclusion
    if fullpath.startswith("plugin://") and getSettingAsBool('ExcludePlugin'):
        logger.debug("checkExclusion(): Video is playing via Plugin source, which is currently set as excluded location.")
        return True

    # Script exclusion
    if xbmcgui.Window(10000).getProperty('script.trakt.paused') == 'true' and getSettingAsBool('ExcludeScript'):
        logger.debug("checkExclusion(): Video is playing via Script source, which is currently set as excluded location.")
        return True

    # Path exclusions
    ExcludePath = getSetting('ExcludePath')
    if ExcludePath != "" and getSettingAsBool('ExcludePathOption'):
        if fullpath.startswith(ExcludePath):
            logger.debug("checkExclusion(): Video is from location, which is currently set as excluded path 1.")
            return True

    found = False
    for x in range(2,13):
        found |= utilities.checkExcludePath(getSetting('ExcludePath%i' % x), getSettingAsBool('ExcludePathOption%i' % x), fullpath, x)

    return found

def kodiRpcToTraktMediaObject(type, data, mode='collected'):
    if type == 'show':
        data['ids'] = data.pop('uniqueid')
        data['rating'] = data['userrating'] if 'userrating' in data and data['userrating'] > 0 else 0
        del data['label']
        return data
    elif type == 'episode':
        if checkExclusion(data['file']):
            return

        if data['playcount'] is None:
            plays = 0
        else:
            plays = data.pop('playcount')

        if plays > 0:
            watched = 1
        else:
            watched = 0

        episode = {'season': data['season'], 'number': data['episode'], 'title': data['label'],
                   'ids': {'episodeid': data['episodeid']}, 'watched': watched,
                   'plays': plays, 'collected': 1}

        if 'uniqueid' in data:
        if 'tmdb' in data['uniqueid']:
            episode['ids']['tmdb'] = data['uniqueid']['tmdb']
        if 'imdb' in data['uniqueid']:
            episode['ids']['imdb'] = data['uniqueid']['imdb']
        if 'tvdb' in data['uniqueid']:
            episode['ids']['tvdb'] = data['uniqueid']['tvdb']
        elif 'unknown' in data['uniqueid']:
            episode['ids']['tvdb'] = utilities.parseIdToTraktIds(data['uniqueid']['unknown'], type)[0]
        if 'lastplayed' in data:
            episode['watched_at'] = utilities.convertDateTimeToUTC(data['lastplayed'])
        if 'dateadded' in data:
            episode['collected_at'] = utilities.convertDateTimeToUTC(data['dateadded'])
        if 'runtime' in data:
            episode['runtime'] = data['runtime']
        episode['rating'] = data['userrating'] if 'userrating' in data and data['userrating'] > 0 else 0
        if mode == 'watched' and episode['watched']:
            return episode
        elif mode == 'collected' and episode['collected']:
            return episode
        else:
            return

    elif type == 'movie':
        if checkExclusion(data.pop('file')):
            return
        if 'lastplayed' in data:
            data['watched_at'] = utilities.convertDateTimeToUTC(data.pop('lastplayed'))
        if 'dateadded' in data:
            data['collected_at'] = utilities.convertDateTimeToUTC(data.pop('dateadded'))
        if data['playcount'] is None:
            data['plays'] = 0
        else:
            data['plays'] = data.pop('playcount')
        data['rating'] = data['userrating'] if 'userrating' in data and data['userrating'] > 0 else 0
        data['collected'] = 1  # this is in our kodi so it should be collected
        data['watched'] = 1 if data['plays'] > 0 else 0
        data['ids'] = data.pop('uniqueid')
        del data['label']
        return data
    else:
        logger.debug('kodiRpcToTraktMediaObject() No valid type')
        return

def kodiRpcToTraktMediaObjects(data, mode='collected'):
    if 'tvshows' in data:
        shows = data['tvshows']

        # reformat show array
        for show in shows:
            kodiRpcToTraktMediaObject('show', show, mode)
        return shows

    elif 'episodes' in data:
        a_episodes = {}
        seasons = []
        for episode in data['episodes']:
            while not episode['season'] in a_episodes:
                s_no = episode['season']
                a_episodes[s_no] = []
            s_no = episode['season']
            episodeObject = kodiRpcToTraktMediaObject('episode', episode, mode)
            if episodeObject:
                a_episodes[s_no].append(episodeObject)

        for episode in a_episodes:
            seasons.append({'number': episode, 'episodes': a_episodes[episode]})
        return seasons

    elif 'movies' in data:
        movies = data['movies']
        kodi_movies = []

        # reformat movie array
        for movie in movies:
            movieObject = kodiRpcToTraktMediaObject('movie', movie, mode)
            if movieObject:
                kodi_movies.append(movieObject)
        return kodi_movies
    else:
        logger.debug('kodiRpcToTraktMediaObjects() No valid key found in rpc data')
        return

def getShowDetailsFromKodi(showID, fields):
    result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': showID, 'properties': fields}, 'id': 1})
    logger.debug("getShowDetailsFromKodi(): %s" % str(result))

    if not result:
        logger.debug("getShowDetailsFromKodi(): Result from Kodi was empty.")
        return None

    try:
        return result['tvshowdetails']
    except KeyError:
        logger.debug("getShowDetailsFromKodi(): KeyError: result['tvshowdetails']")
        return None

def getSeasonDetailsFromKodi(seasonID, fields):
    result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetSeasonDetails', 'params': {'seasonid': seasonID, 'properties': fields}, 'id': 1})
    logger.debug("getSeasonDetailsFromKodi(): %s" % str(result))

    if not result:
        logger.debug("getSeasonDetailsFromKodi(): Result from Kodi was empty.")
        return None

    try:
        return result['seasondetails']
    except KeyError:
        logger.debug("getSeasonDetailsFromKodi(): KeyError: result['seasondetails']")
        return None

# get a single episode from kodi given the id
def getEpisodeDetailsFromKodi(libraryId, fields):
    result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodeDetails', 'params': {'episodeid': libraryId, 'properties': fields}, 'id': 1})
    logger.debug("getEpisodeDetailsFromKodi(): %s" % str(result))

    if not result:
        logger.debug("getEpisodeDetailsFromKodi(): Result from Kodi was empty.")
        return None

    show_data = getShowDetailsFromKodi(result['episodedetails']['tvshowid'], ['year', 'uniqueid'])

    if not show_data:
        logger.debug("getEpisodeDetailsFromKodi(): Result from getShowDetailsFromKodi() was empty.")
        return None

    result['episodedetails']['show_ids'] = show_data['uniqueid']
    result['episodedetails']['year'] = show_data['year']

    try:
        return result['episodedetails']
    except KeyError:
        logger.debug("getEpisodeDetailsFromKodi(): KeyError: result['episodedetails']")
        return None

# get a single movie from kodi given the id
def getMovieDetailsFromKodi(libraryId, fields):
    result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': libraryId, 'properties': fields}, 'id': 1})
    logger.debug("getMovieDetailsFromKodi(): %s" % str(result))

    if not result:
        logger.debug("getMovieDetailsFromKodi(): Result from Kodi was empty.")
        return None

    try:
        return result['moviedetails']
    except KeyError:
        logger.debug("getMovieDetailsFromKodi(): KeyError: result['moviedetails']")
        return None

def checkAndConfigureProxy():
    proxyActive = kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.usehttpproxy"}, 'id': 1})['value']
    proxyType = kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.httpproxytype"}, 'id': 1})['value']

    if proxyActive and proxyType == 0: # PROXY_HTTP
        proxyURL = kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.httpproxyserver"}, 'id': 1})['value']
        proxyPort = str(kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.httpproxyport"}, 'id': 1})['value'])
        proxyUsername = kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.httpproxyusername"}, 'id': 1})['value']
        proxyPassword = kodiJsonRequest({'jsonrpc': '2.0', "method":"Settings.GetSettingValue", "params":{"setting":"network.httpproxypassword"}, 'id': 1})['value']

        if proxyUsername and proxyPassword and proxyURL and proxyPort:
            regexUrl = re.compile(REGEX_URL)
            matchURL = regexUrl.search(proxyURL)
            if matchURL:
                return matchURL.group(1) + proxyUsername + ':' + proxyPassword + '@' + matchURL.group(2) + ':' + proxyPort
        elif proxyURL and proxyPort:
            return proxyURL + ':' + proxyPort

    return None

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

def getInfoLabelDetails(result):
    type = result['item']['type']
    data = {'action': 'started'}
    # check type of item
    if 'id' not in result['item'] or type == 'channel':
        # do a deeper check to see if we have enough data to perform scrobbles
        logger.debug("getInfoLabelDetails - Started playing a non-library file, checking available data.")
        season = int(xbmc.getInfoLabel('VideoPlayer.Season') or '-1')
        episode = int(xbmc.getInfoLabel('VideoPlayer.Episode') or '-1')
        showtitle = (xbmc.getInfoLabel('VideoPlayer.TVShowTitle') or xbmc.getInfoLabel('VideoPlayer.Title'))
        title = xbmc.getInfoLabel('VideoPlayer.EpisodeName')
        year = (xbmc.getInfoLabel('VideoPlayer.Year') or utilities.regex_year(showtitle)[1])
        video_ids = xbmcgui.Window(10000).getProperty('script.trakt.ids')
        if video_ids:
            data['video_ids'] = json.loads(video_ids)
        logger.debug("getInfoLabelDetails info - ids: %s, showtitle: %s, Year: %s, Season: %s, Episode: %s" % (video_ids, showtitle, year, season, episode))

        if season >= 0 and episode > 0 and (showtitle or video_ids):
            # we have season, episode and either a show title or video_ids, can scrobble this as an episode
            type = 'episode'
            data['type'] = 'episode'
            data['season'] = season
            data['episode'] = episode
            data['showtitle'] = showtitle
            data['title'] = (title or showtitle)
            if year.isdigit():
                data['year'] = int(year)
            logger.debug("getInfoLabelDetails - Playing a non-library 'episode' - %s - S%02dE%02d - %s." % (data['showtitle'], data['season'], data['episode'], data['title']))
        elif (year or video_ids) and season < 0 and not title:
            # we have a year or video_id and no season/showtitle info, enough for a movie
            type = 'movie'
            data['type'] = 'movie'
            if year.isdigit():
                data['year'] = int(year)
            data['title'] = utilities.regex_year(showtitle)[0]
            logger.debug("getInfoLabelDetails - Playing a non-library 'movie' - %s (%s)." % (data['title'], data.get('year', 'NaN')))
        elif (showtitle or title):
            title, season, episode = utilities.regex_tvshow(title)
            if season < 0 and episode < 0:
                title, season, episode = utilities.regex_tvshow(showtitle)
            data['type'] = 'episode'
            data['season'] = season
            data['episode'] = episode
            data['title'] = data['showtitle'] = (title or showtitle)
            logger.debug("getInfoLabelDetails - Title: %s, showtitle: %s, season: %d, episode: %d" % (title, showtitle, season, episode))
        else:
            logger.debug("getInfoLabelDetails - Non-library file, not enough data for scrobbling, skipping.")
            return {}, {}
    return type, data