
"""Scoutlist: Spotify Playlist Aggregator

Features:
* Gets unique tracks (no duplicates) across multiple playlists
* Exclude tracks from specified playlists
* Gets most recently added tracks

Author:
    jykong - James Kong

Created:
    January 4, 2018
"""
import datetime
import json
import os
from collections import namedtuple

import dateutil.parser
import spotipy
import spotipy.util


def authenticate(username, app_credentials_fp='app_credentials.json') \
    -> spotipy.client.Spotify:
    """User authentication via Spotify API

    To find your Spotify username manually, go to profile -> share -> copy URL.
    All the characters after the last slash (/) are the username.

    Args:
        username (str): Spotify username.
        app_credentials_fp (str, optional): Filepath to app credentials.
            Expects json.

    Returns:
        spotipy.client.Spotify: Spotify API session object. For more info read:
            https://spotipy.readthedocs.io/en/latest/#spotipy.client.Spotify
    """

    with open(app_credentials_fp) as app_cred_f:
        cred = json.load(app_cred_f)
        os.environ["SPOTIPY_CLIENT_ID"] = cred['client_id']
        os.environ["SPOTIPY_CLIENT_SECRET"] = cred['client_secret']
        os.environ["SPOTIPY_REDIRECT_URI"] = cred['redirect_uri']

    scope = 'playlist-read-private playlist-modify-private playlist-modify-public'

    token = spotipy.util.prompt_for_user_token(username, scope)

    if not token:
        print("Can't get token for ", username)
        return

    print("Authenticated " + username)

    return spotipy.Spotify(auth=token)

Playlist = namedtuple('Playlist', ['track_name', 'owner_id', 'playlist_id'])

def inspect_playlists(sp_sess):
    """Print user's playlists.

    Print output is conveniently formatted as line elements for a list of
    Playlist objects. Copy paste lines from the output to create
    source_playlist and exclude_playlist.

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
    """

    limit = 50
    offset = 0
    while True:
        results = sp_sess.current_user_playlists(limit=limit, offset=offset)
        for item in results['items']:
            print('Playlist(\"{:30s}\", {!r}, {!r}),'.format(item['name'], item['owner']['id'], item['id']))
        total = results['total']
        offset += limit
        if offset > total:
            print(str(total) + ' playlists')
            break

class Track():
    """Hashable class with track data derived from json item data.

    Uses track_name and artist_ids for __key(), __eq__(), and __hash__(),
    instead of track_id because they are more useful unique track identifiers.
    Spotify has many identical tracks by the same artist with different
    track_ids.

    Attributes:
        track_id (str): Track id
        track_name (str): Track name
        artist_ids (frozenset): Frozenset of artist ids
    """

    def __init__(self, item):
        self.track_id = item['track']['id']
        self.track_name = item['track']['name']
        self.artist_ids = frozenset(a['id'] for a in item['track']['artists'])
    def __key(self):
        return (self.track_name, self.artist_ids)
    def __eq__(self, other):
        return self.track_name == other.track_name and \
            self.artist_ids == other.artist_ids
    def __hash__(self):
        return hash(self.__key())

class TrackAddedAt(Track):
    """Sortable extension of Track() class with added_at data.

    Attributes:
        added_at (Datetime): Datetime describing when the track was added to
            the source playlist.
    """

    def __init__(self, item):
        Track.__init__(self, item)
        self.added_at = dateutil.parser.parse(item['added_at'])
    def __lt__(self, other):
        return self.added_at < other.added_at

def tracks_iterator(sp_sess, playlist, added_at):
    """Generator that iteratively yields tracks from the specified playlist.

    Internally handles fetching json items from sp_sess object.

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
        playlist (Playlist): Playlist object.
        added_at (bool): Specifies whether or not to fetch & use added_at data.

    Yields either a Track() or TrackAddedAt() object depending on added_at arg.
    """

    limit = 100
    offset = 0
    fields = "items.track.id, items.track.name, items.track.artists.id, total"
    if added_at is True:
        fields += ", items.added_at"
    while True:
        results = sp_sess.user_playlist_tracks(
            user=playlist.owner_id,
            playlist_id=playlist.playlist_id,
            fields=fields,
            limit=limit,
            offset=offset)

        if added_at is True:
            for item in results['items']:
                track = TrackAddedAt(item)
                if track.track_id is not None:
                    yield track
        else:
            for item in results['items']:
                track = Track(item)
                if track.track_id is not None:
                    yield track

        offset += limit
        if offset > results['total']:
            break

def aggregate_excluded_tracks(sp_sess, exclude_playlists) -> set:
    """Aggregate excluded tracks across user-specified playlists.

    Returned excluded_tracks for use by aggregate_source_tracks().

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
        exclude_playlists (list): List of Playlist objects.

    Returns:
        set: Set of Track() objects.
    """

    excluded_tracks = set()
    for playlist in exclude_playlists:
        for track in tracks_iterator(sp_sess, playlist, added_at=False):
            excluded_tracks.add(track)

    print("Excluded tracks size: " + str(len(excluded_tracks)))
    return excluded_tracks

def aggregate_source_tracks(sp_sess, source_playlists, excluded_tracks, output_len) -> list:
    """Aggregates source tracks across user-specified playlists.

    Excludes tracks from excluded_tracks. Limits output list length to output_len.
    Includes and sorts tracks by most recent added_at datetime.

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
        source_playlists (list): List of Playlist objects.
        excluded_tracks (set): Set of Track() objects.
        output_len (int): Length of output list.

    Return:
        list: List of track ids.
    """

    included_tracks = []

    for playlist in source_playlists:
        for track in tracks_iterator(sp_sess, playlist, added_at=True):
            if len(included_tracks) >= output_len and \
               track.added_at <= included_tracks[-1].added_at:
                continue

            if track in excluded_tracks:
                continue

            excluded_tracks.add(track)

            included_tracks.append(track)
            included_tracks = sorted(included_tracks, reverse=True)
            if len(included_tracks) > output_len:
                included_tracks.pop()

    return [track.track_id for track in included_tracks]

def create_scoutlist(sp_sess, username) -> str:
    """Create a scoutlist playlist in the user's account.

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
        username (str): Spotify username.

    Returns:
        str: Playlist id.
    """

    now = datetime.datetime.now()
    pl_name = "scout_%04d%02d%02d_%02d%02d%02d" \
            % (now.year, now.month, now.day, now.hour, now.minute, now.second)
    result = sp_sess.user_playlist_create(user=username, name=pl_name, public=False)
    print("Created playlist " + pl_name)
    return result['id']

def add_playlist_tracks(sp_sess, username, playlist_id, tracks):
    """Added tracks to a user's playlist.

    Args:
        sp_sess (spotipy.client.Spotify): Spotify API session object.
        username (str): Spotify username.
        playlist_id (str): Playlist id.
        tracks (list): List of track ids.
    """

    offset = 0
    while offset < len(tracks):
        sp_sess.user_playlist_add_tracks(
            user=username,
            playlist_id=playlist_id,
            tracks=tracks[offset:offset+100],
            position=offset)
        offset += 100
    print(str(len(tracks)) + " tracks added")
