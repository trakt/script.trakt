# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmcaddon
import utilities
import windows
from utilities import Debug

__author__ = "Ralph-Gordon Paul, Adrian Cowan"
__credits__ = ["Ralph-Gordon Paul", "Adrian Cowan", "Justin Nemeth",  "Sean Rudford"]
__license__ = "GPL"
__maintainer__ = "Andrew Etches"
__email__ = "andrew.etches@dur.ac.uk"
__status__ = "Production"

__settings__ = xbmcaddon.Addon( "script.trakt" )

def ratingCheck(current_video, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the correct rating window"""
	settings = xbmcaddon.Addon("script.trakt")

	rate_movies = settings.getSetting("rate_movie")
	rate_episodes = settings.getSetting("rate_episode")
	rate_each_playlist_item = settings.getSetting("rate_each_playlist_item")
	rate_min_view_time = settings.getSetting("rate_min_view_time")

	Debug("[Rating] Rating Check called for " + current_video['type'] + " id=" + str(current_video['id']) );

	if (watched_time/total_time)*100>=float(rate_min_view_time):
		if (playlist_length <= 1) or (rate_each_playlist_item == 'true'):
			if current_video['type'] == 'movie' and rate_movies == 'true':
				rateMovie(current_video['id'])
			if current_video['type'] == 'episode' and rate_episodes == 'true':
				rateEpisode(current_video['id'])


def rateMovie(movieid):
	"""Launches the movie rating dialogue"""
	if movieid == None:
		return

	match = utilities.getMovieDetailsFromXbmc(movieid, ['imdbnumber', 'title', 'year'])
	if not match:
		#add error message here
		return

	imdbid = match['imdbnumber']
	title = match['title']
	year = match['year']

	Debug("[Rating] Rating movie '" + title + "' (IMDBID:"+str(imdbid)+")" );

	ratingType = utilities.traktSettings["viewing"]["ratings"]["mode"]
	curRating = utilities.getMovieRatingFromTrakt(imdbid, title, year, ratingType)
	if ratingType == "advanced":
		if curRating != 0:
			return
		gui = windows.RateMovieDialog("rate_advanced.xml", __settings__.getAddonInfo('path'))
	else:
		if curRating != False:
			return
		gui = windows.RateMovieDialog("rate.xml", __settings__.getAddonInfo('path'))

	gui.initDialog(imdbid, title, year, curRating, ratingType)
	gui.doModal()
	del gui


def rateEpisode(episode_id):
	if episode_id == None:
		return

	"""Launches the episode rating dialogue"""
	match = utilities.getEpisodeDetailsFromXbmc(episode_id, ['showtitle', 'season', 'episode','tvshowid'])
	if not match:
		#add error message here
		return

	tvdbid = match['tvdb_id']
	title = match['showtitle']
	year = match['year']
	season = match['season']
	episode = match['episode']

	Debug("[Rating] Rating tv episode '" + title + "' "+str(season)+"x"+str(episode)+" (TVDBID:"+str(tvdbid)+")");

	ratingType = utilities.traktSettings["viewing"]["ratings"]["mode"]
	curRating = utilities.getEpisodeRatingFromTrakt(tvdbid, title, year, season, episode, ratingType)
	if ratingType == "advanced":
		if curRating != 0:
			return
		gui = windows.RateEpisodeDialog("rate_advanced.xml", __settings__.getAddonInfo('path'))
	else:
		if curRating != False:
			return
		gui = windows.RateEpisodeDialog("rate.xml", __settings__.getAddonInfo('path'))

	gui.initDialog(tvdbid, title, year, season, episode, curRating, ratingType)
	gui.doModal()
	del gui
