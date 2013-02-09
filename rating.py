# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities
from utilities import Debug, xbmcJsonRequest, traktJsonRequest, notification

__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

rate_movies = __settings__.getSetting("rate_movie")
rate_episodes = __settings__.getSetting("rate_episode")
rate_each_playlist_item = __settings__.getSetting("rate_each_playlist_item")
rate_min_view_time = __settings__.getSetting("rate_min_view_time")


def ratingCheck(current_video, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the rating dialog"""

	Debug("[Rating] Rating Check called for " + current_video['type'] + " id=" + str(current_video['id']) );
	if __settings__.getSetting("rate_"+current_video['type']):
		if (watched_time/total_time)*100>=float(rate_min_view_time):
			if (playlist_length <= 1) or (rate_each_playlist_item == 'true'):
				rateMedia(current_video['id'], current_video['type'])


def rateMedia(media_id, media_type):
	"""Launches the rating dialog"""
	if media_id == None:
		return

	if media_type == 'movie':
		xbmc_media = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': media_id, 'properties': ['title', 'imdbnumber', 'year', 'art']}})['moviedetails']
		trakt_summary = traktJsonRequest('POST', '/movie/summary.json/%%API_KEY%%/' + xbmc_media['imdbnumber'])

	else:
		xbmc_media = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetEpisodeDetails', 'params': {'episodeid': media_id, 'properties': ['title', 'uniqueid', 'tvshowid', 'showtitle', 'episode', 'season']}})['episodedetails']
		xbmc_show = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': xbmc_media['tvshowid'], 'properties': ['art', 'imdbnumber']}})['tvshowdetails']
		trakt_summary = traktJsonRequest('POST', '/show/episode/summary.json/%%API_KEY%%/'+xbmc_media['imdbnumber']+'/'+xbmc_media['season']+'/'+xbmc_media['episode'])

		xbmc_media['art'] = xbmc_show['art']
		xbmc_media['year'] = trakt_summary['show']['year']

	if not trakt_summary['rating'] and not trakt_summary['rating_advanced']:
		rating_type = utilities.traktSettings['viewing']['ratings']['mode']
		ratings = trakt_summary['ratings']

		xbmc.executebuiltin('Dialog.Close(all, true)')
		gui = RatingDialog(
			"RatingDialog.xml",
			__settings__.getAddonInfo('path'),
			media_type=media_type,
			media=xbmc_media,
			ratings=ratings,
			rating_type=rating_type
		)

		gui.doModal()
		del gui


class RatingDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, xmlFile, resourcePath, defaultName='Default', forceFallback=False, media_type=None, media=None, ratings=None, rating_type=None):
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type

		self.poster = media['art']['poster']
		self.loved = str(ratings['loved'])
		self.hated = str(ratings['hated'])
		self.loved_percent = str(ratings['percentage'])
		self.hated_percent = str(100 - ratings['percentage'])
		self.buttons = {
			10030:	'love',
			10031:	'hate',
			11030:	'1',
			11031:	'2',
			11032:	'3',
			11033:	'4',
			11034:	'5',
			11035:	'6',
			11036:	'7',
			11037:	'8',
			11038:	'9',
			11039:	'10'
		}


	def onInit(self):
		self.getControl(10111).setVisible(self.rating_type == 'simple')
		self.getControl(10112).setVisible(self.rating_type == 'advanced')


		if self.media_type == 'movie':
			self.getControl(10011).setLabel('%s (%s)' % (self.media['title'], self.media['year']))
		else:
			self.getControl(10011).setLabel('%s %s' % (self.media['showtitle'], self.media['label']))

		if self.rating_type == 'simple':
			self.getControl(10012).setImage(self.poster)
			self.getControl(10013).setLabel(self.loved_percent+'%')
			self.getControl(10014).setLabel('%s[CR]votes' % self.loved)
			self.getControl(10015).setLabel(self.hated_percent+'%')
			self.getControl(10016).setLabel('%s[CR]votes' % self.hated)

			self.setFocus(self.getControl(10030)) #Focus Loved Button

		else:
			self.getControl(11012).setImage(self.poster)
			self.getControl(11013).setLabel(self.loved_percent+'%')
			self.getControl(11014).setLabel('%s[CR]votes' % self.loved)
			self.getControl(11015).setLabel(self.hated_percent+'%')
			self.getControl(11016).setLabel('%s[CR]votes' % self.hated)

			self.setFocus(self.getControl(11037)) #Focus 8 Button


	def onClick(self, controlID):
		if controlID in self.buttons:
			self.rateOnTrakt(self.buttons[controlID])
			self.close()


	def rateOnTrakt(self, rating):
		if self.media_type == 'movie':
			params = {'title': self.media['title'], 'year': self.media['year'], 'rating': rating}

			if self.media['imdbnumber'].startswith('tt'):
				params['imdb_id'] = self.media['imdbnumber']

			elif self.media['imdbnumber'].isdigit():
				params['tmdb_id']

			data = traktJsonRequest('POST', '/rate/movie/%%API_KEY%%', params, passVersions=True)

		else:
			params = {'title': self.media['showtitle'], 'year': self.media['year'], 'season': self.media['season'], 'episode': self.media['episode'], 'rating': rating}

			if self.media['tvshowid'].isdigit():
				params['tvdb_id'] = self.media['tvshowid']

			elif self.media['imdbnumber'].startswith('tt'):
				params['imdb_id'] = self.media['tvshowid']

			data = traktJsonRequest('POST', '/rate/episode/%%API_KEY%%', params, passVersions=True)

		if data:
			notification(__language__(1201).encode( "utf-8", "ignore" ), __language__(1167).encode( "utf-8", "ignore" )) # Rating submitted successfully