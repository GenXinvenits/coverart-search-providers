# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
#
# Copyright (C) 2012 - fossfreedom
# Copyright (C) 2012 - Agustin Carrasco
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

import os
import os.path
import gettext

from gi.repository import RB

import rb3compat

gettext.install('rhythmbox', RB.locale_dir())

ART_FOLDER = os.path.join(RB.user_cache_dir(), 'covers')


class OldCacheSearch(object):
    """Search Rhythmbox's legacy on-disk artwork cache.

    Rhythmbox has historically used ~/.cache/rhythmbox/covers for artwork
    extracted from files and downloaded by older art-search implementations.
    The old implementation cached the directory-exists result at import time
    and only checked jpg/png.  That caused existing .jpeg artwork to be missed,
    which then sent every album through the more expensive providers.
    """

    EXTENSIONS = ('jpg', 'jpeg', 'png')

    def __init__(self):
        pass

    def filename(self, album, artist, extension):
        artist = artist.replace('/', '-')
        album = album.replace('/', '-')
        return os.path.join(ART_FOLDER, '%s - %s.%s' % (artist, album, extension))

    def _artist_candidates(self, key):
        candidates = []

        for field in ('artist', 'album-artist'):
            try:
                values = key.get_field_values(field) or []
            except Exception:
                values = []

            for value in values:
                if value and value not in candidates:
                    candidates.append(value)

        return candidates

    def search(self, key, last_time, store, callback, *args):
        print("OldCacheSearch")
        print(ART_FOLDER)

        # Do not cache whether the directory exists. Rhythmbox can create
        # the cache after this plugin has already been imported.
        if not os.path.isdir(ART_FOLDER):
            callback(True)
            return

        album = key.get_field("album")
        if not album:
            callback(True)
            return

        artists = self._artist_candidates(key)
        print("looking for %s by %s" % (album, str(artists)))

        for artist in artists:
            for ext in self.EXTENSIONS:
                path = self.filename(album, artist, ext)
                if os.path.isfile(path):
                    print("found legacy cache %s" % path)
                    uri = "file://" + rb3compat.pathname2url(path)

                    # Keep all known artist identities on the storage key.
                    # RB's album-art lookup can then match either track artist
                    # or album artist (important for compilations).
                    storekey = RB.ExtDBKey.create_storage('album', album)
                    for candidate in artists:
                        storekey.add_field("artist", candidate)

                    store.store_uri(storekey, RB.ExtDBSourceType.SEARCH, uri)
                    callback(False)
                    return

        callback(True)
