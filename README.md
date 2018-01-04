# Scoutlist

Scoutlist is a Spotify playlist track aggregator for efficient music discovery. Scoutlist helps DJs or other music enthusiasts searching for new music that are tired of switching between playlists and skipping songs they've already heard. Scoutlist aggregates tracks from a list of user-specified source playlists into a single generated playlist. The generated playlist is free of duplicate tracks and excluded tracks from other user-specified already-listened-to playlists.

Scoutlist is written in Python 3 and uses the Spotify API via the Spotipy library. It currently uses a jupyter notebook at the primary user interface.

## Dependencies
* python 3
* spotipy
* jupyter

## Notes

To run the app, you will need to populate the app_credentials.json file or copy an existing one. For more information on how to do that visit: <http://spotipy.readthedocs.io/en/latest/#authorized-requests>