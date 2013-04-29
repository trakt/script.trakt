# -*- coding: utf-8 -*-

import utilities as utils
import xbmc
import sys

try:
	import simplejson as json
except ImportError:
	import json

def getMediaType():
	
	if xbmc.getCondVisibility('Container.Content(tvshows)'):
		return "show"
	elif xbmc.getCondVisibility('Container.Content(seasons)'):
		return "season"
	elif xbmc.getCondVisibility('Container.Content(episodes)'):
		return "episode"
	elif xbmc.getCondVisibility('Container.Content(movies)'):
		return "movie"
	else:
		return None

def getArguments():
	data = None
	
	if len(sys.argv) == 1:
		data = {'action': "sync"}
	else:
		data = {}
		for item in sys.argv:
			values = item.split("=")
			if len(values) == 2:
				data[values[0].lower()] = values[1].lower()

	return data

def Main():

	args = getArguments()

	if args['action'] == 'sync':
		# set property for service to initiate a manual sync
		utils.setProperty('traktManualSync', 'True')
	elif args['action'] in ['rate', 'unrate']:
		utils.Debug(str(args))
		data = {}
		data['action'] = args['action']
		media_type = None
		if 'media_type' in args and 'dbid' in args:
			media_type = args['media_type']
			try:
				data['dbid'] = int(args['dbid'])
			except ValueError:
				utils.Debug("Manual %s triggered for library item, but DBID is invalid." % args['action'])
				return
		elif 'media_type' in args and 'remoteid' in args:
			media_type = args['media_type']
			data['remoteid'] = args['remoteid']
			if 'season' in args:
				if not 'episode' in args:
					utils.Debug("Manual %s triggered for non-library episode, but missing episode number." % args['action'])
					return
				try:
					data['season'] = int(args['season'])
					data['episode'] = int(args['episode'])
				except ValueError:
					utilities.Debug("Error parsing season or episode for manual %s" % args['action'])
					return
		else:
			media_type = getMediaType()
			if not utils.isValidMediaType(media_type):
				utils.Debug("Error, not in video library.")
				return
			data['dbid'] = int(xbmc.getInfoLabel('ListItem.DBID'))

		if media_type is None:
			utils.Debug("Manual %s triggered on an unsupported content container." % args['action'])
		elif utils.isValidMediaType(media_type):
			data['media_type'] = media_type
			if 'dbid' in data:
				utils.Debug("Manual %s of library '%s' with an ID of '%s'." % (args['action'], media_type, data['dbid']))
			else:
				if 'season' in data:
					utils.Debug("Manual %s of non-library '%s' S%02dE%02d, with an ID of '%s'." % (args['action'], media_type, data['season'], data['episode'], data['remoteid']))
				else:
					utils.Debug("Manual %s of non-library '%s' with an ID of '%s'." % (args['action'], media_type, data['remoteid']))
			if args['action'] == 'rate' and 'rating' in args:
				if args['rating'] in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
					data['rating'] = int(args['rating'])
			utils.setProperty('traktManualRateData', json.dumps(data))
			utils.setProperty('traktManualRate', 'True')
		else:
			utils.Debug("Manual %s of '%s' is unsupported." % (args['action'], media_type))

if __name__ == '__main__':
	Main()