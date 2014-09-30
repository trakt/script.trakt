# -*- coding: utf-8 -*-
"""Module used to launch rating dialogues and send ratings to trakt"""

import xbmc
import xbmcaddon
import xbmcgui
import utilities as utils
import tagging
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
	
	if utils.isEpisode(media_type):
		if 'rating' in summary_info['episode']:
			summary_info['rating'] = summary_info['episode']['rating']
		if 'rating_advanced' in summary_info['episode']:
			summary_info['rating_advanced'] = summary_info['episode']['rating_advanced']

	s = utils.getFormattedItemName(media_type, summary_info)

	if not globals.traktapi.settings:
		globals.traktapi.getAccountSettings()
	rating_type = globals.traktapi.settings['viewing']['ratings']['mode']

	if unrate:
		rating = None

		if rating_type == "simple":
			if not summary_info['rating'] == "false":
				rating = "unrate"
		else:
			if summary_info['rating_advanced'] > 0:
				rating = 0

		if not rating is None:
			utils.Debug("[Rating] '%s' is being unrated." % s)
			rateOnTrakt(rating, media_type, summary_info, unrate=True)
		else:
			utils.Debug("[Rating] '%s' has not been rated, so not unrating." % s)

		return

	rerate = utils.getSettingAsBool('rate_rerate')
	if not rating is None:
		if summary_info['rating_advanced'] == 0:
			utils.Debug("[Rating] Rating for '%s' is being set to '%d' manually." % (s, rating))
			rateOnTrakt(rating, media_type, summary_info)
		else:
			if rerate:
				if not summary_info['rating_advanced'] == rating:
					utils.Debug("[Rating] Rating for '%s' is being set to '%d' manually." % (s, rating))
					rateOnTrakt(rating, media_type, summary_info)
				else:
					utils.notification(utils.getString(1353), s)
					utils.Debug("[Rating] '%s' already has a rating of '%d'." % (s, rating))
			else:
				utils.notification(utils.getString(1351), s)
				utils.Debug("[Rating] '%s' is already rated." % s)
		return

	if summary_info['rating'] or summary_info['rating_advanced']:
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
		rating_type=rating_type,
		rerate=rerate
	)

	gui.doModal()
	if gui.rating:
		rating = gui.rating
		if rerate:
			rating = gui.rating
			
			if rating_type == "simple":
				if not summary_info['rating'] == "false" and rating == summary_info['rating']:
					rating = "unrate"
			else:
				if summary_info['rating_advanced'] > 0 and rating == summary_info['rating_advanced']:
					rating = 0

		if rating == 0 or rating == "unrate":
			rateOnTrakt(rating, gui.media_type, gui.media, unrate=True)
		else:
			rateOnTrakt(rating, gui.media_type, gui.media)
	else:
		utils.Debug("[Rating] Rating dialog was closed with no rating.")

	del gui

def rateOnTrakt(rating, media_type, media, unrate=False):
	utils.Debug("[Rating] Sending rating (%s) to trakt.tv" % rating)

	params = {}
	params['rating'] = rating

	if utils.isMovie(media_type):
		params['title'] = media['title']
		params['year'] = media['year']
		params['tmdb_id'] = media['tmdb_id']
		params['imdb_id'] = media['imdb_id']

		data = globals.traktapi.rateMovie(params)

	elif utils.isShow(media_type):
		params['title'] = media['title']
		params['year'] = media['year']
		params['tvdb_id'] = media['tvdb_id']
		params['imdb_id'] = media['imdb_id']

		data = globals.traktapi.rateShow(params)
	
	elif utils.isEpisode(media_type):
		params['title'] = media['show']['title']
		params['year'] = media['show']['year']
		params['season'] = media['episode']['season']
		params['episode'] = media['episode']['number']
		params['tvdb_id'] = media['show']['tvdb_id']
		params['imdb_id'] = media['show']['imdb_id']

		data = globals.traktapi.rateEpisode(params)

	else:
		return

	if data:
		s = utils.getFormattedItemName(media_type, media)
		if 'status' in data and data['status'] == "success":

			if 'xbmc_id' in media and tagging.isTaggingEnabled() and tagging.isRatingsEnabled():
				if utils.isMovie(media_type) or utils.isShow(media_type):

					id = media['xbmc_id']
					f = utils.getMovieDetailsFromXbmc if utils.isMovie(media_type) else utils.getShowDetailsFromXBMC
					result = f(id, ['tag'])
					
					if result:
						tags = result['tag']

						new_rating = rating
						if new_rating == "love":
							new_rating = 10
						elif new_rating == "hate":
							new_rating = 1

						new_rating_tag = tagging.ratingToTag(new_rating)
						if unrate:
							new_rating_tag = ""

						update = False
						if tagging.hasTraktRatingTag(tags):
							old_rating_tag = tagging.getTraktRatingTag(tags)
							if not old_rating_tag == new_rating_tag:
								tags.remove(old_rating_tag)
								update = True

						if not unrate and new_rating >= tagging.getMinRating():
							tags.append(new_rating_tag)
							update = True

						if update:
							tagging.xbmcSetTags(id, media_type, s, tags)

					else:
						utils.Debug("No data was returned from XBMC, aborting tag udpate.")

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
		10030:	'love',
		10031:	'hate',
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

	def __init__(self, xmlFile, resourcePath, forceFallback=False, media_type=None, media=None, rating_type=None, rerate=False):
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type
		self.rating = None
		self.rerate = rerate
		self.default_simple = utils.getSettingAsInt('rating_default_simple')
		self.default_advanced = utils.getSettingAsInt('rating_default_advanced')

	def onInit(self):
		self.getControl(10014).setVisible(self.rating_type == 'simple')
		self.getControl(10015).setVisible(self.rating_type == 'advanced')

		s = utils.getFormattedItemName(self.media_type, self.media, short=True)
		self.getControl(10012).setLabel(s)

		rateID = None
		if self.rating_type == 'simple':
			rateID = 10030 + self.default_simple
			if self.rerate:
				if self.media['rating'] == "hate":
					rateID = 10031
		else:
			rateID = 11029 + self.default_advanced
			if self.rerate and int(self.media['rating_advanced']) > 0:
				rateID = 11029 + int(self.media['rating_advanced'])
		self.setFocus(self.getControl(rateID))

	def onClick(self, controlID):
		if controlID in self.buttons:
			self.rating = self.buttons[controlID]
			self.close()

	def onFocus(self, controlID):
		if controlID in self.focus_labels:
			s = utils.getString(self.focus_labels[controlID])
			if self.rerate:
				if self.media['rating'] == self.buttons[controlID] or self.media['rating_advanced'] == self.buttons[controlID]:
					if utils.isMovie(self.media_type):
						s = utils.getString(1325)
					elif utils.isShow(self.media_type):
						s = utils.getString(1326)
					elif utils.isEpisode(self.media_type):
						s = utils.getString(1327)
					else:
						pass
			
			self.getControl(10013).setLabel(s)
		else:
			self.getControl(10013).setLabel('')
