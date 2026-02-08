"""
BPM lookup via the GetSongBPM API.
https://getsongbpm.com/api
"""

import os
import re
import requests
import streamlit as st

API_BASE = "https://api.getsongbpm.com"


def _api_key() -> str:
    return os.getenv("GETSONGBPM_API_KEY", "")


def _clean(text: str) -> str:
    """Strip parenthetical info & special chars for cleaner search."""
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def lookup_bpm(song_name: str, artist_name: str) -> int | None:
    """
    Search GetSongBPM for a track and return its BPM (int), or None if
    not found.  Results are cached in session_state to avoid repeat calls.
    """
    # ---- check cache first ----
    if "bpm_cache" not in st.session_state:
        st.session_state["bpm_cache"] = {}

    cache_key = f"{song_name}|{artist_name}".lower()
    if cache_key in st.session_state["bpm_cache"]:
        return st.session_state["bpm_cache"][cache_key]

    # ---- call API ----
    query = f"{_clean(song_name)} {_clean(artist_name)}"
    try:
        resp = requests.get(
            f"{API_BASE}/search/",
            params={
                "api_key": _api_key(),
                "type": "both",
                "lookup": query,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # Network / rate-limit error – return None, don't cache
        return None

    # ---- parse response ----
    results = data.get("search", [])
    if not results:
        st.session_state["bpm_cache"][cache_key] = None
        return None

    # Take the first result's tempo
    tempo_raw = results[0].get("tempo")
    if tempo_raw is not None:
        try:
            bpm = int(round(float(tempo_raw)))
            st.session_state["bpm_cache"][cache_key] = bpm
            return bpm
        except (ValueError, TypeError):
            pass

    st.session_state["bpm_cache"][cache_key] = None
    return None


def enrich_tracks_with_bpm(
    tracks: list[dict],
    progress_callback=None,
) -> list[dict]:
    """
    Given a list of track dicts (with 'name' and 'artist'), add a 'bpm'
    key to each.  Tracks with no BPM found will have bpm=None.

    progress_callback(current, total) is called after each lookup so the
    UI can update a progress bar.
    """
    total = len(tracks)
    for i, track in enumerate(tracks):
        track["bpm"] = lookup_bpm(track["name"], track["artist"])
        if progress_callback:
            progress_callback(i + 1, total)
    return tracks
