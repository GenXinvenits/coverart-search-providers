# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
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

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import RB
from gi.repository import Peas

from coverart_search_providers_prefs import GSetting
from coverart_search_providers_prefs import CoverLocale
from coverart_album_search import CoverAlbumSearch
from coverart_album_search import CoverSearch
from coverart_album_search import CoverartArchiveSearch
from coverart_artist_search import ArtistCoverSearch
from coverart_artist_search import LastFMArtistSearch
from coverart_album_search import SpotifySearch
from coverart_artist_search import user_has_account
from coverart_extdb import CoverArtExtDB
from rb_oldcache import OldCacheSearch
from rb_local import LocalSearch
from rb_lastfm import LastFMSearch
from rb_musicbrainz import MusicBrainzSearch
from rb_embedded import EmbeddedSearch
from coverart_search_providers_prefs import SearchPreferences
import rb3compat


def lastfm_connected():
    """
    returns True/False if connected to lastfm
    """
    return user_has_account()


def get_search_providers():
    """
    returns an array of search providers
    """
    gs = GSetting()
    setting = gs.get_setting(gs.Path.PLUGIN)
    current_providers = setting[gs.PluginKey.PROVIDERS]

    return current_providers.split(',')


class CoverArtAlbumSearchPlugin(GObject.Object, Peas.Activatable):
    """
    Main class of the plugin. Manages the activation and deactivation of the
    plugin.
    """
    __gtype_name = 'CoverArtAlbumSearchPlugin'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        """
        Initialises the plugin object.
        """
        GObject.Object.__init__(self)
        if not rb3compat.compare_pygobject_version('3.9'):
            GObject.threads_init()

        self._automatic_scan_idle_id = 0
        self._automatic_scan_model = None
        self._automatic_refresh_idle_id = 0
        self._automatic_refresh_keys = []
        self._automatic_scan_requested = set()

    def do_activate(self):
        """
        Called by Rhythmbox when the plugin is activated. It creates the
        plugin's source and connects signals to manage the plugin's
        preferences.
        """

        cl = CoverLocale()
        cl.switch_locale(cl.Locale.LOCALE_DOMAIN)

        plugin = _('CoverArt Browser Search Providers')
        desc = _('Additional coverart search providers for Rhythmbox')

        print("CoverArtBrowser DEBUG - do_activate")
        self.shell = self.object
        self.db = self.shell.props.db

        self.art_store = RB.ExtDB(name="album-art")
        self.req_id = self.art_store.connect("request", self.album_art_requested)
        self.art_added_id = self.art_store.connect("added", self.album_art_added)

        self.artist_store = CoverArtExtDB(name="artist-art")
        self.artist_req_id = self.artist_store.connect("request", self.artist_art_requested)

        self.peas = Peas.Engine.get_default()
        self.csi_id = self.shell.connect("create_song_info", self.create_song_info)

        # Do not scan while Rhythmbox is still constructing the library model.
        # Starting requests from row-inserted can re-enter the database/model
        # update path and can crash Rhythmbox. Instead, wait until the main
        # loop is idle and perform a single safe pass over the completed model.
        self._automatic_scan_idle_id = GLib.idle_add(
            self._automatic_scan_start)

        print("CoverArtBrowser DEBUG - automatic album-art scan scheduled")
        print("CoverArtBrowser DEBUG - end do_activate")

    def do_deactivate(self):
        """
        Called by Rhythmbox when the plugin is deactivated. It makes sure to
        free all the resources used by the plugin.
        """
        print("CoverArtBrowser DEBUG - do_deactivate")

        if self._automatic_scan_idle_id:
            try:
                GLib.source_remove(self._automatic_scan_idle_id)
            except Exception:
                pass
            self._automatic_scan_idle_id = 0

        if self._automatic_refresh_idle_id:
            try:
                GLib.source_remove(self._automatic_refresh_idle_id)
            except Exception:
                pass
            self._automatic_refresh_idle_id = 0

        self._automatic_refresh_keys = []
        self._automatic_scan_requested.clear()
        self._automatic_scan_model = None

        self.shell.disconnect(self.csi_id)
        self.csi_id = 0
        del self.shell
        del self.db
        self.art_store.disconnect(self.req_id)
        self.art_store.disconnect(self.art_added_id)
        self.artist_store.disconnect(self.artist_req_id)
        self.req_id = 0
        self.art_added_id = 0
        self.artist_store = None
        self.art_store = None
        self.peas = None

        print("CoverArtBrowser DEBUG - end do_deactivate")

    def create_song_info(self, shell, song_info, is_multiple):
        if is_multiple is False:
            try:
                import sys

                artsearch_dir = self.peas.get_plugin_info('artsearch').get_module_dir()
                sys.path.append(artsearch_dir)
                from songinfo import AlbumArtPage

                x = AlbumArtPage(shell, song_info)
            except:
                pass

    def album_art_added(self, store, key, path, pixbuf):
        """Refresh the CoverArt Browser after automatic artwork is stored.

        The search-provider ExtDB instance can receive the ``added`` signal
        without the CoverArt Browser's own ExtDB instance receiving it.
        Queue the key and refresh the corresponding Album object from the
        CoverArt Browser on the next main-loop iteration. This avoids touching
        the GTK model while ExtDB is emitting its signal.
        """
        try:
            self._automatic_refresh_keys.append(key.copy())
        except Exception:
            self._automatic_refresh_keys.append(key)

        if not self._automatic_refresh_idle_id:
            self._automatic_refresh_idle_id = GLib.idle_add(
                self._automatic_refresh_album_art)

    def _automatic_refresh_album_art(self):
        """Apply newly downloaded artwork to visible CoverArt albums."""
        self._automatic_refresh_idle_id = 0

        keys = self._automatic_refresh_keys
        self._automatic_refresh_keys = []

        try:
            page = self.shell.props.selected_page
            manager = getattr(page, 'album_manager', None)

            if manager is None:
                return False

            for key in keys:
                try:
                    album = manager.model.get_from_ext_db_key(key)
                    if album is not None:
                        manager.cover_man.load_cover(album)
                        print("CoverArtBrowser DEBUG - refreshed album art: %s" % album)
                except Exception as e:
                    print("CoverArtBrowser DEBUG - automatic album-art refresh error: %s" % e)

        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic album-art refresh failed: %s" % e)

        return False

    def _get_coverart_manager(self):
        """Return CoverArt Browser's album manager when its source is ready.

        CoverArt Browser creates its AlbumManager when its source is first
        selected. Use Rhythmbox's public entry-type-to-source lookup rather
        than walking the display-page tree, which is not a stable API.
        """
        try:
            entry_type = self.db.entry_type_get_by_name('CoverArtBrowserEntryType')
            if entry_type is None:
                return None

            source = self.shell.get_source_by_entry_type(entry_type)
            if source is None:
                return None

            return getattr(source, 'album_manager', None)
        except Exception as e:
            print("CoverArtBrowser DEBUG - unable to access browser manager: %s" % e)
            return None

    def _automatic_scan_start(self):
        """Scan once and request artwork only for albums without cached art."""
        self._automatic_scan_idle_id = 0

        try:
            self._automatic_scan_model = self.shell.props.library_source.props.base_query_model
            if self._automatic_scan_model is None:
                print("CoverArtBrowser DEBUG - library model unavailable")
                return False

            manager = self._get_coverart_manager()

            seen = set()
            count = 0
            skipped = 0

            # Each album is considered once per scan, regardless of how many
            # tracks it contains. ExtDB is checked before requesting it.
            for row in self._automatic_scan_model:
                entry = row[0]

                try:
                    if entry.get_entry_type() != self.db.entry_type_get_by_name("song"):
                        continue

                    album = entry.get_string(RB.RhythmDBPropType.ALBUM)
                    if not album:
                        continue

                    artist = entry.get_string(RB.RhythmDBPropType.ALBUM_ARTIST)
                    if not artist:
                        artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
                    if not artist:
                        continue

                    identity = (album, artist)
                    if identity in seen:
                        continue
                    seen.add(identity)

                    try:
                        key = entry.get_entry_type().create_ext_db_key(
                            entry, RB.RhythmDBPropType.ALBUM)
                    except Exception:
                        key = None

                    if key is None:
                        continue

                    key_identity = (album, artist)
                    if key_identity in self._automatic_scan_requested:
                        skipped += 1
                        continue

                    # If CoverArt Browser is already initialized, trust its
                    # actual Album object. Its unknown_cover is the placeholder
                    # used when no artwork is available, so an album whose
                    # cover differs from that placeholder already has art
                    # displayed by the browser and must not be searched again.
                    if manager is not None:
                        try:
                            album_obj = manager.model.get(album, artist)
                            if album_obj is not None and \
                                    album_obj.cover is not manager.cover_man.unknown_cover:
                                skipped += 1
                                continue
                        except Exception as e:
                            print("CoverArtBrowser DEBUG - browser cover check failed for %s: %s" %
                                  (album, e))

                    # lookup() returns the stored artwork location when real
                    # artwork exists. Do not request an album that already
                    # has artwork in the album-art ExtDB.
                    art_location = self.art_store.lookup(key)
                    if art_location:
                        skipped += 1
                        continue

                    self._automatic_scan_requested.add(key_identity)
                    self.art_store.request(key, None, None)
                    count += 1

                except Exception as e:
                    print("CoverArtBrowser DEBUG - automatic scan entry error: %s" % e)

            print("CoverArtBrowser DEBUG - automatic album-art scan requested %d missing albums, skipped %d" %
                  (count, skipped))

        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic album-art scan failed: %s" % e)

        return False

    def album_art_requested(self, store, key, last_time):
        searches = []

        current_list = get_search_providers()

        for provider in current_list:
            if provider == SearchPreferences.EMBEDDED_SEARCH:
                searches.append(EmbeddedSearch())
                searches.append(CoverAlbumSearch())
            if provider == SearchPreferences.LOCAL_SEARCH:
                searches.append(LocalSearch())
            if provider == SearchPreferences.CACHE_SEARCH:
                searches.append(OldCacheSearch())
            if provider == SearchPreferences.LASTFM_SEARCH:
                searches.append(LastFMSearch())
            if provider == SearchPreferences.MUSICBRAINZ_SEARCH:
                searches.append(MusicBrainzSearch())
            if provider == SearchPreferences.SPOTIFY_SEARCH:
                searches.append(SpotifySearch())
            if provider == SearchPreferences.COVERARTARCHIVE_SEARCH:
                searches.append(CoverartArchiveSearch())

        s = CoverSearch(store, key, last_time, searches)

        return s.next_search(True)

    def artist_art_requested(self, store, key, last_time):
        print("artist_art_requested")

        print(store)
        print(key)
        print(last_time)

        searches = []
        searches.append(LastFMArtistSearch())
        s = ArtistCoverSearch(store, key, last_time, searches)

        print("finished artist_art_requested")
        return s.next_search(True)
