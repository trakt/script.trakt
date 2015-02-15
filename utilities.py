# -*- coding: utf-8 -*-
#

import xbmc
import xbmcaddon
import time
import re
import sys
import logging
from datetime import datetime
from dateutil.tz import tzutc, tzlocal


if sys.version_info >=  (2, 7):
	import json as json
else:
	import simplejson as json

# read settings
__addon__ = xbmcaddon.Addon('script.trakt')

# make strptime call prior to doing anything, to try and prevent threading errors
time.strptime("1970-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")

logger = logging.getLogger(__name__)

REGEX_EXPRESSIONS = [ '[Ss]([0-9]+)[][._-]*[Ee]([0-9]+)([^\\\\/]*)$',
					  '[\._ \-]([0-9]+)x([0-9]+)([^\\/]*)',                     # foo.1x09
					  '[\._ \-]([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)',          # foo.109
					  '([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)',
					  '[\\\\/\\._ -]([0-9]+)([0-9][0-9])[^\\/]*',
					  'Season ([0-9]+) - Episode ([0-9]+)[^\\/]*',              # Season 01 - Episode 02
					  'Season ([0-9]+) Episode ([0-9]+)[^\\/]*',                # Season 01 Episode 02
					  '[\\\\/\\._ -][0]*([0-9]+)x[0]*([0-9]+)[^\\/]*',
					  '[[Ss]([0-9]+)\]_\[[Ee]([0-9]+)([^\\/]*)',                #foo_[s01]_[e01]
					  '[\._ \-][Ss]([0-9]+)[\.\-]?[Ee]([0-9]+)([^\\/]*)',       #foo, s01e01, foo.s01.e01, foo.s01-e01
					  's([0-9]+)ep([0-9]+)[^\\/]*',                             #foo - s01ep03, foo - s1ep03
					  '[Ss]([0-9]+)[][ ._-]*[Ee]([0-9]+)([^\\\\/]*)$',
					  '[\\\\/\\._ \\[\\(-]([0-9]+)x([0-9]+)([^\\\\/]*)$'
					 ]

def notification(header, message, time=5000, icon=__addon__.getAddonInfo('icon')):
	xbmc.executebuiltin("XBMC.Notification(%s,%s,%i,%s)" % (header, message, time, icon))

def showSettings():
	__addon__.openSettings()

def getSetting(setting):
	return __addon__.getSetting(setting).strip()

def getSettingAsBool(setting):
	return getSetting(setting).lower() == "true"

def getSettingAsFloat(setting):
	try:
		return float(getSetting(setting))
	except ValueError:
		return 0

def getSettingAsInt(setting):
	try:
		return int(getSettingAsFloat(setting))
	except ValueError:
		return 0

def getString(string_id):
	return __addon__.getLocalizedString(string_id).encode('utf-8', 'ignore')

def isMovie(type):
	return type == 'movie'

def isEpisode(type):
	return type == 'episode'

def isShow(type):
	return type == 'show'

def isSeason(type):
	return type == 'season'

def isValidMediaType(type):
	return type in ['movie', 'show', 'episode']

def kodiJsonRequest(params):
	data = json.dumps(params)
	request = xbmc.executeJSONRPC(data)

	try:
		response = json.loads(request)
	except UnicodeDecodeError:
		response = json.loads(request.decode('utf-8', 'ignore'))

	try:
		if 'result' in response:
			return response['result']
		return None
	except KeyError:
		logger.debug("[%s] %s" % (params['method'], response['error']['message']), True)
		return None

def chunks(l, n):
	return [l[i:i+n] for i in range(0, len(l), n)]

# check exclusion settings for filename passed as argument
def checkExclusion(fullpath):

	if not fullpath:
		return True

	if (fullpath.find("pvr://") > -1) and getSettingAsBool('ExcludeLiveTV'):
		logger.debug("checkExclusion(): Video is playing via Live TV, which is currently set as excluded location.")
		return True

	if (fullpath.find("http://") > -1) and getSettingAsBool('ExcludeHTTP'):
		logger.debug("checkExclusion(): Video is playing via HTTP source, which is currently set as excluded location.")
		return True

	ExcludePath = getSetting('ExcludePath')
	if ExcludePath != "" and getSettingAsBool('ExcludePathOption'):
		if fullpath.find(ExcludePath) > -1:
			logger.debug("checkExclusion(): Video is from location, which is currently set as excluded path 1.")
			return True

	ExcludePath2 = getSetting('ExcludePath2')
	if ExcludePath2 != "" and getSettingAsBool('ExcludePathOption2'):
		if fullpath.find(ExcludePath2) > -1:
			logger.debug("checkExclusion(): Video is from location, which is currently set as excluded path 2.")
			return True

	ExcludePath3 = getSetting('ExcludePath3')
	if ExcludePath3 != "" and getSettingAsBool('ExcludePathOption3'):
		if fullpath.find(ExcludePath3) > -1:
			logger.debug("checkExclusion(): Video is from location, which is currently set as excluded path 3.")
			return True

	return False

