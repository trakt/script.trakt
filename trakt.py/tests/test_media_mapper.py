from trakt.media_mapper import MediaMapper


def test_ids_empty():
    store = {}
    mapper = MediaMapper(store)

    item = {
        'ids': {}
    }

    assert mapper.process('shows', item) is None
