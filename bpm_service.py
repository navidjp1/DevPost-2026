"""
BPM lookup using a local Spotify dataset.

Dataset: https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset
Contains ~114K tracks with BPM data.
"""

import os
import pandas as pd
import streamlit as st


# ── Load the CSV once and build a track_id -> tempo lookup ──────────────
@st.cache_data(show_spinner=False)
def _load_bpm_dataset() -> dict[str, int]:
    """
    Load the Hugging Face Spotify dataset CSV and return a dict
    mapping track_id -> BPM (int).
    """
    csv_path = os.path.join(os.path.dirname(__file__), "data", "spotify_tracks.csv")
    if not os.path.exists(csv_path):
        return {}

    df = pd.read_csv(csv_path, usecols=["track_id", "tempo"])
    df = df.dropna(subset=["track_id", "tempo"])
    # Build dict: track_id -> rounded BPM
    return {
        row["track_id"]: int(round(row["tempo"]))
        for _, row in df.iterrows()
    }


def enrich_tracks_with_bpm(
    tracks: list[dict],
    progress_callback=None,
) -> list[dict]:
    """
    Given a list of track dicts (with 'id', 'name', 'artist'), add a 'bpm'
    key to each using the local CSV dataset.

    Tracks not found in the dataset will have bpm=None and will be excluded
    from the workout playlist.

    progress_callback(current, total) is called so the UI can update a
    progress bar.
    """
    dataset = _load_bpm_dataset()
    total = len(tracks)

    for i, track in enumerate(tracks):
        bpm = dataset.get(track["id"])
        track["bpm"] = bpm if (bpm is not None and bpm > 0) else None

        if progress_callback:
            progress_callback(i + 1, total)

    return tracks
