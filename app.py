"""
BPM Workout Playlist Generator – Streamlit MVP
with AI Running Coach (K2-Think) & Music Curator (Dedalus Labs)
"""

import html
import json
import os
from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

# #region agent log
DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), ".cursor", "debug.log")
def _debug_log(message: str, data: dict, hypothesis_id: str = ""):
    try:
        payload = {"location": "app.py", "message": message, "data": data, "hypothesisId": hypothesis_id, "timestamp": __import__("time").time() * 1000}
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion
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
from workout_playlist import playlist_stats
from agents.workout_designer import design_workout
from agents.music_curator import curate_playlist, generate_health_insights
from route_service import (
    get_running_route,
    bpm_to_pace_min_per_km,
    format_pace,
    parse_coords,
)

# ─── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BeatMatch",
    page_icon="🏃",
    layout="centered",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { max-width: 760px; }
    .track-row {
        display: flex; align-items: center; gap: 12px;
        padding: 6px 0; border-bottom: 1px solid #333;
    }
    .track-row img { border-radius: 4px; }
    .phase-tag {
        font-size: 0.7rem; font-weight: 700; padding: 2px 8px;
        border-radius: 10px; color: #fff; display: inline-block;
    }
    .warmup   { background: #f59e0b; }
    .peak     { background: #ef4444; }
    .cooldown { background: #3b82f6; }
    .source-tag {
        font-size: 0.65rem; font-weight: 600; padding: 2px 6px;
        border-radius: 8px; display: inline-block; margin-left: 4px;
    }
    .familiar  { background: #22c55e; color: #fff; }
    .discovery { background: #a855f7; color: #fff; }
    .coach-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155; border-radius: 12px;
        padding: 20px; margin: 12px 0;
    }
    .insight-section {
        background: #0f172a; border: 1px solid #1e293b;
        border-radius: 10px; padding: 16px; margin: 8px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Helpers ────────────────────────────────────────────────────────────
def _ms_to_min_sec(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _phase_tag(phase: str) -> str:
    """Return an HTML phase tag based on the track's phase."""
    label = phase.upper() if phase else "—"
    css_class = phase if phase in ("warmup", "peak", "cooldown") else ""
    return f'<span class="phase-tag {css_class}">{label}</span>'


def _source_tag(source: str) -> str:
    """Return an HTML source tag (familiar / discovery)."""
    if source == "discovery":
        return '<span class="source-tag discovery">NEW</span>'
    return '<span class="source-tag familiar">YOURS</span>'


# ─── Auth handling ──────────────────────────────────────────────────────
is_authed = handle_auth_callback()

# =====================================================================
# SCREEN 1 – Login
# =====================================================================
if not is_authed:
    st.title("BeatMatch")
    st.subheader("Run to the beat.")
    st.write(
        "Generate a personalised playlist that matches your workout "
        "intensity — songs ramp up from a chill warmup to peak energy, "
        "then bring you back down for a cool-off."
    )
    st.caption("Powered by K2-Think & Dedalus Labs")
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

st.title("BeatMatch")
st.caption(f"Logged in as **{display_name}**")

# Logout button in sidebar
with st.sidebar:
    st.header("Account")
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# =====================================================================
# SCREEN 2 – Runner Profile
# =====================================================================
st.header("1. Your Runner Profile")
st.write("Tell us about yourself so we can personalise your workout.")

col_a, col_b = st.columns(2)
with col_a:
    runner_age = st.number_input("Age", min_value=13, max_value=100, value=25)
    runner_goal = st.selectbox(
        "Goal",
        ["General Fitness", "Weight Loss", "Race Training", "Stress Relief"],
    )
with col_b:
    runner_fitness = st.selectbox(
        "Fitness Level",
        ["Beginner", "Intermediate", "Advanced"],
    )
    runner_health = st.text_input(
        "Health notes (optional)",
        placeholder="e.g. bad knees, asthma …",
    )

st.divider()

# =====================================================================
# SCREEN 3 – Playlist selection
# =====================================================================
st.header("2. Pick your source playlists")
st.write("Select playlists you'd like us to pull songs from:")

if "user_playlists" not in st.session_state:
    with st.spinner("Loading your playlists…"):
        st.session_state["user_playlists"] = fetch_user_playlists(sp)

playlists = st.session_state["user_playlists"]

selected_ids: list[str] = []
if playlists:
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
else:
    st.info("No playlists found on your Spotify account.")

# Genre fallback when no playlists selected
genre_pref = ""
if len(selected_ids) == 0:
    st.markdown("---")
    st.markdown(
        "**No playlists selected?** No problem! Tell us your genre preferences "
        "and we'll find great tracks for you."
    )
    genre_pref = st.text_input(
        "Genre preferences",
        placeholder="e.g. pop, hip-hop, electronic, rock",
        help="Comma-separated genres. We'll search our dataset for matching tracks.",
    )

st.divider()

# =====================================================================
# SCREEN 4 – Workout config
# =====================================================================
st.header("3. Configure your workout")
workout_minutes = st.slider(
    "Workout duration (minutes)",
    min_value=15,
    max_value=120,
    value=45,
    step=5,
)

DEDALUS_MODEL_OPTIONS = [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-2.5-pro",
    "google/gemini-2.0-flash",
]
dedalus_model = st.selectbox(
    "Dedalus model (playlist curation)",
    options=DEDALUS_MODEL_OPTIONS,
    index=0,
    help="AI model used by Dedalus for discovery hints and track ordering.",
)

st.divider()

# =====================================================================
# Generate – no longer disabled when 0 playlists (genre fallback)
# =====================================================================
can_generate = len(selected_ids) > 0 or len(genre_pref.strip()) > 0
generate = st.button(
    "🎵 Generate Workout Playlist",
    use_container_width=True,
    disabled=not can_generate,
)

if not can_generate:
    st.info("Select at least one playlist or enter genre preferences above to get started.")

# When Generate is clicked, run the full generation pipeline and store in session state
if generate:
    # ── Agent 1: Workout Designer (K2-Think) ─────────────────────────
    with st.status("🤖 Agent 1: K2-Think is designing your workout…", expanded=True) as status:
        plan = design_workout(
            age=runner_age,
            fitness_level=runner_fitness,
            goal=runner_goal,
            health_notes=runner_health,
            workout_minutes=workout_minutes,
        )
        status.update(label="✅ Workout plan ready (K2-Think)", state="complete")

    # ── Gather tracks from selected playlists ───────────────────────
    all_tracks: list[dict] = []
    if selected_ids:
        with st.status("Fetching tracks from selected playlists…", expanded=True) as status:
            for pid in selected_ids:
                name = next((p["name"] for p in playlists if p["id"] == pid), pid)
                st.write(f"📂 {name}")
                tracks = fetch_playlist_tracks(sp, pid)
                all_tracks.extend(tracks)
            status.update(label=f"Fetched {len(all_tracks)} tracks", state="complete")

        # ── Look up BPMs ────────────────────────────────────────────
        with st.status("Looking up BPM data…", expanded=True) as status:
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

    # ── Agent 2: Music Curator (Dedalus) ─────────────────────────────
    with st.status("🎵 Agent 2: Dedalus is curating your playlist…", expanded=True) as status:
        st.write("Balancing familiar tracks with new discoveries…")
        playlist = curate_playlist(
            workout_plan=plan,
            familiar_tracks=all_tracks,
            workout_minutes=workout_minutes,
            genre_pref=genre_pref if genre_pref.strip() else None,
            dedalus_model=dedalus_model,
        )
        status.update(label="✅ Playlist curated (Dedalus)", state="complete")

    if not playlist:
        st.error(
            "Could not build a playlist — not enough tracks matched the BPM ranges. "
            "Try selecting more playlists or providing genre preferences."
        )
        st.stop()

    # Store in session state so results persist after Save button click
    stats = playlist_stats(playlist)

    # Clear any previously saved URL, cached insights, and route when generating a new playlist
    if "saved_spotify_url" in st.session_state:
        del st.session_state["saved_spotify_url"]
    if "generated_insights" in st.session_state:
        del st.session_state["generated_insights"]
    if "generated_route" in st.session_state:
        del st.session_state["generated_route"]

    st.session_state["generated_playlist"] = playlist
    st.session_state["generated_plan"] = plan
    st.session_state["generated_stats"] = stats
    st.session_state["generated_workout_minutes"] = workout_minutes
    st.session_state["generated_dedalus_model"] = dedalus_model
    st.session_state["generated_runner_age"] = runner_age
    st.session_state["generated_runner_fitness"] = runner_fitness
    st.session_state["generated_runner_goal"] = runner_goal
    st.session_state["generated_runner_health"] = runner_health

# =====================================================================
# SCREEN 5 – Results (shown whenever we have a generated playlist)
# =====================================================================
if "generated_playlist" in st.session_state:
    playlist = st.session_state["generated_playlist"]
    plan = st.session_state["generated_plan"]
    stats = st.session_state["generated_stats"]
    workout_minutes = st.session_state["generated_workout_minutes"]
    runner_age = st.session_state["generated_runner_age"]
    runner_fitness = st.session_state["generated_runner_fitness"]
    runner_goal = st.session_state["generated_runner_goal"]
    runner_health = st.session_state["generated_runner_health"]

    st.success("Your personalised workout playlist is ready!")

    # ── AI Coach Plan ────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="coach-card">
            <strong>🧠 AI Coach says:</strong><br><br>
            {plan.get("coaching_notes", "")}
            <br><br>
            <small>
                Warmup {int(plan["warmup_frac"]*100)}% ·
                Peak {int(plan["peak_frac"]*100)}% ·
                Cooldown {int(plan["cooldown_frac"]*100)}%
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Workout plan designed by K2-Think v2")

    # Target HR zones
    hr = plan.get("target_hr_zones", {})
    if hr:
        z1, z2, z3 = st.columns(3)
        z1.metric("🟡 Warmup HR", hr.get("warmup", "—"))
        z2.metric("🔴 Peak HR", hr.get("peak", "—"))
        z3.metric("🔵 Cooldown HR", hr.get("cooldown", "—"))

    # Recommended music BPM ranges
    b1, b2, b3 = st.columns(3)
    warmup_bpm = plan.get("warmup_bpm_range", [90, 120])
    peak_bpm = plan.get("peak_bpm_range", [140, 180])
    cooldown_bpm = plan.get("cooldown_bpm_range", [90, 120])
    b1.metric("🟡 Warmup BPM", f"{warmup_bpm[0]}–{warmup_bpm[1]}")
    b2.metric("🔴 Peak BPM", f"{peak_bpm[0]}–{peak_bpm[1]}")
    b3.metric("🔵 Cooldown BPM", f"{cooldown_bpm[0]}–{cooldown_bpm[1]}")

    # Safety notes from AI coach
    if plan.get("safety_notes"):
        with st.expander("⚠️ Safety Notes from AI Coach", expanded=bool(runner_health)):
            st.write(plan["safety_notes"])

    st.divider()

    # ── Stats row ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracks", stats["total_tracks"])
    c2.metric("Duration", f"{stats['total_duration_min']} min")
    c3.metric("BPM Range", f"{stats['min_bpm']}–{stats['max_bpm']}")
    c4.metric("Avg BPM", stats["avg_bpm"])

    # # Source breakdown
    # familiar_count = sum(1 for t in playlist if t.get("source") == "familiar")
    # discovery_count = sum(1 for t in playlist if t.get("source") == "discovery")
    # s1, s2 = st.columns(2)
    # s1.metric("🟢 Familiar Tracks", familiar_count)
    # s2.metric("🟣 New Discoveries", discovery_count)

    # ── BPM curve chart ─────────────────────────────────────────────
    st.subheader("Your Personalised BPM Curve")
    bpm_data = [{"Track #": i + 1, "BPM": t["bpm"]} for i, t in enumerate(playlist)]
    st.area_chart(
        bpm_data,
        x="Track #",
        y="BPM",
        color="#ef4444",
    )

    # ── Track list ──────────────────────────────────────────────────
    st.subheader("Tracklist")
    for i, track in enumerate(playlist):
        phase = _phase_tag(track.get("phase", ""))
        source = _source_tag(track.get("source", "familiar"))
        art = track.get("album_art") or ""
        img_html = f'<img src="{html.escape(art)}" width="40" height="40"/>' if art else ""
        name_escaped = html.escape(str(track.get("name", "")))
        artist_escaped = html.escape(str(track.get("artist", "")))
        bpm = track.get("bpm") or 0
        pace_str = format_pace(bpm_to_pace_min_per_km(bpm), unit="mi") if bpm else "—"
        row_html = (
            f'<div class="track-row">'
            f"{img_html}"
            f'<div style="flex:1">'
            f"<strong>{name_escaped}</strong><br>"
            f'<span style="opacity:0.7">{artist_escaped}</span>'
            f"</div>"
            f'<div style="text-align:right; min-width:70px">'
            f"{track['bpm']} BPM<br>"
            f'<span style="opacity:0.6">{_ms_to_min_sec(track["duration_ms"])}</span>'
            f"</div>"
            f'<div style="text-align:right; min-width:80px">~{html.escape(pace_str)}</div>'
            f'<div style="min-width:120px; text-align:right">{phase} {source}</div>'
            f"</div>"
        )
        st.html(row_html)

    st.divider()

    # =====================================================================
    # Health Insights (Dedalus)
    # =====================================================================
    st.subheader("🩺 Health Insights")
    st.caption("Powered by Dedalus Labs")

    if "generated_insights" not in st.session_state:
        with st.spinner("Generating health insights…"):
            st.session_state["generated_insights"] = generate_health_insights(
                age=runner_age,
                fitness_level=runner_fitness,
                goal=runner_goal,
                health_notes=runner_health,
                workout_minutes=workout_minutes,
                total_tracks=stats["total_tracks"],
                avg_bpm=stats["avg_bpm"],
                min_bpm=stats["min_bpm"],
                max_bpm=stats["max_bpm"],
                total_duration_min=stats["total_duration_min"],
                model=st.session_state.get("generated_dedalus_model"),
            )
    insights = st.session_state["generated_insights"]

    # Calories
    ic1, ic2 = st.columns(2)
    ic1.metric("🔥 Est. Calories", insights.get("estimated_calories", "—"))
    ic2.metric("⏱️ Playlist Duration", f"{stats['total_duration_min']} min")

    # HR Zone Breakdown
    with st.expander("❤️ Heart Rate Zone Breakdown", expanded=True):
        hr_zones = insights.get("hr_zone_breakdown", {})
        if isinstance(hr_zones, dict):
            for zone_name, zone_desc in hr_zones.items():
                st.markdown(f"**{zone_name.title()}:** {zone_desc}")
        else:
            st.write(hr_zones)

    # Recovery Tips
    with st.expander("🧊 Recovery Tips", expanded=True):
        st.write(insights.get("recovery_tips", ""))

    # Next Workout
    with st.expander("📈 Next Workout Suggestion", expanded=False):
        st.write(insights.get("next_workout", ""))

    # Safety Notes
    if runner_health:
        with st.expander("⚠️ Safety Notes", expanded=True):
            st.write(insights.get("safety_notes", ""))
    else:
        with st.expander("⚠️ Safety Notes", expanded=False):
            st.write(insights.get("safety_notes", ""))

    st.divider()

    # =====================================================================
    # Save to Spotify
    # =====================================================================
    st.subheader("Save to Spotify")
    playlist_name = st.text_input(
        "Playlist name",
        value=f"Workout {workout_minutes}min – {date.today().strftime('%b %d')}",
    )
    if st.button("💾 Save to my Spotify", use_container_width=True):
        with st.spinner("Creating playlist…"):
            track_uris = [t["uri"] for t in playlist]
            url = create_spotify_playlist(
                sp,
                name=playlist_name,
                track_uris=track_uris,
                description=(
                    f"AI-personalised BPM workout playlist ({workout_minutes} min) "
                    f"· {runner_fitness} · {runner_goal} "
                    f"· K2-Think + Dedalus Labs"
                ),
            )
            st.session_state["saved_spotify_url"] = url
        st.balloons()

    # Show success + Open in Spotify link (persists after Save, so graph stays visible)
    if "saved_spotify_url" in st.session_state:
        url = st.session_state["saved_spotify_url"]
        st.success("Playlist saved to your Spotify account!")
        # Opens in new tab so user keeps the app visible
        st.markdown(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block;background:#1DB954;color:white;padding:10px 24px;'
            'border-radius:20px;text-decoration:none;font-weight:600;text-align:center;">'
            "🎵 Open in Spotify</a>",
            unsafe_allow_html=True,
        )

    # =====================================================================
    # Plan your running route
    # =====================================================================
    st.divider()
    st.subheader("Plan your running route")
    st.caption(
        "Generate a round-trip route from a start location, matched to your "
        "workout duration and average BPM. Elevation and phase alignment are shown below."
    )

    route_location = st.text_input(
        "Start location",
        placeholder="e.g. Central Park, NYC or 40.7829, -73.9654",
        key="route_start_location",
    )

    if st.button("Generate route", key="generate_route_btn"):
        if not route_location or not route_location.strip():
            st.warning("Enter an address or lat,lng to generate a route.")
        else:
            with st.spinner("Finding route…"):
                start_input = route_location.strip()
                use_lat_lng = parse_coords(start_input) is not None

                route_result = get_running_route(
                    start_input,
                    workout_minutes=workout_minutes,
                    avg_bpm=stats["avg_bpm"],
                    use_lat_lng=use_lat_lng,
                )
                if route_result:
                    st.session_state["generated_route"] = route_result
                    st.success("Route generated.")
                else:
                    st.error(
                        "Could not find a route for that location. "
                        "Check the address or try pasting lat,lng. Ensure OPENROUTE_SERVICE_API_KEY is set."
                    )

    if "generated_route" in st.session_state:
        route_data = st.session_state["generated_route"]
        summary = route_data["summary"]
        geometry = route_data["geometry"]
        elevation_profile = route_data["elevation_profile"]
        start_coords = route_data["start_coords"]
        lon0, lat0 = start_coords[0], start_coords[1]

        # Est. run time from distance and running pace (not ORS walking duration)
        pace_min_per_km = bpm_to_pace_min_per_km(stats["avg_bpm"])
        speed_m_per_min = 1000 / pace_min_per_km if pace_min_per_km else 0
        est_run_min = round(summary["distance_m"] / speed_m_per_min) if speed_m_per_min else 0

        st.metric("Route distance", f"{summary['distance_m'] / 1609.34:.1f} mi")
        st.metric("Est. run time", f"~{est_run_min} min")
        st.caption(f"Planned workout: {workout_minutes} min")

        m = folium.Map(location=[lat0, lon0], zoom_start=14)
        # Folium expects (lat, lon); geometry is [lon, lat] or [lon, lat, z]
        route_lat_lon = [(p[1], p[0]) for p in geometry]
        folium.PolyLine(route_lat_lon, color="#ef4444", weight=5, opacity=0.8).add_to(m)
        folium.Marker([lat0, lon0], popup="Start / End", tooltip="Start / End").add_to(m)
        st_folium(m, use_container_width=True, key="route_map")
        st.caption("Round trip: starts and ends at the same point.")

        if elevation_profile:
            st.caption("Elevation along the route")
            elev_data = [
                {"Distance (km)": round(p["distance_m"] / 1000, 2), "Elevation (m)": p["elev_m"]}
                for p in elevation_profile
            ]
            st.line_chart(elev_data, x="Distance (km)", y="Elevation (m)")

        st.info(
            "Warmup aligns with the start of the route, peak with the middle, "
            "and cooldown with the end. Consider saving steep climbs for warmup/cooldown "
            "and using flatter sections for peak effort."
        )
