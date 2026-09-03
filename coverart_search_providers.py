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

# define plugin

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

        self._automatic_scan_model = None
        self._automatic_scan_row_id = 0
        self._automatic_scan_queue = []
        self._automatic_scan_seen = set()
        self._automatic_scan_active = False
        self._automatic_scan_idle_id = 0

    def do_activate(self):
        """
        Called by Rhythmbox when the plugin is activated. It creates the
        plugin's source and connects signals to manage the plugin's
        preferences.
        """

        cl = CoverLocale()
        cl.switch_locale(cl.Locale.LOCALE_DOMAIN)

        # define .plugin text strings used for translation
        plugin = _('CoverArt Browser Search Providers')
        desc = _('Additional coverart search providers for Rhythmbox')

        print("CoverArtBrowser DEBUG - do_activate")
        self.shell = self.object
        self.db = self.shell.props.db

        self.art_store = RB.ExtDB(name="album-art")
        self.req_id = self.art_store.connect("request", self.album_art_requested)

        self.artist_store = CoverArtExtDB(name="artist-art")
        self.artist_req_id = self.artist_store.connect("request", self.artist_art_requested)

        self.peas = Peas.Engine.get_default()

        self.csi_id = self.shell.connect("create_song_info", self.create_song_info)

        # Scan the library automatically.  The library query model is the
        # source of truth for library entries and is updated as new music is
        # added, so this handles both existing and newly imported albums.
        try:
            self._automatic_scan_model = self.shell.props.library_source.props.base_query_model
            self._automatic_scan_row_id = self._automatic_scan_model.connect(
                "row-inserted", self._automatic_scan_row_inserted)
            self._automatic_scan_idle_id = GLib.idle_add(
                self._automatic_scan_existing_entries)
            print("CoverArtBrowser DEBUG - automatic album-art scan enabled")
        except Exception as e:
            print("CoverArtBrowser DEBUG - unable to start automatic album-art scan: %s" % e)

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

        if self._automatic_scan_model is not None and self._automatic_scan_row_id:
            try:
                self._automatic_scan_model.disconnect(self._automatic_scan_row_id)
            except Exception:
                pass

        self._automatic_scan_model = None
        self._automatic_scan_row_id = 0
        self._automatic_scan_queue = []
        self._automatic_scan_seen.clear()
        self._automatic_scan_active = False

        self.shell.disconnect(self.csi_id)
        self.csi_id = 0
        del self.shell
        del self.db
        self.art_store.disconnect(self.req_id)
        self.artist_store.disconnect(self.artist_req_id)
        self.req_id = 0
        self.art_store = None
        self.artist_store = None
        self.peas = None

        print("CoverArtBrowser DEBUG - end do_deactivate")

    def create_song_info(self, shell, song_info, is_multiple):
        if is_multiple is False:
            # following only valid for rhythmbox 3.2
            try:
                import sys

                artsearch_dir = self.peas.get_plugin_info('artsearch').get_module_dir()
                sys.path.append(artsearch_dir)
                from songinfo import AlbumArtPage

                x = AlbumArtPage(shell, song_info)
            except:
                pass

    def _automatic_scan_key(self, entry):
        """Return the normal Rhythmbox album-art key for a song entry."""
        album = entry.get_string(RB.RhythmDBPropType.ALBUM)
        if not album or album == _("Unknown"):
            return None, None

        artist = entry.get_string(RB.RhythmDBPropType.ALBUM_ARTIST)
        if not artist or artist == _("Unknown"):
            artist = entry.get_string(RB.RhythmDBPropType.ARTIST)

        if not artist or artist == _("Unknown"):
            return None, None

        identity = (album, artist)

        # Use the entry type's ExtDB key builder when available.  Besides
        # producing the same album/artist storage key, this preserves
        # informational fields such as location and MusicBrainz IDs needed
        # by the embedded/local and Cover Art Archive providers.
        try:
            key = entry.get_entry_type().create_ext_db_key(
                entry, RB.RhythmDBPropType.ALBUM)
            if key is not None:
                return identity, key
        except Exception:
            pass

        # Fallback for entry types without create_ext_db_key.
        key = RB.ExtDBKey.create_storage("album", album)
        key.add_field("artist", artist)
        return identity, key

    def _automatic_scan_queue_entry(self, entry):
        """Queue an album if it is a song and has no cached album art."""
        try:
            song_type = self.db.entry_type_get_by_name("song")
            if entry.get_entry_type() != song_type:
                return

            identity, key = self._automatic_scan_key(entry)
            if identity is None or identity in self._automatic_scan_seen:
                return

            self._automatic_scan_seen.add(identity)

            try:
                if self.art_store.lookup(key):
                    return
            except Exception:
                pass

            self._automatic_scan_queue.append(key)
            self._automatic_scan_process()
        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic scan queue error: %s" % e)

    def _automatic_scan_existing_entries(self):
        self._automatic_scan_idle_id = 0

        if self._automatic_scan_model is None:
            return False

        try:
            for row in self._automatic_scan_model:
                self._automatic_scan_queue_entry(row[0])
        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic scan iteration error: %s" % e)

        self._automatic_scan_process()
        return False

    def _automatic_scan_row_inserted(self, model, path, treeiter):
        try:
            entry = model.get_value(treeiter, 0)
            self._automatic_scan_queue_entry(entry)
        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic scan row error: %s" % e)

    def _automatic_scan_process(self):
        """Request one album at a time to avoid flooding providers."""
        if self._automatic_scan_active or not self._automatic_scan_queue:
            return

        key = self._automatic_scan_queue.pop(0)
        self._automatic_scan_active = True

        try:
            print("CoverArtBrowser DEBUG - automatically searching for album: %s" %
                  key.get_field("album"))
            pending = self.art_store.request(
                key, self._automatic_scan_finished, None)

            # Cached results call the callback synchronously.  For an
            # asynchronous request the callback is invoked after the provider
            # stores the result.
            if not pending and self._automatic_scan_active:
                self._automatic_scan_finished(key, None, None, None)
        except Exception as e:
            print("CoverArtBrowser DEBUG - automatic scan request error: %s" % e)
            self._automatic_scan_active = False
            GLib.idle_add(self._automatic_scan_process)

    def _automatic_scan_finished(self, key, filename, data, user_data):
        self._automatic_scan_active = False
        GLib.idle_add(self._automatic_scan_process)
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
            # if provider == SearchPreferences.DISCOGS_SEARCH:
            #    searches.append(DiscogsSearch())
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
        # searches.append(DiscogsSearch())

        s = ArtistCoverSearch(store, key, last_time, searches)

        print("finished artist_art_requested")
        return s.next_search(True)
