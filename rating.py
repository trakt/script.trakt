# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities
from utilities import Debug, xbmcJsonRequest, traktJsonRequest, notification, get_float_setting, get_bool_setting

__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

buttons = {
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

focus_labels = {
	10030: __language__(1314).encode('utf-8', 'ignore'),
	10031: __language__(1315).encode('utf-8', 'ignore'),
	11030: __language__(1315).encode('utf-8', 'ignore'),
	11031: __language__(1316).encode('utf-8', 'ignore'),
	11032: __language__(1317).encode('utf-8', 'ignore'),
	11033: __language__(1318).encode('utf-8', 'ignore'),
	11034: __language__(1319).encode('utf-8', 'ignore'),
	11035: __language__(1320).encode('utf-8', 'ignore'),
	11036: __language__(1321).encode('utf-8', 'ignore'),
	11037: __language__(1322).encode('utf-8', 'ignore'),
	11038: __language__(1323).encode('utf-8', 'ignore'),
	11039: __language__(1314).encode('utf-8', 'ignore')
}


def ratingCheck(current_video, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the rating dialog"""
	Debug("[Rating] Rating Check called for '%s' with id=%s" % (current_video['type'], str(current_video['id'])));
	if get_bool_setting("rate_%s" % current_video['type']):
		watched = (watched_time / total_time) * 100
		if watched >= get_float_setting("rate_min_view_time"):
			if (playlist_length <= 1) or get_bool_setting("rate_each_playlist_item"):
				rateMedia(current_video['id'], current_video['type'])
			else:
				Debug("[Rating] Rate each playlist item is disabled.")
		else:
			Debug("[Rating] '%s' does not meet minimum view time for rating (watched: %0.2f%%, minimum: %0.2f%%)" % (current_video['type'], watched, get_float_setting("rate_min_view_time")))
	else:
		Debug("[Rating] '%s' is configured to not be rated." % current_video['type'])


def rateMedia(media_id, media_type):
	"""Launches the rating dialog"""
	if media_id == None:
		Debug('[Rating] Missing media_id')
		return

	if media_type == 'movie':
		resp = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetMovieDetails', 'params': {'movieid': media_id, 'properties': ['title', 'imdbnumber', 'year']}})
		if not resp:
			Debug("[Rating] Problem getting movie data from XBMC")
			return
		
		if not resp.has_key("moviedetails"):
			Debug("[Rating] Error with movie results from XBMC, %s" % resp)
			return
			
		xbmc_media = resp["moviedetails"]
		if xbmc_media == None:
			Debug('[Rating] Failed to retrieve movie data from XBMC')
			return

		jsonString = "/movie/summary.json/%%API_KEY%%/" + xbmc_media['imdbnumber']
		trakt_summary = traktJsonRequest('POST', jsonString)
		if trakt_summary == None:
			Debug('[Rating] Failed to retrieve movie data from trakt')
			return

		if trakt_summary['rating'] or trakt_summary['rating_advanced']:
			Debug('[Rating] Movie has been rated')
			return

	else:
		resp = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetEpisodeDetails', 'params': {'episodeid': media_id, 'properties': ['uniqueid', 'tvshowid', 'episode', 'season']}})
		if not resp:
			Debug("[Rating] Problem getting episode data from XBMC")
			return
		
		if not resp.has_key("episodedetails"):
			Debug("[Rating] Error with episode results from XBMC, %s" % resp)
			return
			
		episode = resp["episodedetails"]
		if episode == None:
			Debug('[Rating] Failed to retrieve episode data from XBMC')
			return

		resp = xbmcJsonRequest({'jsonrpc': '2.0', 'id': 0, 'method': 'VideoLibrary.GetTVShowDetails', 'params': {'tvshowid': episode['tvshowid'], 'properties': ['imdbnumber']}})
		if not resp:
			Debug("[Rating] Problem getting tvshow data from XBMC")
			return
		
		if not resp.has_key("tvshowdetails"):
			Debug("[Rating] Error with tvshow results from XBMC, %s" % resp)
			return

		xbmc_media = resp["tvshowdetails"]
		if xbmc_media == None:
			Debug('[Rating] Failed to retrieve tvshow data from XBMC')
			return

		xbmc_media["episode"] = episode

		jsonString = "/show/episode/summary.json/%%API_KEY%%/" + str(xbmc_media['imdbnumber']) + "/" + str(xbmc_media['episode']['season']) + "/" + str(xbmc_media['episode']['episode'])
		trakt_summary = traktJsonRequest('POST', jsonString)
		if trakt_summary == None:
			Debug('[Rating] Failed to retrieve show/episode data from trakt')
			return

		xbmc_media['year'] = trakt_summary['show']['year']

		if trakt_summary['episode']['rating'] or trakt_summary['episode']['rating_advanced']:
			Debug('[Rating] Episode has been rated')
			return

	rating_type = utilities.traktSettings['viewing']['ratings']['mode']
	xbmc.executebuiltin('Dialog.Close(all, true)')

	gui = RatingDialog(
		"RatingDialog.xml",
		__settings__.getAddonInfo('path'),
		media_type=media_type,
		media=xbmc_media,
		rating_type=rating_type
	)

	gui.doModal()
	del gui


class RatingDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, xmlFile, resourcePath, forceFallback=False, media_type=None, media=None, rating_type=None):
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type

	def onInit(self):
		self.getControl(10014).setVisible(self.rating_type == 'simple')
		self.getControl(10015).setVisible(self.rating_type == 'advanced')

		if self.media_type == 'movie':
			self.getControl(10012).setLabel('%s (%s)' % (self.media['title'], self.media['year']))
		else:
			self.getControl(10012).setLabel('%s - %s' % (self.media['label'], self.media['episode']['label']))

		if self.rating_type == 'simple':
			self.setFocus(self.getControl(10030)) #Focus Loved Button
		else:
			self.setFocus(self.getControl(11037)) #Focus 8 Button


	def onClick(self, controlID):
		if controlID in buttons:
			self.rateOnTrakt(buttons[controlID])
			self.close()


	def onFocus(self, controlID):
		if controlID in focus_labels:
			self.getControl(10013).setLabel(focus_labels[controlID])
		else:
			self.getControl(10013).setLabel('')


	def rateOnTrakt(self, rating):
		if self.media_type == 'movie':
			params = {'title': self.media['title'], 'year': self.media['year'], 'rating': rating}

			if self.media['imdbnumber'].startswith('tt'):
				params['imdb_id'] = self.media['imdbnumber']

			elif self.media['imdbnumber'].isdigit():
				params['tmdb_id']

			data = traktJsonRequest('POST', '/rate/movie/%%API_KEY%%', params, passVersions=True)

		else:
			params = {'title': self.media['label'], 'year': self.media['year'], 'season': self.media['episode']['season'], 'episode': self.media['episode']['episode'], 'rating': rating}

			if self.media['imdbnumber'].isdigit():
				params['tvdb_id'] = self.media['imdbnumber']

			elif self.media['imdbnumber'].startswith('tt'):
				params['imdb_id'] = self.media['imdbnumber']

			data = traktJsonRequest('POST', '/rate/episode/%%API_KEY%%', params, passVersions=True)

		if data != None:
			notification(__language__(1201).encode('utf-8', 'ignore'), __language__(1167).encode('utf-8', 'ignore')) # Rating submitted successfully
