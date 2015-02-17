# -*- coding: utf-8 -*-
import utilities as utils
import xbmc
import sqliteQueue
import sys
import logging

logger = logging.getLogger(__name__)

def __getMediaType():
	
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

def __getArguments():
	data = None
	default_actions = {0: "sync"}
	if len(sys.argv) == 1:
		data = {'action': default_actions[0]}
	else:
		data = {}
		for item in sys.argv:
			values = item.split("=")
			if len(values) == 2:
				data[values[0].lower()] = values[1]
		data['action'] = data['action'].lower()

	return data

def Main():

	args = __getArguments()
	data = {}

	if args['action'] == 'sync':
		data = {'action': 'manualSync', 'silent': False}
		if 'silent' in args:
			data['silent'] = (args['silent'].lower() == 'true')
		data['library'] = "all"
		if 'library' in args and args['library'] in ['episodes', 'movies']:
			data['library'] = args['library']

	elif args['action'] in ['rate', 'unrate']:
		#todo fix this
		data = {'action': args['action']}
		media_type = None
		if 'media_type' in args and 'dbid' in args:
			media_type = args['media_type']
			try:
				data['dbid'] = int(args['dbid'])
			except ValueError:
				logger.debug("Manual %s triggered for library item, but DBID is invalid." % args['action'])
				return
		elif 'media_type' in args and 'remoteid' in args:
			media_type = args['media_type']
			data['remoteid'] = args['remoteid']
			if 'season' in args:
				if not 'episode' in args:
					logger.debug("Manual %s triggered for non-library episode, but missing episode number." % args['action'])
					return
				try:
					data['season'] = int(args['season'])
					data['episode'] = int(args['episode'])
				except ValueError:
					logger.debug("Error parsing season or episode for manual %s" % args['action'])
					return
		else:
			media_type = __getMediaType()
			if not utils.isValidMediaType(media_type):
				logger.debug("Error, not in video library.")
				return
			data['dbid'] = int(xbmc.getInfoLabel('ListItem.DBID'))

		if media_type is None:
			logger.debug("Manual %s triggered on an unsupported content container." % args['action'])
		elif utils.isValidMediaType(media_type):
			data['media_type'] = media_type
			if 'dbid' in data:
				logger.debug("Manual %s of library '%s' with an ID of '%s'." % (args['action'], media_type, data['dbid']))
				if utils.isMovie(media_type):
					result = utils.getMovieDetailsFromKodi(data['dbid'], ['imdbnumber', 'title', 'year'])
					if not result:
						logger.debug("No data was returned from Kodi, aborting manual %s." % args['action'])
						return
					data['imdbnumber'] = result['imdbnumber']

				elif utils.isShow(media_type):
					result = utils.getShowDetailsFromKodi(data['dbid'], ['imdbnumber', 'tag'])
					if not result:
						logger.debug("No data was returned from Kodi, aborting manual %s." % args['action'])
						return
					data['imdbnumber'] = result['imdbnumber']
					data['tag'] = result['tag']

				elif utils.isEpisode(media_type):
					result = utils.getEpisodeDetailsFromKodi(data['dbid'], ['showtitle', 'season', 'episode', 'imdbnumber'])
					if not result:
						logger.debug("No data was returned from Kodi, aborting manual %s." % args['action'])
						return
					data['imdbnumber'] = result['imdbnumber']
					data['season'] = result['season']
					data['episode'] = result['episode']

			else:
				if 'season' in data:
					logger.debug("Manual %s of non-library '%s' S%02dE%02d, with an ID of '%s'." % (args['action'], media_type, data['season'], data['episode'], data['remoteid']))
					data['imdbnumber'] = data['remoteid']
				else:
					logger.debug("Manual %s of non-library '%s' with an ID of '%s'." % (args['action'], media_type, data['remoteid']))
					data['imdbnumber'] = data['remoteid']

			if args['action'] == 'rate' and 'rating' in args:
				if args['rating'] in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
					data['rating'] = int(args['rating'])

			data = {'action': 'manualRating', 'ratingData': data}

		else:
			logger.debug("Manual %s of '%s' is unsupported." % (args['action'], media_type))

	elif args['action'] == 'togglewatched':
		#todo fix this
		media_type = __getMediaType()
		if media_type in ['movie', 'show', 'season', 'episode']:
			data = {'media_type': media_type}
			if utils.isMovie(media_type):
				dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
				result = utils.getMovieDetailsFromKodi(dbid, ['imdbnumber', 'title', 'year', 'playcount'])
				if result:
					if result['playcount'] == 0:
						data['id'] = result['imdbnumber']
					else:
						logger.debug("Movie alread marked as watched in Kodi.")
				else:
					logger.debug("Error getting movie details from Kodi.")
					return

			elif utils.isEpisode(media_type):
				dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
				result = utils.getEpisodeDetailsFromKodi(dbid, ['showtitle', 'season', 'episode', 'tvshowid', 'playcount'])
				if result:
					if result['playcount'] == 0:
						data['id'] = result['tvdb_id']
						data['season'] = result['season']
						data['episode'] = result['episode']
					else:
						logger.debug("Episode already marked as watched in Kodi.")
				else:
					logger.debug("Error getting episode details from Kodi.")
					return

			elif utils.isSeason(media_type):
				showID = None
				showTitle = xbmc.getInfoLabel('ListItem.TVShowTitle')
				result = utils.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetTVShows', 'params': {'properties': ['title', 'imdbnumber', 'year']}, 'id': 0})
				if result and 'tvshows' in result:
					for show in result['tvshows']:
						if show['title'] == showTitle:
							showID = show['tvshowid']
							data['id'] = show['imdbnumber']
							break
				else:
					logger.debug("Error getting TV shows from Kodi.")
					return

				season = xbmc.getInfoLabel('ListItem.Season')
				if season == "":
					season = 0
				else:
					season = int(season)

				result = utils.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': showID, 'season': season, 'properties': ['season', 'episode', 'playcount']}, 'id': 0})
				if result and 'episodes' in result:
					episodes = []
					for episode in result['episodes']:
						if episode['playcount'] == 0:
							episodes.append(episode['episode'])
					
					if len(episodes) == 0:
						logger.debug("'%s - Season %d' is already marked as watched." % (showTitle, season))
						return

					data['season'] = season
					data['episodes'] = episodes
				else:
					logger.debug("Error getting episodes from '%s' for Season %d" % (showTitle, season))
					return

			elif utils.isShow(media_type):
				dbid = int(xbmc.getInfoLabel('ListItem.DBID'))
				result = utils.getShowDetailsFromKodi(dbid, ['year', 'imdbnumber'])
				if not result:
					logger.debug("Error getting show details from Kodi.")
					return
				showTitle = result['label']
				data['id'] = result['imdbnumber']
				result = utils.kodiJsonRequest({'jsonrpc': '2.0', 'method': 'VideoLibrary.GetEpisodes', 'params': {'tvshowid': dbid, 'properties': ['season', 'episode', 'playcount']}, 'id': 0})
				if result and 'episodes' in result:
					i = 0
					s = {}
					for e in result['episodes']:
						season = str(e['season'])
						if not season in s:
							s[season] = []
						if e['playcount'] == 0:
							s[season].append(e['episode'])
							i += 1

					if i == 0:
						logger.debug("'%s' is already marked as watched." % showTitle)
						return

					data['seasons'] = dict((k, v) for k, v in s.iteritems() if v)
				else:
					logger.debug("Error getting episode details for '%s' from Kodi." % showTitle)
					return

			if len(data) > 1:
				logger.debug("Marking '%s' with the following data '%s' as watched on trakt.tv" % (media_type, str(data)))
				data['action'] = 'markWatched'

		# execute toggle watched action
		xbmc.executebuiltin("Action(ToggleWatched)")

	q = sqliteQueue.SqliteQueue()
	if 'action' in data:
		logger.debug("Queuing for dispatch: %s" % data)
		q.append(data)

if __name__ == '__main__':
	Main()