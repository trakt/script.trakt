# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import telnetlib
import time
import socket

import simplejson as json

import threading
from utilities import Debug
from scrobbler import Scrobbler

__settings__ = xbmcaddon.Addon("script.trakt")
__language__ = __settings__.getLocalizedString

class NotificationService(threading.Thread):
	""" Receives XBMC notifications and passes them off as needed """
	_abortRequested = False
	_scrobbler = None

	def _forward(self, notification):
		""" Fowards the notification recieved to a function on the scrobbler """
		if not ('method' in notification and 'params' in notification and 'sender' in notification['params'] and notification['params']['sender'] == 'xbmc'):
			return

		if notification['method'] == 'Player.OnStop':
			self._scrobbler.playbackEnded()
		elif notification['method'] == 'Player.OnPlay':
			if 'data' in notification['params'] and 'item' in notification['params']['data'] and 'type' in notification['params']['data']['item']:
				self._scrobbler.playbackStarted(notification['params']['data'])
		elif notification['method'] == 'Player.OnPause':
			self._scrobbler.playbackPaused()
		elif notification['method'] == 'System.OnQuit':
			self._abortRequested = True


	def run(self):
		#while xbmc is running
		self._scrobbler = Scrobbler()
		self._scrobbler.start()

		while (not (self._abortRequested or xbmc.abortRequested)):
			time.sleep(1)
			try:
				telnet = telnetlib.Telnet('localhost', 9090)
			except IOError as (errno, strerror):
				#connection failed, try again soon
				Debug("[Notification Service] Telnet too soon? ("+str(errno)+") "+strerror)
				continue

			Debug("[Notification Service] Waiting~")
			notificationBuffer = ""

			while (not (self._abortRequested or xbmc.abortRequested)):
				try:
					addbuffer = telnet.read_some()
				except socket.timeout:
					continue

				if addbuffer == "":
					break # hit EOF restart outer loop

				notificationBuffer += addbuffer
				try:
					data, offset = json.JSONDecoder().raw_decode(notificationBuffer)
					notificationBuffer = notificationBuffer[offset:]
				except ValueError:  #Not a complete json document in buffer
					continue

				Debug("[Notification Service] message: " + str(data))
				self._forward(data)

		try:
			telnet.close()
		except:
			Debug("[NotificationService] Error attempting to close the telnet connection")
			raise

		self._scrobbler.abortRequested = True
		Debug("Notification service stopping")
