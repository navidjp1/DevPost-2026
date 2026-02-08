"""
BPM lookup and discovery using a local Spotify dataset.

Dataset: https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset
Contains ~114K tracks with BPM data.
"""

import os

import pandas as pd
import streamlit as st


_CSV_COLUMNS = [
    "track_id", "track_name", "artists", "duration_ms",
    "tempo", "track_genre", "popularity",
]


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


@st.cache_data(show_spinner=False)
def _load_full_dataset() -> pd.DataFrame:
    """Load the full CSV with track metadata for discovery searches."""
    csv_path = os.path.join(os.path.dirname(__file__), "data", "spotify_tracks.csv")
    if not os.path.exists(csv_path):
        return pd.DataFrame()

    df = pd.read_csv(csv_path, usecols=_CSV_COLUMNS)
    df = df.dropna(subset=["track_id", "tempo"])
    df["tempo"] = df["tempo"].round().astype(int)
    return df


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


def search_tracks_by_bpm(
    min_bpm: int,
    max_bpm: int,
    genre: str | None = None,
    exclude_ids: set[str] | None = None,
    limit: int = 50,
    artist_hints: list[str] | None = None,
    diverse: bool = True,
) -> list[dict]:
    """
    Search the local CSV dataset for tracks within a BPM range.

    Parameters
    ----------
    min_bpm, max_bpm : int
        Inclusive BPM bounds.
    genre : str or None
        Optional genre filter (case-insensitive).
        Can be a comma-separated string of genres, e.g. "pop, hip-hop".
    exclude_ids : set[str] or None
        Track IDs to skip (e.g. already-selected familiar tracks).
    limit : int
        Max number of tracks to return.
    artist_hints : list[str] or None
        Optional artist names. Tracks by these artists are boosted
        (included first), but the pool is not limited to them.
    diverse : bool
        If True (default), mix popular and less-popular tracks so the
        pool varies across runs.  If False, return top-N by popularity.

    Returns
    -------
    list[dict]
        Each dict has: id, uri, name, artist, duration_ms, bpm, genre.
    """
    df = _load_full_dataset()
    if df.empty:
        return []

    # Filter by BPM range
    mask = (df["tempo"] >= min_bpm) & (df["tempo"] <= max_bpm)

    # Filter by genre(s) if provided
    if genre:
        genre_parts = [g.strip().lower() for g in genre.split(",") if g.strip()]
        if genre_parts:
            genre_mask = df["track_genre"].str.lower().isin(genre_parts)
            # If genre filter yields results, use it; otherwise skip
            if genre_mask.any():
                mask = mask & genre_mask

    df_filtered = df[mask].copy()

    # Exclude already-selected track IDs
    if exclude_ids:
        df_filtered = df_filtered[~df_filtered["track_id"].isin(exclude_ids)]

    if df_filtered.empty:
        return []

    # ── Artist-hint boosting ────────────────────────────────────────
    # Separate artist-matched rows so they get priority slots
    artist_rows = pd.DataFrame()
    if artist_hints:
        patterns = [ah.lower() for ah in artist_hints if ah]
        if patterns:
            artist_mask = df_filtered["artists"].str.lower().apply(
                lambda a: any(p in str(a) for p in patterns)
            )
            artist_rows = df_filtered[artist_mask]
            # Remove artist rows from general pool to avoid doubles
            df_filtered = df_filtered[~artist_mask]

    # ── Diversity sampling ──────────────────────────────────────────
    if diverse and len(df_filtered) > limit:
        # Split into popular half and less-popular half
        df_sorted = df_filtered.sort_values("popularity", ascending=False)
        mid = len(df_sorted) // 2
        top_half = df_sorted.iloc[:mid]
        bottom_half = df_sorted.iloc[mid:]

        # Take 60% from top, 40% from bottom (randomly sampled)
        n_top = int(limit * 0.6)
        n_bottom = limit - n_top
        top_sample = top_half.sample(n=min(n_top, len(top_half)), random_state=None)
        bottom_sample = bottom_half.sample(n=min(n_bottom, len(bottom_half)), random_state=None)
        df_filtered = pd.concat([top_sample, bottom_sample])
    else:
        df_filtered = df_filtered.sort_values("popularity", ascending=False).head(limit)

    # Combine: artist-matched first, then general pool
    if not artist_rows.empty:
        # Cap artist rows to ~30% of limit so they don't dominate
        artist_cap = max(3, int(limit * 0.3))
        artist_rows = artist_rows.sort_values("popularity", ascending=False).head(artist_cap)
        df_filtered = pd.concat([artist_rows, df_filtered]).head(limit)

    # Shuffle so the order isn't deterministic
    df_filtered = df_filtered.sample(frac=1, random_state=None)

    # Build result list
    results = []
    for _, row in df_filtered.iterrows():
        results.append({
            "id": row["track_id"],
            "uri": f"spotify:track:{row['track_id']}",
            "name": row["track_name"],
            "artist": row["artists"],
            "duration_ms": int(row["duration_ms"]) if pd.notna(row["duration_ms"]) else 210000,
            "bpm": int(row["tempo"]),
            "genre": row["track_genre"] if pd.notna(row["track_genre"]) else "",
            "source": "discovery",
        })

    return results
