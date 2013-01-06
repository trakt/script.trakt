# -*- coding: utf-8 -*-
""" Handles notifications from XBMC via its own thread and forwards them on to the scrobbler """

import xbmc
import telnetlib
import socket

import simplejson as json

import threading
from utilities import Debug
from scrobbler import Scrobbler
from movie_sync import SyncMovies

class NotificationService(threading.Thread):
	""" Receives XBMC notifications and passes them off as needed """

	TELNET_ADDRESS = 'localhost'
	TELNET_PORT = 9090

	_abortRequested = False
	_scrobbler = None
	_notificationBuffer = ""


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
		elif notification['method'] == 'VideoLibrary.OnScanFinished':
			movies = SyncMovies(show_progress=False)
			movies.Run()
		elif notification['method'] == 'System.OnQuit':
			self._abortRequested = True


	def _readNotification(self, telnet):
		""" Read a notification from the telnet connection, blocks until the data is available, or else raises an EOFError if the connection is lost """
		while True:
			try:
				addbuffer = telnet.read_some()
			except socket.timeout:
				continue

			if addbuffer == "":
				raise EOFError

			self._notificationBuffer += addbuffer
			try:
				data, offset = json.JSONDecoder().raw_decode(self._notificationBuffer)
				self._notificationBuffer = self._notificationBuffer[offset:]
			except ValueError:
				continue

			return data


	def run(self):
		#while xbmc is running
		self._scrobbler = Scrobbler()
		self._scrobbler.start()
		telnet = telnetlib.Telnet(self.TELNET_ADDRESS, self.TELNET_PORT)

		while not (self._abortRequested or xbmc.abortRequested):
			try:
				data = self._readNotification(telnet)
			except EOFError:
				telnet = telnetlib.Telnet(self.TELNET_ADDRESS, self.TELNET_PORT)
				self._notificationBuffer = ""
				continue

			Debug("[Notification Service] message: " + str(data))
			self._forward(data)

		telnet.close()
		self._scrobbler.abortRequested = True
		Debug("Notification service stopping")
