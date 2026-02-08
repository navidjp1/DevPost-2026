"""
Spotify OAuth + playlist/track helpers for Streamlit.
"""

import os
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPES = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
])


def _get_auth_manager() -> SpotifyOAuth:
    """Return a SpotifyOAuth manager configured from env vars."""
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501"),
        scope=SCOPES,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler(
            token_info=st.session_state.get("token_info")
        ),
        show_dialog=True,
    )


def get_auth_url() -> str:
    """Return the Spotify authorization URL the user should visit."""
    auth_manager = _get_auth_manager()
    return auth_manager.get_authorize_url()


def handle_auth_callback() -> bool:
    """
    Check query params for a Spotify auth code, exchange it for a token,
    and store the token in session state.  Returns True if a valid token
    is now available.
    """
    # Already authenticated
    if st.session_state.get("token_info"):
        auth_manager = _get_auth_manager()
        # Refresh if expired
        token_info = auth_manager.validate_token(st.session_state["token_info"])
        if token_info:
            st.session_state["token_info"] = token_info
            return True

    # Check for auth code in URL
    params = st.query_params
    code = params.get("code")
    if code:
        auth_manager = _get_auth_manager()
        try:
            token_info = auth_manager.get_access_token(code, as_dict=True)
            st.session_state["token_info"] = token_info
            # Clear the code from the URL to avoid re-processing
            st.query_params.clear()
            return True
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            return False

    return False


def get_spotify_client() -> spotipy.Spotify | None:
    """Return an authenticated Spotify client, or None."""
    token_info = st.session_state.get("token_info")
    if not token_info:
        return None
    auth_manager = _get_auth_manager()
    return spotipy.Spotify(auth_manager=auth_manager)


def fetch_user_playlists(sp: spotipy.Spotify) -> list[dict]:
    """
    Return a list of the current user's playlists.
    Each dict has keys: id, name, image_url, track_count.
    """
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        for item in results["items"]:
            playlists.append({
                "id": item["id"],
                "name": item["name"],
                "image_url": item["images"][0]["url"] if item.get("images") else None,
                "track_count": item["tracks"]["total"],
            })
        if results["next"]:
            results = sp.next(results)
        else:
            break
    return playlists


def fetch_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[dict]:
    """
    Return all tracks from a playlist.
    Each dict has keys: id, uri, name, artist, duration_ms, album_art.
    """
    tracks = []
    results = sp.playlist_tracks(playlist_id, limit=100)
    while results:
        for item in results["items"]:
            track = item.get("track")
            if not track or not track.get("id"):
                continue  # skip local/unavailable tracks
            tracks.append({
                "id": track["id"],
                "uri": track["uri"],
                "name": track["name"],
                "artist": ", ".join(a["name"] for a in track["artists"]),
                "duration_ms": track["duration_ms"],
                "album_art": (
                    track["album"]["images"][-1]["url"]
                    if track.get("album", {}).get("images")
                    else None
                ),
            })
        if results["next"]:
            results = sp.next(results)
        else:
            break
    return tracks


def create_spotify_playlist(
    sp: spotipy.Spotify,
    name: str,
    track_uris: list[str],
    description: str = "",
) -> str:
    """
    Create a new playlist on the user's account and add tracks.
    Returns the playlist URL.
    """
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=description,
    )
    # Spotify API accepts max 100 tracks per request
    for i in range(0, len(track_uris), 100):
        sp.playlist_add_items(playlist["id"], track_uris[i : i + 100])
    return playlist["external_urls"]["spotify"]
