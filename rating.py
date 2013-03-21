# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities
import globals
from utilities import Debug, xbmcJsonRequest, notification, getSettingAsFloat, getSettingAsBool

__addon__ = xbmcaddon.Addon("script.trakt")

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
	10030: utilities.getString(1314),
	10031: utilities.getString(1315),
	11030: utilities.getString(1315),
	11031: utilities.getString(1316),
	11032: utilities.getString(1317),
	11033: utilities.getString(1318),
	11034: utilities.getString(1319),
	11035: utilities.getString(1320),
	11036: utilities.getString(1321),
	11037: utilities.getString(1322),
	11038: utilities.getString(1323),
	11039: utilities.getString(1314)
}

def ratingCheck(current_video, summary_info, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the rating dialog"""
	Debug("[Rating] Rating Check called for '%s' with id=%s" % (current_video['type'], str(current_video['id'])));
	if getSettingAsBool("rate_%s" % current_video['type']):
		watched = (watched_time / total_time) * 100
		if watched >= getSettingAsFloat("rate_min_view_time"):
			if (playlist_length <= 1) or getSettingAsBool("rate_each_playlist_item"):
				rateMedia(current_video['id'], current_video['type'], summary_info)
			else:
				Debug("[Rating] Rate each playlist item is disabled.")
		else:
			Debug("[Rating] '%s' does not meet minimum view time for rating (watched: %0.2f%%, minimum: %0.2f%%)" % (current_video['type'], watched, getSettingAsFloat("rate_min_view_time")))
	else:
		Debug("[Rating] '%s' is configured to not be rated." % current_video['type'])

def rateMedia(media_id, media_type, summary_info):
	"""Launches the rating dialog"""
	if media_id == None:
		Debug("[Rating] Missing media_id")
		return

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
	if media_type == 'movie':
		params = {}
		params['title'] = media['title']
		params['year'] = media['year']
		params['rating'] = rating
		params['tmdb_id'] = media['tmdb_id']
		params['imdb_id'] = media['imdb_id']

		data = globals.traktapi.rateMovie(params)

	else:
		params = {}
		params['title'] = media['show']['title']
		params['year'] = media['show']['year']
		params['season'] = media['episode']['season']
		params['episode'] = media['episode']['number']
		params['rating'] = rating
		params['tvdb_id'] = media['show']['tvdb_id']
		params['imdb_id'] = media['show']['imdb_id']

		data = globals.traktapi.rateEpisode(params)

	if data != None:
		notification(utilities.getString(1201), utilities.getString(1167)) # Rating submitted successfully

class RatingDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, xmlFile, resourcePath, defaultName='Default', forceFallback=False, media_type=None, media=None, rating_type=None):
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
		if controlID in buttons:
			self.rating = buttons[controlID]
			self.close()

	def onFocus(self, controlID):
		if controlID in focus_labels:
			self.getControl(10013).setLabel(focus_labels[controlID])
		else:
			self.getControl(10013).setLabel('')
