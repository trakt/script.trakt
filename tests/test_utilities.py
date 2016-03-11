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
    assert utilities.getFormattedItemName('show', data) == 'Game of Thrones'

def test_getFormattedItemName_Season():
    data = load_params_from_json('tests/fixtures/season.json')
    assert utilities.getFormattedItemName('season', data) == 'Winter Is Coming - Season 1'

def test_getFormattedItemName_Episode():
    data = load_params_from_json('tests/fixtures/episode.json')
    assert utilities.getFormattedItemName('episode', data) == 'S01E01 - Winter Is Coming'

def test_getFormattedItemName_Movie():
    data = load_params_from_json('tests/fixtures/movie.json')
    assert utilities.getFormattedItemName('movie', data) == 'TRON: Legacy (2010)'

def test_parseIdToTraktIds_IMDB():
    assert utilities.parseIdToTraktIds('tt1431045', 'movie')[0] == {'imdb': 'tt1431045'}

def test_parseIdToTraktIds_TMDB():
    assert utilities.parseIdToTraktIds('20077', 'movie')[0] == {'tmdb': '20077'}

def test_parseIdToTraktIds_Tvdb():
    assert utilities.parseIdToTraktIds('4346770', 'show')[0] == {'tvdb': '4346770'}

def test_best_id_trakt():
    data = load_params_from_json('tests/fixtures/shows.json')
    assert utilities.best_id(data[1]['show']['ids']) == 1395