def getFormattedItemName(type, info):
	s = None
	if isShow(type):
		s = info['title']
	elif isEpisode(type):
			s = "S%02dE%02d - %s" % (info['season'], info['number'], info['title'])
	elif isSeason(type):
		if info['season'] > 0:
			s = "%s - Season %d" % (info['title'], info['season'])
		else:
			s = "%s - Specials" % info['title']
	elif isMovie(type):
		s = "%s (%s)" % (info['title'], info['year'])
	return s.encode('utf-8', 'ignore')

def getShowDetailsFromKodi(showID, fields):
	result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShowDetails', 'params':{'tvshowid': showID, 'properties': fields}, 'id': 1})
	logger.debug("getShowDetailsFromKodi(): %s" % str(result))

	if not result:
		logger.debug("getShowDetailsFromKodi(): Result from Kodi was empty.")
		return None

	try:
		return result['tvshowdetails']
	except KeyError:
		logger.debug("getShowDetailsFromKodi(): KeyError: result['tvshowdetails']")
		return None

# get a single episode from kodi given the id
def getEpisodeDetailsFromKodi(libraryId, fields):
	result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodeDetails', 'params':{'episodeid': libraryId, 'properties': fields}, 'id': 1})
	logger.debug("getEpisodeDetailsFromKodi(): %s" % str(result))

	if not result:
		logger.debug("getEpisodeDetailsFromKodi(): Result from Kodi was empty.")
		return None

	show_data = getShowDetailsFromKodi(result['episodedetails']['tvshowid'], ['year', 'imdbnumber'])

	if not show_data:
		logger.debug("getEpisodeDetailsFromKodi(): Result from getShowDetailsFromKodi() was empty.")
		return None

	result['episodedetails']['imdbnumber'] = show_data['imdbnumber']
	result['episodedetails']['year'] = show_data['year']

	try:
		return result['episodedetails']
	except KeyError:
		logger.debug("getEpisodeDetailsFromKodi(): KeyError: result['episodedetails']")
		return None

# get a single movie from kodi given the id
def getMovieDetailsFromKodi(libraryId, fields):
	result = kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetMovieDetails', 'params':{'movieid': libraryId, 'properties': fields}, 'id': 1})
	logger.debug("getMovieDetailsFromKodi(): %s" % str(result))

	if not result:
		logger.debug("getMovieDetailsFromKodi(): Result from Kodi was empty.")
		return None

	try:
		return result['moviedetails']
	except KeyError:
		logger.debug("getMovieDetailsFromKodi(): KeyError: result['moviedetails']")
		return None

def __findInList(list, case_sensitive=True, **kwargs):
	for item in list:
		i = 0
		for key in kwargs:
			# becuause we can need to find at the root level and inside ids this is is required
			if key in item:
				key_val = item[key]
			else:
				if 'ids' in item and key in item['ids']:
					key_val = item['ids'][key]
				else:
					continue
			if not case_sensitive and isinstance(key_val, basestring):
				if key_val.lower() == kwargs[key].lower():
					i = i + 1
			else:
				# forcing the compare to be done at the string level
				if unicode(key_val) == unicode(kwargs[key]):
					i = i + 1
		if i == len(kwargs):
			return item
	return None

def findMediaObject(mediaObjectToMatch, listToSearch):
	result = None
	if result is None and 'ids' in mediaObjectToMatch and 'imdb' in mediaObjectToMatch['ids'] and unicode(mediaObjectToMatch['ids']['imdb']).startswith("tt"):
		result = __findInList(listToSearch, imdb=mediaObjectToMatch['ids']['imdb'])
	# we don't want to give up if we don't find a match based on the first field so we use if instead of elif
	if result is None and 'ids' in mediaObjectToMatch and 'tmdb' in mediaObjectToMatch['ids'] and mediaObjectToMatch['ids']['tmdb'].isdigit():
		result = __findInList(listToSearch, tmdb=mediaObjectToMatch['ids']['tmdb'])
	if result is None and 'ids' in mediaObjectToMatch and 'tvdb' in mediaObjectToMatch['ids'] and mediaObjectToMatch['ids']['tvdb'].isdigit():
		result = __findInList(listToSearch, tvdb=mediaObjectToMatch['ids']['tvdb'])
	# match by title and year it will result in movies with the same title and year to mismatch - but what should we do instead?
	if result is None and 'title' in mediaObjectToMatch and 'year' in mediaObjectToMatch:
		result = __findInList(listToSearch, title=mediaObjectToMatch['title'], year=mediaObjectToMatch['year'])
	return result

