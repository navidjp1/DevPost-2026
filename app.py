"""
BPM Workout Playlist Generator – Streamlit MVP
"""

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from spotify_utils import (
    get_auth_url,
    handle_auth_callback,
    get_spotify_client,
    fetch_user_playlists,
    fetch_playlist_tracks,
    create_spotify_playlist,
)
from bpm_service import enrich_tracks_with_bpm
from workout_playlist import build_workout_playlist, playlist_stats

# ─── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BPM Workout Playlist",
    page_icon="🏃",
    layout="centered",
)

# ─── Custom CSS for a cleaner look ──────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { max-width: 720px; }
    .track-row {
        display: flex; align-items: center; gap: 12px;
        padding: 6px 0; border-bottom: 1px solid #333;
    }
    .track-row img { border-radius: 4px; }
    .phase-tag {
        font-size: 0.7rem; font-weight: 700; padding: 2px 8px;
        border-radius: 10px; color: #fff; display: inline-block;
    }
    .warmup  { background: #f59e0b; }
    .peak    { background: #ef4444; }
    .cooldown { background: #3b82f6; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Helpers ────────────────────────────────────────────────────────────
def _ms_to_min_sec(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _phase_label(idx: int, warmup_count: int, peak_count: int) -> str:
    if idx < warmup_count:
        return '<span class="phase-tag warmup">WARMUP</span>'
    elif idx < warmup_count + peak_count:
        return '<span class="phase-tag peak">PEAK</span>'
    else:
        return '<span class="phase-tag cooldown">COOLDOWN</span>'


# ─── Auth handling ──────────────────────────────────────────────────────
is_authed = handle_auth_callback()

# =====================================================================
# SCREEN 1 – Login
# =====================================================================
if not is_authed:
    st.title("🏃 BPM Workout Playlist")
    st.subheader("Run to the beat.")
    st.write(
        "Generate a playlist that matches your workout intensity — "
        "songs ramp up from a chill warmup to peak energy, then bring "
        "you back down for a cool-off."
    )
    auth_url = get_auth_url()
    st.link_button("🔗 Login with Spotify", auth_url, use_container_width=True)
    st.stop()

# From here on the user is authenticated
sp = get_spotify_client()
if sp is None:
    st.error("Could not create Spotify client. Please log in again.")
    if st.button("Reset session"):
        st.session_state.clear()
        st.rerun()
    st.stop()

# Fetch user info for greeting
try:
    user_info = sp.current_user()
    display_name = user_info.get("display_name", "Runner")
except Exception:
    display_name = "Runner"

st.title("🏃 BPM Workout Playlist")
st.caption(f"Logged in as **{display_name}**")

# Logout button in sidebar
with st.sidebar:
    st.header("Account")
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# =====================================================================
# SCREEN 2 – Playlist selection + workout config
# =====================================================================
st.header("1. Pick your source playlists")
st.write("Select playlists you'd like us to pull songs from:")

if "user_playlists" not in st.session_state:
    with st.spinner("Loading your playlists..."):
        st.session_state["user_playlists"] = fetch_user_playlists(sp)

playlists = st.session_state["user_playlists"]

if not playlists:
    st.warning("You don't have any playlists on Spotify!")
    st.stop()

selected_ids: list[str] = []
cols_per_row = 2
for i in range(0, len(playlists), cols_per_row):
    cols = st.columns(cols_per_row)
    for j, col in enumerate(cols):
        idx = i + j
        if idx >= len(playlists):
            break
        pl = playlists[idx]
        with col:
            checked = st.checkbox(
                f"**{pl['name']}** ({pl['track_count']} tracks)",
                key=f"pl_{pl['id']}",
            )
            if checked:
                selected_ids.append(pl["id"])

st.divider()

# =====================================================================
# SCREEN 3 – Workout config
# =====================================================================
st.header("2. Configure your workout")
workout_minutes = st.slider(
    "Workout duration (minutes)",
    min_value=15,
    max_value=120,
    value=45,
    step=5,
)

st.divider()

# =====================================================================
# Generate
# =====================================================================
generate = st.button(
    "🎵 Generate Workout Playlist",
    use_container_width=True,
    disabled=len(selected_ids) == 0,
)

if len(selected_ids) == 0:
    st.info("Select at least one playlist above to get started.")

if generate:
    # -- Gather tracks from selected playlists --
    all_tracks: list[dict] = []
    with st.status("Fetching tracks from selected playlists...", expanded=True) as status:
        for pid in selected_ids:
            name = next((p["name"] for p in playlists if p["id"] == pid), pid)
            st.write(f"📂 {name}")
            tracks = fetch_playlist_tracks(sp, pid)
            all_tracks.extend(tracks)
        status.update(label=f"Fetched {len(all_tracks)} tracks", state="complete")

    if not all_tracks:
        st.error("No tracks found in the selected playlists.")
        st.stop()

    # -- Look up BPMs --
    with st.status("Looking up BPM data...", expanded=True) as status:
        progress_bar = st.progress(0, text="0%")

        def _update_progress(current: int, total: int):
            pct = current / total
            progress_bar.progress(pct, text=f"{current}/{total} tracks")

        all_tracks = enrich_tracks_with_bpm(all_tracks, progress_callback=_update_progress)
        found = sum(1 for t in all_tracks if t.get("bpm") is not None)
        status.update(
            label=f"BPM found for {found}/{len(all_tracks)} tracks",
            state="complete",
        )

    # -- Build the playlist --
    playlist = build_workout_playlist(all_tracks, workout_minutes)

    if not playlist:
        st.error(
            "Could not build a playlist — no tracks with BPM data. "
            "Try selecting playlists with more popular / well-known songs."
        )
        st.stop()

    # Store in session state for the save button
    st.session_state["generated_playlist"] = playlist

    # =====================================================================
    # SCREEN 4 – Results
    # =====================================================================
    stats = playlist_stats(playlist)

    st.success("Your workout playlist is ready!")

    # -- Stats row --
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracks", stats["total_tracks"])
    c2.metric("Duration", f"{stats['total_duration_min']} min")
    c3.metric("BPM Range", f"{stats['min_bpm']}–{stats['max_bpm']}")
    c4.metric("Avg BPM", stats["avg_bpm"])

    # -- BPM curve chart --
    st.subheader("BPM Curve")
    bpm_data = [{"Track #": i + 1, "BPM": t["bpm"]} for i, t in enumerate(playlist)]
    st.area_chart(
        bpm_data,
        x="Track #",
        y="BPM",
        color="#ef4444",
    )

    # -- Figure out phase boundaries for labels --
    from workout_playlist import WARMUP_FRAC, PEAK_FRAC
    total_ms = workout_minutes * 60 * 1000
    warmup_target = total_ms * WARMUP_FRAC
    peak_target = total_ms * PEAK_FRAC

    cum_ms = 0
    warmup_count = 0
    for t in playlist:
        cum_ms += t["duration_ms"]
        if cum_ms <= warmup_target:
            warmup_count += 1
        else:
            break

    cum_ms = 0
    peak_count = 0
    for t in playlist[warmup_count:]:
        cum_ms += t["duration_ms"]
        if cum_ms <= peak_target:
            peak_count += 1
        else:
            break

    # -- Track list --
    st.subheader("Tracklist")
    for i, track in enumerate(playlist):
        phase = _phase_label(i, warmup_count, peak_count)
        art = track.get("album_art") or ""
        img_html = f'<img src="{art}" width="40" height="40"/>' if art else ""
        st.markdown(
            f"""
            <div class="track-row">
                {img_html}
                <div style="flex:1">
                    <strong>{track['name']}</strong><br>
                    <span style="opacity:0.7">{track['artist']}</span>
                </div>
                <div style="text-align:right; min-width:70px">
                    {track['bpm']} BPM<br>
                    <span style="opacity:0.6">{_ms_to_min_sec(track['duration_ms'])}</span>
                </div>
                <div style="min-width:80px; text-align:right">{phase}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # -- Save to Spotify --
    st.subheader("Save to Spotify")
    playlist_name = st.text_input(
        "Playlist name",
        value=f"Workout {workout_minutes}min – {date.today().strftime('%b %d')}",
    )
    if st.button("💾 Save to my Spotify", use_container_width=True):
        with st.spinner("Creating playlist..."):
            track_uris = [t["uri"] for t in playlist]
            url = create_spotify_playlist(
                sp,
                name=playlist_name,
                track_uris=track_uris,
                description=f"BPM-curved workout playlist ({workout_minutes} min)",
            )
        st.success(f"Playlist created! [Open in Spotify]({url})")
        st.balloons()
