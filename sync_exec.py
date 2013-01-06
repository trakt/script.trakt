# -*- coding: utf-8 -*-

import xbmcaddon
import xbmcgui
from movie_sync import SyncMovies

def get_bool(boolean):
	return xbmcaddon.Addon('script.trakt').getSetting(boolean) == 'true'

def do_sync(media_type):
	if media_type == 'movies':
		if get_bool('add_movies_to_trakt') or get_bool('trakt_movie_playcount') or get_bool('xbmc_movie_playcount'):
			return True
	else:
		if get_bool('add_episodes_to_trakt') or get_bool('trakt_episode_playcount') or get_bool('xbmc_episode_playcount'):
			return True

	return False

if __name__ == '__main__':
	if not xbmcaddon.Addon('script.trakt').getSetting('api_key'):
		xbmcgui.Dialog().ok('trakt', 'Please enter your API key in settings'.encode( "utf-8", "ignore" )) # Please enter your API key in settings
		xbmcaddon.Addon("script.trakt").openSettings()

	else:
		if do_sync('movies'):
			movies = SyncMovies(show_progress=True)
			movies.Run()
