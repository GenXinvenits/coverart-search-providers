# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
"""Performance wrapper for CoverArt search providers.

The original provider implementation lives in coverart_album_search_legacy.py.
This module keeps its public API while removing blocking rate-limit sleeps,
using an O(1) provider queue, and bounding Discogs worker concurrency.
"""

import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib
import coverart_album_search_legacy as _legacy


# Keep network work bounded. A library scan can otherwise create one worker
# thread per album and make Rhythmbox compete with dozens of network threads.
_DISCOGS_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix='coverart-discogs'
)


def _async_rate_limit(self, callback_func, args, per_second_rate):
    """Rate-limit without ever sleeping in Rhythmbox's main loop."""
    if per_second_rate <= 0:
        def invoke_immediate():
            callback_func(*args)
            return False
        return GLib.idle_add(invoke_immediate)

    interval = 1.0 / per_second_rate
    now = time.monotonic()
    next_time = getattr(self, '_opti_next_request_time', now)
    delay = max(0.0, next_time - now)
    self._opti_next_request_time = max(now, next_time) + interval
    self.current_time = time.time() + delay + interval

    def invoke():
        callback_func(*args)
        return False

    return GLib.timeout_add(max(0, int(delay * 1000)), invoke)


_legacy.BaseSearch.rate_limit = _async_rate_limit


def _cover_search_init(self, store, key, last_time, searches):
    self.store = store
    self.key = key.copy()
    self.last_time = last_time
    self.searches = deque(searches)


def _cover_search_next(self, continue_search):
    if not continue_search:
        return False

    if not self.searches:
        album = self.key.get_field('album')
        if not album:
            return False

        key = _legacy.RB.ExtDBKey.create_storage('album', album)
        key.add_field('artist', self.key.get_field('artist'))
        self.store.store(key, _legacy.RB.ExtDBSourceType.NONE, None)
        return False

    search = self.searches.popleft()
    search.search(
        self.key,
        self.last_time,
        self.store,
        self.search_done,
        None
    )
    return True


_legacy.CoverSearch.__init__ = _cover_search_init
_legacy.CoverSearch.next_search = _cover_search_next


def _discogs_search(self, key, last_time, store, callback, args):
    album = key.get_field('album')
    artists = key.get_field_values('artist')
    artists = [x for x in artists if x not in (None, '', 'Unknown')]
    if album in ('', 'Unknown'):
        album = None

    if album is None or not artists:
        callback(True)
        return

    searches = [[artist, album] for artist in artists]
    searches.append(['Various Artists', album])
    self.searches = searches
    self.callback = callback
    self.callback_args = args

    _DISCOGS_EXECUTOR.submit(
        self.get_release_cb,
        store,
        key,
        self.searches,
        args,
        callback
    )


_legacy.DiscogsSearch.search = _discogs_search


# Re-export the complete legacy public API.
for _name in dir(_legacy):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_legacy, _name)
