# -*- coding: utf-8 -*-
#

import xbmc
import time
import logging
import utilities
import math
from rating import ratingCheck

logger = logging.getLogger(__name__)

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
    traktShowSummary = None

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
                logger.debug("Current playlist item changed! Not updating time! (%d -> %d)" % (self.playlistIndex, l))

            if 'id' in self.curVideo and self.isMultiPartEpisode:
                # do transition check every minute
                if (time.time() > (self.lastMPCheck + 60)) or forceCheck:
                    self.lastMPCheck = time.time()
                    watchedPercent = self.__calculateWatchedPercent()
                    epIndex = self._currentEpisode(watchedPercent, self.curVideo['multi_episode_count'])
                    if self.curMPEpisode != epIndex:
                        # current episode in multi-part episode has changed
                        logger.debug("Attempting to stop scrobble episode part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))

                        # recalculate watchedPercent and duration for multi-part, and scrobble
                        adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
                        watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100
                        response = self.traktapi.scrobbleEpisode(self.traktShowSummary, self.curVideoInfo, watchedPercent, 'stop')
                        if response is not None:
                            logger.debug("Scrobble response: %s" % str(response))

                        # update current information
                        self.curMPEpisode = epIndex
                        self.curVideoInfo = utilities.kodiRpcToTraktMediaObject('episode', utilities.getEpisodeDetailsFromKodi(self.curVideo['multi_episode_data'][self.curMPEpisode], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid', 'file', 'playcount']))

                        if not forceCheck:
                            logger.debug("Attempting to start scrobble episode part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
                            response = self.traktapi.scrobbleEpisode(self.traktShowSummary, self.curVideoInfo, 0, 'start')
                            if response is not None:
                                logger.debug("Scrobble response: %s" % str(response))

    def playbackStarted(self, data):
        logger.debug("playbackStarted(data: %s)" % data)
        if not data:
            return
        self.curVideo = data
        self.curVideoInfo = None

        if 'type' in self.curVideo:
            logger.debug("Watching: %s" % self.curVideo['type'])
            if not xbmc.Player().isPlayingVideo():
                logger.debug("Suddenly stopped watching item")
                return
            xbmc.sleep(1000)  # Wait for possible silent seek (caused by resuming)
            try:
                self.watchedTime = xbmc.Player().getTime()
                self.videoDuration = xbmc.Player().getTotalTime()
            except Exception as e:
                logger.debug("Suddenly stopped watching item: %s" % e.message)
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
            if self.playlistLength == 0:
                logger.debug("Warning: Cant find playlist length, assuming that this item is by itself")
                self.playlistLength = 1

            self.isMultiPartEpisode = False
            if utilities.isMovie(self.curVideo['type']):
                if 'id' in self.curVideo:
                    self.curVideoInfo = utilities.kodiRpcToTraktMediaObject('movie', utilities.getMovieDetailsFromKodi(self.curVideo['id'], ['imdbnumber', 'title', 'year', 'file', 'lastplayed', 'playcount']))
                elif 'title' in self.curVideo and 'year' in self.curVideo:
                    self.curVideoInfo = {'title': self.curVideo['title'], 'year': self.curVideo['year']}

            elif utilities.isEpisode(self.curVideo['type']):
                if 'id' in self.curVideo:
                    episodeDetailsKodi = utilities.getEpisodeDetailsFromKodi(self.curVideo['id'], ['showtitle', 'season', 'episode', 'tvshowid', 'uniqueid', 'file', 'playcount'])
                    tvdb = episodeDetailsKodi['imdbnumber']
                    title, year = utilities.regex_year(episodeDetailsKodi['showtitle'])
                    if not year:
                        self.traktShowSummary = {'title': episodeDetailsKodi['showtitle'], 'year': episodeDetailsKodi['year']}
                    else:
                        self.traktShowSummary = {'title': title, 'year': year}
                    if tvdb:
                        self.traktShowSummary['ids'] = {'tvdb': tvdb}
                    self.curVideoInfo = utilities.kodiRpcToTraktMediaObject('episode', episodeDetailsKodi)
                    if not self.curVideoInfo:  # getEpisodeDetailsFromKodi was empty
                        logger.debug("Episode details from Kodi was empty, ID (%d) seems invalid, aborting further scrobbling of this episode." % self.curVideo['id'])
                        self.curVideo = None
                        self.isPlaying = False
                        self.watchedTime = 0
                        return
                elif 'title' in self.curVideo and 'season' in self.curVideo and 'episode' in self.curVideo:
                    self.curVideoInfo = {'title': self.curVideo['title'], 'season': self.curVideo['season'],
                                         'number': self.curVideo['episode']}

                    title, year = utilities.regex_year(self.curVideo['showtitle'])
                    if not year:
                        self.traktShowSummary = {'title': self.curVideo['showtitle']}
                    else:
                        self.traktShowSummary = {'title': title, 'year': year}

                    if 'year' in self.curVideo:
                        self.traktShowSummary['year'] = self.curVideo['year']

                if 'multi_episode_count' in self.curVideo:
                    self.isMultiPartEpisode = True

            self.isPlaying = True
            self.isPaused = False
            result = self.__scrobble('start')
            if result:
                if utilities.isMovie(self.curVideo['type']) and utilities.getSettingAsBool('rate_movie'):
                    # pre-get sumamry information, for faster rating dialog.
                    logger.debug("Movie rating is enabled, pre-fetching summary information.")
                    if result['movie']['ids']['imdb']:
                        self.curVideoInfo['user'] = {'ratings': self.traktapi.getMovieRatingForUser(result['movie']['ids']['imdb'])}
                        self.curVideoInfo['ids'] = result['movie']['ids']
                    else:
                        logger.debug("'%s (%d)' has no valid id, can't get rating." % (self.curVideoInfo['title'], self.curVideoInfo['year']))
                elif utilities.isEpisode(self.curVideo['type']) and utilities.getSettingAsBool('rate_episode'):
                    # pre-get sumamry information, for faster rating dialog.
                    logger.debug("Episode rating is enabled, pre-fetching summary information.")

                    if result['show']['ids']['tvdb']:
                        self.curVideoInfo['user'] = {'ratings': self.traktapi.getEpisodeRatingForUser(result['show']['ids']['tvdb'], self.curVideoInfo['season'], self.curVideoInfo['number'])}
                        self.curVideoInfo['ids'] = result['episode']['ids']
                    else:
                        logger.debug("'%s - S%02dE%02d' has no valid id, can't get rating." % (self.curVideoInfo['showtitle'], self.curVideoInfo['season'], self.curVideoInfo['episode']))

    def playbackResumed(self):
        if not self.isPlaying:
            return

        logger.debug("playbackResumed()")
        if self.isPaused:
            p = time.time() - self.pausedAt
            logger.debug("Resumed after: %s" % str(p))
            self.pausedAt = 0
            self.isPaused = False
            self.update(True)
            self.__scrobble('start')

    def playbackPaused(self):
        if not self.isPlaying:
            return

        logger.debug("playbackPaused()")
        self.update(True)
        logger.debug("Paused after: %s" % str(self.watchedTime))
        self.isPaused = True
        self.pausedAt = time.time()
        self.__scrobble('pause')

    def playbackSeek(self):
        if not self.isPlaying:
            return

        logger.debug("playbackSeek()")
        self.update(True)
        self.__scrobble('start')

    def playbackEnded(self):
        if not self.isPlaying:
            return

        logger.debug("playbackEnded()")
        if self.curVideo is None:
            logger.debug("Warning: Playback ended but video forgotten.")
            return
        self.isPlaying = False
        if self.watchedTime != 0:
            if 'type' in self.curVideo:
                self.__scrobble('stop')
                ratingCheck(self.curVideo['type'], self.curVideoInfo, self.watchedTime, self.videoDuration, self.playlistLength)
            self.watchedTime = 0
            self.isMultiPartEpisode = False
        self.curVideoInfo = None
        self.curVideo = None
        self.playlistLength = 0
        self.playlistIndex = 0

    def __calculateWatchedPercent(self):
        return (self.watchedTime / math.floor(self.videoDuration)) * 100  # we need to floor this, so this calculation yields the same result as the playback progress calculation

    def __scrobble(self, status):
        if not self.curVideoInfo:
            return

        logger.debug("scrobble()")
        scrobbleMovieOption = utilities.getSettingAsBool('scrobble_movie')
        scrobbleEpisodeOption = utilities.getSettingAsBool('scrobble_episode')

        watchedPercent = self.__calculateWatchedPercent()

        if utilities.isMovie(self.curVideo['type']) and scrobbleMovieOption:
            response = self.traktapi.scrobbleMovie(self.curVideoInfo, watchedPercent, status)
            if not response is None:
                self.__scrobbleNotification(response)
                logger.debug("Scrobble response: %s" % str(response))
                return response

        elif utilities.isEpisode(self.curVideo['type']) and scrobbleEpisodeOption:
            if self.isMultiPartEpisode:
                logger.debug("Multi-part episode, scrobbling part %d of %d." % (self.curMPEpisode + 1, self.curVideo['multi_episode_count']))
                adjustedDuration = int(self.videoDuration / self.curVideo['multi_episode_count'])
                watchedPercent = ((self.watchedTime - (adjustedDuration * self.curMPEpisode)) / adjustedDuration) * 100

            response = self.traktapi.scrobbleEpisode(self.traktShowSummary, self.curVideoInfo, watchedPercent, status)

            if not response is None:
                self.__scrobbleNotification(response)
                logger.debug("Scrobble response: %s" % str(response))
                return response

    def __scrobbleNotification(self, info):
        if not self.curVideoInfo:
            return

        if utilities.getSettingAsBool("scrobble_notification"):
            s = utilities.getFormattedItemName(self.curVideo['type'], info[self.curVideo['type']])
            utilities.notification(utilities.getString(32015), s)
