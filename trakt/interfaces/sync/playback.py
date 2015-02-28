from trakt.interfaces.sync.core.mixins import Get


class SyncPlaybackInterface(Get):
    path = 'sync/playback'
