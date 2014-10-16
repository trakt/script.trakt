# -*- coding: utf-8 -*-
#

import xbmc
import time

import utilities
import tagging
from utilities import Debug
from rating import ratingCheck


class Scrobbler():

    traktapi = None
    isPlaying = False
    isPaused = False
    isMultiPartEpisode = False
    lastMPCheck = 0
    curMPEpisode = 0
    videoDuration = 1
    watchedTime = 0
    pausedAt = 0
    curVideo = None
    curVideoInfo = None
    playlistLength = 1
    playlistIndex = 0
    markedAsWatched = []
    traktSummaryInfo = None

    def __init__(self, api):
        self.traktapi = api

    def _currentEpisode(self, watchedPercent, episodeCount):
        split = (100 / episodeCount)
        for i in range(episodeCount - 1, 0, -1):
            if watchedPercent >= (i * split):
                return i
        return 0

    def update(self, forceCheck=False):
        if not xbmc.Player().isPlayingVideo():
            return

        if self.isPlaying:
            t = xbmc.Player().getTime()
            l = xbmc.PlayList(xbmc.PLAYLIST_VIDEO).getposition()
            if self.playlistIndex == l:
                self.watchedTime = t
            else:
                Debug("[Scrobbler] Current playlist item changed! Not updating time! (%d -> %d)" % (self.playlistIndex, l))

            if 'id' in self.curVideo and self.isMultiPartEpisode:
                # do transition check every minute
                if (time.time() > (self.lastMPCheck + 60)) or forceCheck:
                    self.lastMPCheck = time.time()
                    watchedPercent = (self.watchedTime / self.videoDuration) * 100
                    epIndex = self._currentEpisode(watchedPercent, self.curVideo['multi_episode_count'])
                    if self.curMPEpisode != epIndex:
                        # current episode in multi-part episode has changed
                        Debug("[Scrobbler] Attempting to scrobble episode part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))

                        # recalculate watchedPercent and duration for multi-part, and scrobble
                        adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
                        duration = adjustedDuration / 60
                        watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100
                        response = self.traktapi.scrobbleEpisode(self.curVideoInfo, duration, watchedPercent)
                        if response is not None:
                            Debug("[Scrobbler] Scrobble response: %s" % str(response))

                        # update current information
                        self.curMPEpisode = epIndex
                        self.curVideoInfo = utilities.getEpisodeDetailsFromXbmc(self.curVideo['multi_episode_data'][self.curMPEpisode], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])

                        if not forceCheck:
                            self.watching()

    def playbackStarted(self, data):
        Debug("[Scrobbler] playbackStarted(data: %s)" % data)
        if not data:
            return
        self.curVideo = data
        self.curVideoInfo = None
        # {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"item":{"type":"movie"},"player":{"playerid":1,"speed":1},"title":"Shooter","year":2007},"sender":"xbmc"}}
        # {"jsonrpc":"2.0","method":"Player.OnPlay","params":{"data":{"episode":3,"item":{"type":"episode"},"player":{"playerid":1,"speed":1},"season":4,"showtitle":"24","title":"9:00 A.M. - 10:00 A.M."},"sender":"xbmc"}}
        if 'type' in self.curVideo:
            Debug("[Scrobbler] Watching: %s" % self.curVideo['type'])
            if not xbmc.Player().isPlayingVideo():
                Debug("[Scrobbler] Suddenly stopped watching item")
                return
            xbmc.sleep(1000)  # Wait for possible silent seek (caused by resuming)
            try:
                self.watchedTime = xbmc.Player().getTime()
                self.videoDuration = xbmc.Player().getTotalTime()
            except Exception, e:
                Debug("[Scrobbler] Suddenly stopped watching item: %s" % e.message)
                self.curVideo = None
                return

            if self.videoDuration == 0:
                if utilities.isMovie(self.curVideo['type']):
                    self.videoDuration = 90
                elif utilities.isEpisode(self.curVideo['type']):
                    self.videoDuration = 30
                else:
                    self.videoDuration = 1

            self.playlistLength = len(xbmc.PlayList(xbmc.PLAYLIST_VIDEO))
            self.playlistIndex = xbmc.PlayList(xbmc.PLAYLIST_VIDEO).getposition()
            if (self.playlistLength == 0):
                Debug("[Scrobbler] Warning: Cant find playlist length, assuming that this item is by itself")
                self.playlistLength = 1

            self.traktSummaryInfo = None
            self.isMultiPartEpisode = False
            if utilities.isMovie(self.curVideo['type']):
                if 'id' in self.curVideo:
                    self.curVideoInfo = utilities.getMovieDetailsFromXbmc(self.curVideo['id'], ['imdbnumber', 'title', 'year'])
                    if utilities.getSettingAsBool('rate_movie'):
                        # pre-get sumamry information, for faster rating dialog.
                        Debug("[Scrobbler] Movie rating is enabled, pre-fetching summary information.")
                        imdb_id = self.curVideoInfo['imdbnumber']
                        if imdb_id.startswith("tt") or imdb_id.isdigit():
                            self.traktSummaryInfo = self.traktapi.getMovieSummary(self.curVideoInfo['imdbnumber'])
                            self.traktSummaryInfo['xbmc_id'] = self.curVideo['id']
                        else:
                            self.curVideoInfo['imdbnumber'] = None
                            Debug("[Scrobbler] Can not get summary information for '%s (%d)' as is has no valid id, will retry during a watching call." % (self.curVideoInfo['title'], self.curVideoInfo['year']))
                elif 'title' in self.curVideo and 'year' in self.curVideo:
                    self.curVideoInfo = {}
                    self.curVideoInfo['imdbnumber'] = None
                    self.curVideoInfo['title'] = self.curVideo['title']
                    self.curVideoInfo['year'] = self.curVideo['year']

            elif utilities.isEpisode(self.curVideo['type']):
                if 'id' in self.curVideo:
                    self.curVideoInfo = utilities.getEpisodeDetailsFromXbmc(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid'])
                    if not self.curVideoInfo:  # getEpisodeDetailsFromXbmc was empty
                        Debug("[Scrobbler] Episode details from XBMC was empty, ID (%d) seems invalid, aborting further scrobbling of this episode." % self.curVideo['id'])
                        self.curVideo = None
                        self.isPlaying = False
                        self.watchedTime = 0
                        return
                    if utilities.getSettingAsBool('rate_episode'):
                        # pre-get sumamry information, for faster rating dialog.
                        Debug("[Scrobbler] Episode rating is enabled, pre-fetching summary information.")
                        tvdb_id = self.curVideoInfo['tvdb_id']
                        if tvdb_id.isdigit() or tvdb_id.startswith("tt"):
                            self.traktSummaryInfo = self.traktapi.getEpisodeSummary(tvdb_id, self.curVideoInfo['season'], self.curVideoInfo['episode'])
                        else:
                            self.curVideoInfo['tvdb_id'] = None
                            Debug("[Scrobbler] Can not get summary information for '%s - S%02dE%02d' as it has no valid id, will retry during a watching call." % (self.curVideoInfo['showtitle'], self.curVideoInfo['season'], self.curVideoInfo['episode']))
                elif 'showtitle' in self.curVideo and 'season' in self.curVideo and 'episode' in self.curVideo:
                    self.curVideoInfo = {}
                    self.curVideoInfo['tvdb_id'] = None
                    self.curVideoInfo['year'] = None
                    if 'year' in self.curVideo:
                        self.curVideoInfo['year'] = self.curVideo['year']
                    self.curVideoInfo['showtitle'] = self.curVideo['showtitle']
                    self.curVideoInfo['season'] = self.curVideo['season']
                    self.curVideoInfo['episode'] = self.curVideo['episode']

                if 'multi_episode_count' in self.curVideo:
                    self.isMultiPartEpisode = True
                    self.markedAsWatched = []
                    episode_count = self.curVideo['multi_episode_count']
                    for i in range(episode_count):
                        self.markedAsWatched.append(False)

            self.isPlaying = True
            self.isPaused = False
            self.watching()

    def playbackResumed(self):
        if not self.isPlaying:
            return

        Debug("[Scrobbler] playbackResumed()")
        if self.isPaused:
            p = time.time() - self.pausedAt
            Debug("[Scrobbler] Resumed after: %s" % str(p))
            self.pausedAt = 0
            self.isPaused = False
            self.update(True)
            if utilities.getSettingAsBool('watching_call_on_resume'):
                self.watching()

    def playbackPaused(self):
        if not self.isPlaying:
            return

        Debug("[Scrobbler] playbackPaused()")
        self.update(True)
        Debug("[Scrobbler] Paused after: %s" % str(self.watchedTime))
        self.isPaused = True
        self.pausedAt = time.time()

    def playbackSeek(self):
        if not self.isPlaying:
            return

        Debug("[Scrobbler] playbackSeek()")
        self.update(True)
        if utilities.getSettingAsBool('watching_call_on_seek'):
            self.watching()

    def playbackEnded(self):
        if not self.isPlaying:
            return

        Debug("[Scrobbler] playbackEnded()")
        if self.curVideo is None:
            Debug("[Scrobbler] Warning: Playback ended but video forgotten.")
            return
        self.isPlaying = False
        self.markedAsWatched = []
        if self.watchedTime != 0:
            if 'type' in self.curVideo:
                ratingCheck(self.curVideo['type'], self.traktSummaryInfo, self.watchedTime, self.videoDuration, self.playlistLength)
                self.check()
            self.watchedTime = 0
            self.isMultiPartEpisode = False
        self.traktSummaryInfo = None
        self.curVideo = None
        self.playlistLength = 0
        self.playlistIndex = 0

    def watching(self):
        if not self.isPlaying:
            return

        if not self.curVideoInfo:
            return

        Debug("[Scrobbler] watching()")
        scrobbleMovieOption = utilities.getSettingAsBool('scrobble_movie')
        scrobbleEpisodeOption = utilities.getSettingAsBool('scrobble_episode')

        self.update(True)

        duration = self.videoDuration / 60
        watchedPercent = (self.watchedTime / self.videoDuration) * 100

        if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
            response = self.traktapi.watchingMovie(self.curVideoInfo, duration, watchedPercent)
            if response is not None:
                if self.curVideoInfo['imdbnumber'] is None:
                    if 'status' in response and response['status'] == "success":
                        if 'movie' in response and 'imdb_id' in response['movie']:
                            self.curVideoInfo['imdbnumber'] = response['movie']['imdb_id']
                            if 'id' in self.curVideo and utilities.getSettingAsBool('update_imdb_id'):
                                req = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": self.curVideoInfo['movieid'], "imdbnumber": self.curVideoInfo['imdbnumber']}}
                                utilities.xbmcJsonRequest(req)
                            # get summary data now if we are rating this movie
                            if utilities.getSettingAsBool('rate_movie') and self.traktSummaryInfo is None:
                                Debug("[Scrobbler] Movie rating is enabled, pre-fetching summary information.")
                                self.traktSummaryInfo = self.traktapi.getMovieSummary(self.curVideoInfo['imdbnumber'])

                Debug("[Scrobbler] Watch response: %s" % str(response))

        elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
            if self.isMultiPartEpisode:
                Debug("[Scrobbler] Multi-part episode, watching part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
                # recalculate watchedPercent and duration for multi-part
                adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
                duration = adjustedDuration / 60
                watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100

            response = self.traktapi.watchingEpisode(self.curVideoInfo, duration, watchedPercent)
            if response is not None:
                if self.curVideoInfo['tvdb_id'] is None:
                    if 'status' in response and response['status'] == "success":
                        if 'show' in response and 'tvdb_id' in response['show']:
                            self.curVideoInfo['tvdb_id'] = response['show']['tvdb_id']
                            if 'id' in self.curVideo and utilities.getSettingAsBool('update_tvdb_id'):
                                req = {"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetTVShowDetails", "params": {"tvshowid": self.curVideoInfo['tvshowid'], "imdbnumber": self.curVideoInfo['tvdb_id']}}
                                utilities.xbmcJsonRequest(req)
                            # get summary data now if we are rating this episode
                            if utilities.getSettingAsBool('rate_episode') and self.traktSummaryInfo is None:
                                Debug("[Scrobbler] Episode rating is enabled, pre-fetching summary information.")
                                self.traktSummaryInfo = self.traktapi.getEpisodeSummary(self.curVideoInfo['tvdb_id'], self.curVideoInfo['season'], self.curVideoInfo['episode'])

                Debug("[Scrobbler] Watch response: %s" % str(response))

    def stoppedWatching(self):
        Debug("[Scrobbler] stoppedWatching()")
        scrobbleMovieOption = utilities.getSettingAsBool("scrobble_movie")
        scrobbleEpisodeOption = utilities.getSettingAsBool("scrobble_episode")

        if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
            response = self.traktapi.cancelWatchingMovie()
            if response is not None:
                Debug("[Scrobbler] Cancel watch response: %s" % str(response))
        elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
            response = self.traktapi.cancelWatchingEpisode()
            if response is not None:
                Debug("[Scrobbler] Cancel watch response: %s" % str(response))

    def scrobble(self):
        if not self.curVideoInfo:
            return

        Debug("[Scrobbler] scrobble()")
        scrobbleMovieOption = utilities.getSettingAsBool('scrobble_movie')
        scrobbleEpisodeOption = utilities.getSettingAsBool('scrobble_episode')

        duration = self.videoDuration / 60
        watchedPercent = (self.watchedTime / self.videoDuration) * 100

        if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
            response = self.traktapi.scrobbleMovie(self.curVideoInfo, duration, watchedPercent)
            if not response is None and 'status' in response:
                if response['status'] == "success":
                    self.watchlistTagCheck()
                    response['title'] = response['movie']['title']
                    response['year'] = response['movie']['year']
                    self.scrobbleNotification(response)
                    Debug("[Scrobbler] Scrobble response: %s" % str(response))
                elif response['status'] == "failure":
                    if response['error'].startswith("scrobbled") and response['error'].endswith("already"):
                        Debug("[Scrobbler] Movie was just recently scrobbled, attempting to cancel watching instead.")
                        self.stoppedWatching()
                    elif response['error'] == "movie not found":
                        Debug("[Scrobbler] Movie '%s' was not found on trakt.tv, possible malformed XBMC metadata." % self.curVideoInfo['title'])

        elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
            if self.isMultiPartEpisode:
                Debug("[Scrobbler] Multi-part episode, scrobbling part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
                adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
                duration = adjustedDuration / 60
                watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100

            response = self.traktapi.scrobbleEpisode(self.curVideoInfo, duration, watchedPercent)
            if not response is None and 'status' in response:
                if response['status'] == "success":
                    response['episode']['season'] = response['season']
                    self.scrobbleNotification(response)
                    Debug("[Scrobbler] Scrobble response: %s" % str(response))
                elif response['status'] == "failure":
                    if response['error'].startswith("scrobbled") and response['error'].endswith("already"):
                        Debug("[Scrobbler] Episode was just recently scrobbled, attempting to cancel watching instead.")
                        self.stoppedWatching()
                    elif response['error'] == "show not found":
                        Debug("[Scrobbler] Show '%s' was not found on trakt.tv, possible malformed XBMC metadata." % self.curVideoInfo['showtitle'])

    def scrobbleNotification(self, info):
        if not self.curVideoInfo:
            return

        if utilities.getSettingAsBool("scrobble_notification"):
            s = utilities.getFormattedItemName(self.curVideo['type'], info)
            utilities.notification(utilities.getString(1049), s)

    def watchlistTagCheck(self):
        if not utilities.isMovie(self.curVideo['type']):
            return

        if not 'id' in self.curVideo:
            return

        if not (tagging.isTaggingEnabled() and tagging.isWatchlistsEnabled()):
            return

        id = self.curVideo['id']
        result = utilities.getMovieDetailsFromXbmc(id, ['tag'])

        if result:
            tags = result['tag']

            if tagging.hasTraktWatchlistTag(tags):
                tags.remove(tagging.listToTag("Watchlist"))
                s = utilities.getFormattedItemName(self.curVideo['type'], self.curVideoInfo)
                tagging.xbmcSetTags(id, self.curVideo['type'], s, tags)

        else:
            utilities.Debug("No data was returned from XBMC, aborting tag udpate.")

    def check(self):
        scrobbleMinViewTimeOption = utilities.getSettingAsFloat("scrobble_min_view_time")

        Debug("[Scrobbler] watched: %s / %s" % (str(self.watchedTime), str(self.videoDuration)))
        if ((self.watchedTime / self.videoDuration) * 100) >= scrobbleMinViewTimeOption:
            self.scrobble()
        else:
            self.stoppedWatching()
