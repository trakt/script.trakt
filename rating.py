# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities
import globals
from utilities import Debug, notification

__addon__ = xbmcaddon.Addon("script.trakt")

def ratingCheck(media_type, summary_info, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the rating dialog"""
	Debug("[Rating] Rating Check called for '%s'" % media_type);
	if summary_info is None:
		Debug("[Rating] Summary information is empty, aborting.")
		return
	if utilities.getSettingAsBool("rate_%s" % media_type):
		watched = (watched_time / total_time) * 100
		if watched >= utilities.getSettingAsFloat("rate_min_view_time"):
			if (playlist_length <= 1) or utilities.getSettingAsBool("rate_each_playlist_item"):
				rateMedia(media_type, summary_info)
			else:
				Debug("[Rating] Rate each playlist item is disabled.")
		else:
			Debug("[Rating] '%s' does not meet minimum view time for rating (watched: %0.2f%%, minimum: %0.2f%%)" % (current_video['type'], watched, utilities.getSettingAsFloat("rate_min_view_time")))
	else:
		Debug("[Rating] '%s' is configured to not be rated." % current_video['type'])

def rateMedia(media_type, summary_info):
	"""Launches the rating dialog"""
	if utilities.isMovie(media_type):
		if summary_info['rating'] or summary_info['rating_advanced']:
			Debug("[Rating] Movie has already been rated.")
			return

	elif utilities.isEpisode(media_type):
		if summary_info['episode']['rating'] or summary_info['episode']['rating_advanced']:
			Debug("[Rating] Episode has already been rated.")
			return

	else:
		return

	if not globals.traktapi.settings:
		globals.traktapi.getAccountSettings()
	rating_type = globals.traktapi.settings['viewing']['ratings']['mode']
	xbmc.executebuiltin('Dialog.Close(all, true)')

	gui = RatingDialog(
		"RatingDialog.xml",
		__addon__.getAddonInfo('path'),
		media_type=media_type,
		media=summary_info,
		rating_type=rating_type
	)

	gui.doModal()
	if gui.rating:
		rateOnTrakt(gui.rating, gui.media_type, gui.media)
	del gui

def rateOnTrakt(rating, media_type, media):
	Debug("[Rating] Sending rating (%s) to trakt.tv" % rating)
	if utilities.isMovie(media_type):
		params = {}
		params['title'] = media['title']
		params['year'] = media['year']
		params['rating'] = rating
		params['tmdb_id'] = media['tmdb_id']
		params['imdb_id'] = media['imdb_id']

		data = globals.traktapi.rateMovie(params)

	elif utilities.isEpisode(media_type):
		params = {}
		params['title'] = media['show']['title']
		params['year'] = media['show']['year']
		params['season'] = media['episode']['season']
		params['episode'] = media['episode']['number']
		params['rating'] = rating
		params['tvdb_id'] = media['show']['tvdb_id']
		params['imdb_id'] = media['show']['imdb_id']

		data = globals.traktapi.rateEpisode(params)

	else:
		return

	if data != None:
		notification(utilities.getString(1201), utilities.getString(1167)) # Rating submitted successfully

class RatingDialog(xbmcgui.WindowXMLDialog):
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
		10030: 1314,
		10031: 1315,
		11030: 1315,
		11031: 1316,
		11032: 1317,
		11033: 1318,
		11034: 1319,
		11035: 1320,
		11036: 1321,
		11037: 1322,
		11038: 1323,
		11039: 1314
	}

	def __init__(self, xmlFile, resourcePath, forceFallback=False, media_type=None, media=None, rating_type=None):
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type
		self.rating = None

	def onInit(self):
		self.getControl(10014).setVisible(self.rating_type == 'simple')
		self.getControl(10015).setVisible(self.rating_type == 'advanced')

		if self.media_type == 'movie':
			self.getControl(10012).setLabel('%s (%s)' % (self.media['title'], self.media['year']))
		else:
			self.getControl(10012).setLabel('%s - %s' % (self.media['show']['title'], self.media['episode']['title']))

		if self.rating_type == 'simple':
			self.setFocus(self.getControl(10030)) #Focus Loved Button
		else:
			self.setFocus(self.getControl(11037)) #Focus 8 Button

	def onClick(self, controlID):
		if controlID in self.buttons:
			self.rating = self.buttons[controlID]
			self.close()

	def onFocus(self, controlID):
		if controlID in self.focus_labels:
			self.getControl(10013).setLabel(utilities.getString(self.focus_labels[controlID]))
		else:
			self.getControl(10013).setLabel('')
