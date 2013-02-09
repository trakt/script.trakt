# -*- coding: utf-8 -*-
#

import xbmcaddon
import xbmcgui
from utilities import Debug

# Addon info
__addon__        = xbmcaddon.Addon(id='script.trakt')
__addonpath__    = __addon__.getAddonInfo('path')
__setting__      = __addon__.getSetting


class RatingDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, xmlFile, resourcePath, defaultName='Default', forceFallback=False, media_type=None, media=None, ratings=None, rating_type=None):
		print '[trakt] init'
		self.media_type = media_type
		self.media = media
		self.rating_type = rating_type
		print self.media

		self.poster = media['art']['poster']
		self.loved = str(ratings['loved'])
		self.hated = str(ratings['hated'])
		self.loved_percent = str(ratings['percentage'])
		self.hated_percent = str(100 - ratings['percentage'])
		Debug(self.loved)
		Debug(self.loved_percent)
		Debug(self.hated)
		Debug(self.hated_percent)


	def onInit(self):
		print '[trakt] oninit'
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

			self.setFocus(self.getControl(10030)) #Loved Button

		else:
			self.getControl(11012).setImage(self.poster)
			self.getControl(11013).setLabel(self.loved_percent+'%')
			self.getControl(11014).setLabel('%s[CR]votes' % self.loved)
			self.getControl(11015).setLabel(self.hated_percent+'%')
			self.getControl(11016).setLabel('%s[CR]votes' % self.hated)

			self.setFocus(self.getControl(11037)) #8 Button


	def onClick(self, controlID):
		if controlID in [11030, 11031, 11032, 11033, 11034, 11035, 11036, 11037, 11038, 11039]: #Advanced Ratings
			self.close()

		elif controlID == 10030: #Love Button
			self.close()

		else: #Hate Button
			self.close()
