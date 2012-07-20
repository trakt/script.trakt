# -*- coding: utf-8 -*-
# 

import os, sys
import time, socket
import urllib
import thread
import threading

try: import http.client as httplib # Python 3.0 +
except ImportError: import httplib # Python 2.7 and earlier

try: from hashlib import sha as sha # Python 2.6 +
except ImportError: import sha # Python 2.5 and earlier

# Allows non-blocking http requests
class NBHTTPConnection():	 
	def __init__(self, host, port = None, strict = None, timeout = None):
		self.rawConnection = httplib.HTTPConnection(host, port, strict, timeout)
		self.response = None
		self.responseLock = threading.Lock()
		self.closing = False
	
	def request(self, method, url, body = None, headers = {}):
		self.rawConnection.request(method, url, body, headers);
	
	def hasResult(self):
		if self.responseLock.acquire(False):
			self.responseLock.release()
			return True
		else:
			return False
		
	def getResult(self):
		while not self.hasResult() and not self.closing:
			time.sleep(1)
		return self.response
	
	def go(self):
		self.responseLock.acquire()
		thread.start_new_thread(NBHTTPConnection._run, (self,))
		
	def _run(self):
		self.response = self.rawConnection.getresponse()
		self.responseLock.release()
		
	def close(self):
		self.closing = True
		self.rawConnection.close()