# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities as utils
import globals

__addon__ = xbmcaddon.Addon("script.trakt")

def ratingCheck(media_type, summary_info, watched_time, total_time, playlist_length):
	"""Check if a video should be rated and if so launches the rating dialog"""
	utils.Debug("[Rating] Rating Check called for '%s'" % media_type);
	if not utils.getSettingAsBool("rate_%s" % media_type):
		utils.Debug("[Rating] '%s' is configured to not be rated." % media_type)
		return
	if summary_info is None:
		utils.Debug("[Rating] Summary information is empty, aborting.")
		return
	watched = (watched_time / total_time) * 100
	if watched >= utils.getSettingAsFloat("rate_min_view_time"):
		if (playlist_length <= 1) or utils.getSettingAsBool("rate_each_playlist_item"):
			rateMedia(media_type, summary_info)
		else:
			utils.Debug("[Rating] Rate each playlist item is disabled.")
	else:
		utils.Debug("[Rating] '%s' does not meet minimum view time for rating (watched: %0.2f%%, minimum: %0.2f%%)" % (media_type, watched, utils.getSettingAsFloat("rate_min_view_time")))

def rateMedia(media_type, summary_info, unrate=False, rating=None):
	"""Launches the rating dialog"""
	if not utils.isValidMediaType(media_type):
		return

	s = utils.getFormattedItemName(media_type, summary_info)

	utils.Debug("[Rating] Summary Info %s" % (summary_info))

	if unrate:
		rating = None

		if summary_info['user']['ratings']['rating'] > 0:
			rating = 0

		if not rating is None:
			utils.Debug("[Rating] '%s' is being unrated." % s)
			__rateOnTrakt(rating, media_type, summary_info, unrate=True)
		else:
			utils.Debug("[Rating] '%s' has not been rated, so not unrating." % s)

		return

	rerate = utils.getSettingAsBool('rate_rerate')
	if not rating is None:
		if summary_info['user']['ratings']['rating'] == 0:
			utils.Debug("[Rating] Rating for '%s' is being set to '%d' manually." % (s, rating))
			__rateOnTrakt(rating, media_type, summary_info)
		else:
			if rerate:
				if not summary_info['user']['ratings']['rating'] == rating:
					utils.Debug("[Rating] Rating for '%s' is being set to '%d' manually." % (s, rating))
					__rateOnTrakt(rating, media_type, summary_info)
				else:
					utils.notification(utils.getString(1353), s)
					utils.Debug("[Rating] '%s' already has a rating of '%d'." % (s, rating))
			else:
				utils.notification(utils.getString(1351), s)
				utils.Debug("[Rating] '%s' is already rated." % s)
		return

	if summary_info['user']['ratings'] and summary_info['user']['ratings']['rating']:
		if not rerate:
			utils.Debug("[Rating] '%s' has already been rated." % s)
			utils.notification(utils.getString(1351), s)
			return
		else:
			utils.Debug("[Rating] '%s' is being re-rated." % s)
	
	xbmc.executebuiltin('Dialog.Close(all, true)')

	gui = RatingDialog(
		"RatingDialog.xml",
		__addon__.getAddonInfo('path'),
		media_type=media_type,
		media=summary_info,
		rating_type='advanced',
		rerate=rerate
	)

	gui.doModal()
	if gui.rating:
		rating = gui.rating
		if rerate:
			rating = gui.rating
			
			if summary_info['user']['ratings'] and summary_info['user']['ratings']['rating'] > 0 and rating == summary_info['user']['ratings']['rating']:
				rating = 0

		if rating == 0 or rating == "unrate":
			__rateOnTrakt(rating, gui.media_type, gui.media, unrate=True)
		else:
			__rateOnTrakt(rating, gui.media_type, gui.media)
	else:
		utils.Debug("[Rating] Rating dialog was closed with no rating.")

	del gui

def __rateOnTrakt(rating, media_type, media, unrate=False):
	utils.Debug("[Rating] Sending rating (%s) to trakt.tv" % rating)

	params = {}
	

	if utils.isMovie(media_type):
		params = media
		params['rating'] = rating
		root = {}
		listing = [params]
		root['movies'] = listing

		data = globals.traktapi.Rate(root)

	elif utils.isShow(media_type):
		params['rating'] = rating
		params['title'] = media['title']
		params['year'] = media['year']
		params['ids'] = {}
		params['ids']['tmdb'] = media['ids']['tmdb']
		params['ids']['imdb'] = media['ids']['imdb']
		params['ids']['tvdb'] = media['ids']['tvdb']

		root = {}
		listing = [params]
		root['shows'] = listing

		data = globals.traktapi.Rate(root)
	
	elif utils.isEpisode(media_type):
		params = media
		params['rating'] = rating
		root = {}
		listing = [params]
		root['episodes'] = listing

		data = globals.traktapi.Rate(root)

	else:
		return

	if data:
		s = utils.getFormattedItemName(media_type, media)
		if 'not_found' in data and not data['not_found']:

			if not unrate:
				utils.notification(utils.getString(1350), s)
			else:
				utils.notification(utils.getString(1352), s)
		elif 'status' in data and data['status'] == "failure":
			utils.notification(utils.getString(1354), s)
		else:
			# status not in data, different problem, do nothing for now
			pass

class RatingDialog(xbmcgui.WindowXMLDialog):
	buttons = {
		11030:	1,
		11031:	2,
		11032:	3,
		11033:	4,
		11034:	5,
		11035:	6,
		11036:	7,
		11037:	8,
		11038:	9,
		11039:	10
	}

	focus_labels = {
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

	def __init__(self, xmlFile, resourcePath, forceFallback=False, media_type=None, media=None, rating_type=None, rerate=False):
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type
		self.rating = None
		self.rerate = rerate
		self.default_advanced = utils.getSettingAsInt('rating_default_advanced')

	def onInit(self):
		self.getControl(10015).setVisible(self.rating_type == 'advanced')

		s = utils.getFormattedItemName(self.media_type, self.media)
		self.getControl(10012).setLabel(s)

		rateID = None
		
		rateID = 11029 + self.default_advanced
		# TODO do we need this? - Manual Rating
		#if self.rerate and int(self.media['rating_advanced']) > 0:
		#	rateID = 11029 + int(self.media['rating_advanced'])
		self.setFocus(self.getControl(rateID))

	def onClick(self, controlID):
		if controlID in self.buttons:
			self.rating = self.buttons[controlID]
			self.close()

	def onFocus(self, controlID):
		if controlID in self.focus_labels:
			s = utils.getString(self.focus_labels[controlID])
			# TODO do we need this? - Manual Rating
			#if self.rerate:
			#	if self.media['rating'] == self.buttons[controlID] or self.media['rating_advanced'] == self.buttons[controlID]:
			#		if utils.isMovie(self.media_type):
			#			s = utils.getString(1325)
			#		elif utils.isShow(self.media_type):
			#			s = utils.getString(1326)
			#		elif utils.isEpisode(self.media_type):
			#			s = utils.getString(1327)
			#		else:
			#			pass
			
			self.getControl(10013).setLabel(s)
		else:
			self.getControl(10013).setLabel('')
