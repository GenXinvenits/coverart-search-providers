# CoverArt Search Providers

CoverArt Search Providers is a Rhythmbox plugin that replaces the default CoverArt Search plugin with additional and updated providers for finding album artwork from local files, embedded metadata, and internet image sources.

This fork is maintained for **Rhythmbox 3.4.9** and is intended for modern manual, per-user installation.

## Compatibility

- **Rhythmbox 3.4.9**
- Rhythmbox 3.x with the APIs used by this fork may also work, but Rhythmbox 3.4.9 is the target version.
- This fork is **not intended for Rhythmbox 2.x**.

## Companion plugin

This plugin is the companion search-provider component for **CoverArt Browser**:

https://github.com/GenXinvenits/coverart-browser

If you use CoverArt Browser, install both plugins before activating them in Rhythmbox.

## Features

### Fixes for the default ArtSearch

1. Correctly find Jamendo local file names such as `$artist - $album` covers.
2. Include the Rhythmbox v2.98 MusicBrainz search patch.
3. Fix cover display for "Various Artists" from MusicBrainz.
4. Ignore downloaded files smaller than 100 bytes.

### Enhancements

1. Choose which providers to search with.
2. Choose the search provider order.
3. Stop searching after a provider finds a cover.
4. Find and extract embedded covers in MP3, M4A, FLAC and Ogg files.
5. Provide an API to embed cover art in MP3, M4A, FLAC and Ogg files.
6. Provide an external interface for finding covers for artists.

## Search providers

Recommended search order:

1. Embedded cover art
2. Cover art in the track folder
3. Local cache (`~/.cache/rhythmbox/covers`)
4. LastFM (rate limit: 5 requests/second; use the LastFM plugin to log in)
5. Spotify (rate limit: 2 requests/second)
6. Cover Art Internet Archive (rate limit: 1 request/second)
7. MusicBrainz (rate limit: 1 request/second)

## Manual installation

No installer script or Makefile is required.

Install the plugin into the Rhythmbox per-user plugin directory:

```bash
rm -rf ~/.local/share/rhythmbox/plugins/coverart-search-providers
git clone -b v3.4.9 https://github.com/GenXinvenits/coverart-search-providers.git ~/.local/share/rhythmbox/plugins/coverart-search-providers
```

Then restart Rhythmbox and enable **CoverArt Search Providers** from **Edit → Plugins**.

### CoverArt Browser installation

If you are using CoverArt Browser, install it alongside this plugin:

```bash
rm -rf ~/.local/share/rhythmbox/plugins/coverart-browser
git clone -b v3.4.9 https://github.com/GenXinvenits/coverart-browser.git ~/.local/share/rhythmbox/plugins/coverart-browser
```

## Dependencies

The plugin requires the Python packages needed by the enabled providers.

Embedded cover-art support uses **Mutagen** for reading and writing embedded artwork in supported audio formats.

## Translations

The `po/` directory contains the plugin's translation catalogs. These are part of the plugin's internationalization support and are kept in the repository.

The old translation installation helper scripts have been removed. `update_all_po.sh` is retained as a translation-development helper and is not required for normal plugin installation.

## LastFM API

LastFM API usage is subject to LastFM licensing. Do not copy `rb_lastfm.py` for your own purposes without obtaining your own API key.

## Development

The repository contains the translation source files and the development helper used to update translation catalogs. Normal users do not need the translation-development tools to install or use the plugin.

## Credits

Original CoverArt Search Providers project by **fossfreedom** and contributors.

The plugin incorporates work from the original Rhythmbox CoverArt Browser/Search Providers projects and other open-source projects.

## License

CoverArt Search Providers is released under the GPLv3+ license. See `LICENSE.txt` for details.