def regex_tvshow(compare, file, sub = ""):
	tvshow = 0

	for regex in REGEX_EXPRESSIONS:
		response_file = re.findall(regex, file)
		if len(response_file) > 0 :
			logger.debug("regex_tvshow(): Regex File Se: %s, Ep: %s," % (str(response_file[0][0]),str(response_file[0][1]),) )
			tvshow = 1
			if not compare :
				title = re.split(regex, file)[0]
				for char in ['[', ']', '_', '(', ')','.','-']:
					title = title.replace(char, ' ')
				if title.endswith(" "): title = title[:-1]
				return title,response_file[0][0], response_file[0][1]
			else:
				break

	if tvshow == 1:
		for regex in REGEX_EXPRESSIONS:
			response_sub = re.findall(regex, sub)
			if len(response_sub) > 0 :
				try :
					if int(response_sub[0][1]) == int(response_file[0][1]):
						return True
				except: pass
		return False
	if compare :
		return True
	else:
		return "","",""

def findMovieMatchInList(id, list):
	return next((item.to_dict() for key, item in list.items() if key[1] == str(id)), {})  #key[1] should be the imdb id

def findEpisodeMatchInList(id, seasonNumber, episodeNumber, list):
	show = next((item for key, item in list.items() if int(key[1]) == int(id)), {}) #key[1] should be the tvdb id
	logger.debug("findEpisodeMatchInList %s" % show)
	if not show:
		return {}
	else:
		if not seasonNumber in show.seasons:
			return {}
		else:	
			season = show.seasons[seasonNumber]
			if not episodeNumber in season.episodes:
				return {}
			else:	
				episode = season.episodes[episodeNumber]
				return episode.to_dict()

def kodiRpcToTraktMediaObject(type, data, mode='collected'):
	if type == 'tvshow':
		data['ids'] = {}
		id = data.pop('imdbnumber')
		if id.startswith("tt"):
			data['ids']['imdb'] = id
		elif id.isdigit():
			data['ids']['tvdb'] = id
		del(data['label'])
		return data
	elif type == 'episode':
		if checkExclusion(data['file']):
			return

		if data['playcount'] is None:
			plays = 0
		else:
			plays = data.pop('playcount')

		if plays > 0:
			watched = 1
		else:
			watched = 0

		episode = { 'season': data['season'], 'number': data['episode'], 'title': data['label'],
		            'ids': { 'tvdb': data['uniqueid']['unknown'], 'episodeid' : data['episodeid']}, 'watched': watched, 'plays': plays }
		episode['collected'] = 1 #this is in our kodi so it should be collected
		if 'lastplayed' in data:
			episode['watched_at'] = convertDateTimeToUTC(data['lastplayed'])
		if 'dateadded' in data:
			episode['collected_at'] = convertDateTimeToUTC(data['dateadded'])
		if mode == 'watched' and episode['watched']:
			return episode
		elif mode == 'collected' and episode['collected']:
			return episode
		else:
			return

	elif type == 'movie':
		if checkExclusion(data.pop('file')):
			return
		if 'lastplayed' in data:
			data['watched_at'] = convertDateTimeToUTC(data.pop('lastplayed'))
		if 'dateadded' in data:
			data['collected_at'] = convertDateTimeToUTC(data.pop('dateadded'))
		if data['playcount'] is None:
			data['plays'] = 0
		else:
			data['plays'] = data.pop('playcount')
		data['collected'] = 1 #this is in our kodi so it should be collected
		data['watched'] = 1 if data['plays'] > 0 else 0
		data['ids'] = {}
		id = data.pop('imdbnumber')
		if id.startswith("tt"):
			data['ids']['imdb'] = id
		elif id.isdigit():
			data['ids']['tmdb'] = id
		del(data['label'])
		return data
	else:
		logger.debug('[Utilities] kodiRpcToTraktMediaObject() No valid type')
		return

def kodiRpcToTraktMediaObjects(data, mode='collected'):
	if 'tvshows' in data:
		shows = data['tvshows']

		# reformat show array
		for show in shows:
			kodiRpcToTraktMediaObject('tvshow', show, mode)
		return shows

	elif 'episodes' in data:
		a_episodes = {}
		seasons = []
		for episode in data['episodes']:
			while not episode['season'] in a_episodes :
				s_no = episode['season']
				a_episodes[s_no] = []
			s_no = episode['season']
			episodeObject = kodiRpcToTraktMediaObject('episode', episode, mode)
			if episodeObject:
				a_episodes[s_no].append(episodeObject)

		for episode in a_episodes:
			seasons.append({'number': episode, 'episodes': a_episodes[episode]})
		return seasons

	elif 'movies' in data:
		movies = data['movies']
		kodi_movies = []

		# reformat movie array
		for movie in movies:
			movieObject = kodiRpcToTraktMediaObject('movie', movie, mode)
			if movieObject:
				kodi_movies.append(movieObject)
		return kodi_movies
	else:
		logger.debug('[Utilities] kodiRpcToTraktMediaObjects() No valid key found in rpc data')
		return

def convertDateTimeToUTC(toConvert):
	if toConvert:
		dateFormat = "%Y-%m-%d %H:%M:%S"
		try:
			naive = datetime.strptime(toConvert, dateFormat)
		except TypeError:
			naive = datetime(*(time.strptime(toConvert, dateFormat)[0:6]))
		local = naive.replace(tzinfo=tzlocal())
		utc = local.astimezone(tzutc())

		return unicode(utc)
	else:
		return toConvert
