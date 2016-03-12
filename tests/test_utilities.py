import json
import pytest
import utilities

def load_params_from_json(json_path):
    with open(json_path) as f:
        return json.load(f)

def test_isMovie():
    assert utilities.isMovie('movie')

def test_isEpisode():
    assert utilities.isEpisode('episode')

def test_isShow():
    assert utilities.isShow('show')

def test_isSeason():
    assert utilities.isSeason('season')

def test_isValidMediaType_Movie():
    assert utilities.isValidMediaType('movie')

def test_isValidMediaType_Episode():
    assert utilities.isValidMediaType('episode')

def test_isValidMediaType_Show():
    assert utilities.isValidMediaType('show')

def test_isValidMediaType_Season():
    assert utilities.isValidMediaType('season')

def test_chunks():
    movies = load_params_from_json('tests/fixtures/movies.json')
    assert len(utilities.chunks(movies, 1)) == 2

def test_getFormattedItemName_Show():
    data = load_params_from_json('tests/fixtures/show.json')
    assert utilities.getFormattedItemName('show', data) == b'Game of Thrones'

def test_getFormattedItemName_Season():
    data = load_params_from_json('tests/fixtures/season.json')
    assert utilities.getFormattedItemName('season', data) == b'Winter Is Coming - Season 1'

def test_getFormattedItemName_Episode():
    data = load_params_from_json('tests/fixtures/episode.json')
    assert utilities.getFormattedItemName('episode', data) == b'S01E01 - Winter Is Coming'

def test_getFormattedItemName_Movie():
    data = load_params_from_json('tests/fixtures/movie.json')
    assert utilities.getFormattedItemName('movie', data) == b'TRON: Legacy (2010)'

#Testing the tilte
def test_regex_tvshow_title_1():
    assert utilities.regex_tvshow('ShowTitle.S01E09')[0] == 'ShowTitle'
def test_regex_tvshow_title_2():
    assert utilities.regex_tvshow('ShowTitle.1x09')[0] == 'ShowTitle'
def test_regex_tvshow_title_3():
    assert utilities.regex_tvshow('ShowTitle.109')[0] == 'ShowTitle'
def test_regex_tvshow_title_4():
    assert utilities.regex_tvshow('ShowTitle.Season 01 - Episode 02')[0] == 'ShowTitle'
def test_regex_tvshow_title_5():
    assert utilities.regex_tvshow('ShowTitle_[s01]_[e01]')[0] == 'ShowTitle'
def test_regex_tvshow_title_6():
    assert utilities.regex_tvshow('ShowTitle - s01ep03')[0] == 'ShowTitle'

#Testing the season
def test_regex_tvshow_season_1():
    assert utilities.regex_tvshow('ShowTitle.S01E09')[1] == 1
def test_regex_tvshow_season_2():
    assert utilities.regex_tvshow('ShowTitle.1x09')[1] == 1
def test_regex_tvshow_season_3():
    assert utilities.regex_tvshow('ShowTitle.109')[1] == 1
def test_regex_tvshow_season_4():
    assert utilities.regex_tvshow('ShowTitle.Season 01 - Episode 02')[1] == 1
def test_regex_tvshow_season_5():
    assert utilities.regex_tvshow('ShowTitle_[s01]_[e01]')[1] == 1
def test_regex_tvshow_season_6():
    assert utilities.regex_tvshow('ShowTitle - s01ep03')[1] == 1

#Testing the episode
def test_regex_tvshow_episode_1():
    assert utilities.regex_tvshow('ShowTitle.S01E09')[2] == 9
def test_regex_tvshow_episode_2():
    assert utilities.regex_tvshow('ShowTitle.1x09')[2] == 9
def test_regex_tvshow_episode_3():
    assert utilities.regex_tvshow('ShowTitle.109')[2] == 9
def test_regex_tvshow_episode_4():
    assert utilities.regex_tvshow('ShowTitle.Season 01 - Episode 09')[2] == 9
def test_regex_tvshow_episode_5():
    assert utilities.regex_tvshow('ShowTitle_[s01]_[e09]')[2] == 9
def test_regex_tvshow_episode_6():
    assert utilities.regex_tvshow('ShowTitle - s01ep09')[2] == 9

def test_regex_year_title_1():
    assert utilities.regex_year('ShowTitle (2014)')[0] == 'ShowTitle'
def test_regex_year_title_2():
    assert utilities.regex_year('ShowTitle')[0] == ''
def test_regex_year_year_1():
    assert utilities.regex_year('ShowTitle (2014)')[1] == '2014'
def test_regex_year_year_2():
    assert utilities.regex_year('ShowTitle')[1] == ''

def test_parseIdToTraktIds_IMDB():
    assert utilities.parseIdToTraktIds('tt1431045', 'movie')[0] == {'imdb': 'tt1431045'}

def test_parseIdToTraktIds_TMDB():
    assert utilities.parseIdToTraktIds('20077', 'movie')[0] == {'tmdb': '20077'}

def test_parseIdToTraktIds_Tvdb():
    assert utilities.parseIdToTraktIds('4346770', 'show')[0] == {'tvdb': '4346770'}

def test_best_id_trakt():
    data = load_params_from_json('tests/fixtures/shows.json')
    assert utilities.best_id(data[1]['show']['ids']) == 1395
