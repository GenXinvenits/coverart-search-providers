# coverart-search-providers

Drop-in Rhythmbox replacement for the default CoverArt Search plugin, providing additional and updated cover-art search providers for local files and internet image hosts.

## Author

- fossfreedom <foss.freedom@gmail.com>

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

Recommended order:

- Embedded cover art
- Cover art in the track folder
- Local cache (`~/.cache/rhythmbox/covers`)
- LastFM (rate limit: 5 requests/second; use the LastFM plugin to log in)
- Spotify (rate limit: 2 requests/second)
- Cover Art Internet Archive (rate limit: 1 request/second)
- MusicBrainz (rate limit: 1 request/second)

## Manual installation

This repository does not contain an installation or uninstallation script. Install the plugin by placing the repository contents in the Rhythmbox user plugin directory:

```text
~/.local/share/rhythmbox/plugins/coverart_search_providers/
```

For Rhythmbox 3 and later, ensure the Rhythmbox 3 plugin descriptor is named:

```text
coverart_search_providers.plugin
```

After copying the files, enable the plugin from Rhythmbox's plugin preferences.

## Dependencies

The plugin requires the Python packages needed by the enabled providers. In particular, embedded cover-art support uses Mutagen.

## LastFM API

LastFM API usage is subject to LastFM licensing. Do not copy `rb_lastfm.py` for your own purposes without obtaining your own API key.

## License

GPL-3.0. See `LICENSE.txt`.
