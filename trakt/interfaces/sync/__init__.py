from trakt.interfaces.base import Interface

# Import child interfaces
from trakt.interfaces.sync.collection import SyncCollectionInterface
from trakt.interfaces.sync.history import SyncHistoryInterface
from trakt.interfaces.sync.ratings import SyncRatingsInterface
from trakt.interfaces.sync.watched import SyncWatchedInterface
from trakt.interfaces.sync.watchlist import SyncWatchlistInterface

__all__ = [
    'SyncInterface',
    'SyncCollectionInterface',
    'SyncHistoryInterface',
    'SyncRatingsInterface',
    'SyncWatchedInterface',
    'SyncWatchlistInterface'
]


class SyncInterface(Interface):
    path = 'sync'

    def last_activities(self, **kwargs):
        return self.get_data(
            self.http.get('last_activities'),
            **kwargs
        )

    def playback(self, store=None, **kwargs):
        response = self.http.get('playback')

        items = self.get_data(response, **kwargs)

        if type(items) is not list:
            return None

        return self.media_mapper(
            store, items
        )
