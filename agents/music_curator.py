"""
Agent 2 – Music Curator (Dedalus Labs)

Balances familiar tracks from the user's playlists with new discovery
tracks from the CSV dataset, then asks Dedalus to curate the final
ordered playlist for each workout phase.
"""

import json
import os
import requests

from bpm_service import enrich_tracks_with_bpm, search_tracks_by_bpm

DEDALUS_API_URL = "https://api.dedaluslabs.ai/v1/chat/completions"
MODEL = "openai/gpt-4o"

# Target mix: 70% familiar / 30% discovery (adjustable)
FAMILIAR_RATIO = 0.70


def _dedalus_api_key() -> str:
    return os.getenv("DEDALUS_API_KEY", "")


def _call_dedalus(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion to Dedalus and return assistant text."""
    api_key = _dedalus_api_key()
    if not api_key:
        raise ValueError("DEDALUS_API_KEY is not set")

    resp = requests.post(
        DEDALUS_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "system": system_prompt,
            "temperature": 0.4,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ── Phase helpers ──────────────────────────────────────────────────────

def _bucket_tracks_by_phase(
    tracks: list[dict],
    warmup_range: list[int],
    peak_range: list[int],
    cooldown_range: list[int],
) -> dict[str, list[dict]]:
    """
    Assign tracks to phases based on their BPM and the workout plan ranges.
    Tracks that don't fit any range go into the closest phase.
    """
    buckets: dict[str, list[dict]] = {
        "warmup": [],
        "peak": [],
        "cooldown": [],
    }

    for track in tracks:
        bpm = track.get("bpm")
        if bpm is None:
            continue

        if warmup_range[0] <= bpm <= warmup_range[1]:
            buckets["warmup"].append(track)
        elif peak_range[0] <= bpm <= peak_range[1]:
            buckets["peak"].append(track)
        elif cooldown_range[0] <= bpm <= cooldown_range[1]:
            buckets["cooldown"].append(track)
        else:
            # Put into the closest-matching phase
            dists = {
                "warmup": min(abs(bpm - warmup_range[0]), abs(bpm - warmup_range[1])),
                "peak": min(abs(bpm - peak_range[0]), abs(bpm - peak_range[1])),
                "cooldown": min(abs(bpm - cooldown_range[0]), abs(bpm - cooldown_range[1])),
            }
            closest = min(dists, key=dists.get)
            buckets[closest].append(track)

    return buckets


def _phase_target_ms(workout_minutes: int, frac: float) -> int:
    return int(workout_minutes * 60 * 1000 * frac)


def _total_duration_ms(tracks: list[dict]) -> int:
    return sum(t.get("duration_ms", 0) for t in tracks)


def _infer_genres(tracks: list[dict]) -> str:
    """Try to infer genres from discovery tracks that already have a genre tag."""
    genres = set()
    for t in tracks:
        g = t.get("genre", "")
        if g:
            genres.add(g.lower())
    if genres:
        return ", ".join(list(genres)[:5])
    return ""


# ── Dedalus discovery hints ────────────────────────────────────────────

def _ask_dedalus_discovery_hints(
    familiar_tracks: list[dict],
    genre_pref: str | None = None,
) -> dict:
    """
    Ask Dedalus to suggest genres and artist hints for discovering new
    tracks that complement the user's familiar tracks.

    Returns a dict like:
        {"genres": ["reggaeton", "latin pop"], "artist_hints": ["Bad Bunny"]}
    Falls back to inferred genres if the API call fails.
    """
    # Build a compact taste summary (up to 15 tracks)
    sample = familiar_tracks[:15]
    taste_summary = [
        {"name": t.get("name", ""), "artist": t.get("artist", "")}
        for t in sample
    ]

    system_prompt = (
        "You are a music discovery expert. Given a user's favourite tracks "
        "and optional genre preference, suggest related genres and artists "
        "to explore for new track discovery. Always respond with valid JSON only."
    )

    genre_hint = f"\nUser's stated genre preference: {genre_pref}" if genre_pref else ""

    user_prompt = f"""Here are tracks from the user's playlists:
{json.dumps(taste_summary, indent=2)}
{genre_hint}

Based on these tracks, suggest genres and artists for discovering similar but fresh music.

IMPORTANT: The genres you suggest will be used to search a Spotify dataset where the genre column
contains values like: pop, hip-hop, latin, reggaeton, r-n-b, rock, edm, dance, acoustic,
classical, jazz, blues, country, folk, indie, alternative, metal, punk, soul, funk, disco,
electronic, house, techno, trance, dubstep, trap, k-pop, j-pop, anime, ambient, chill,
sleep, study, party, romance, sad, happy, workout, etc.

Return a JSON object with EXACTLY these keys:
{{
  "genres": ["genre1", "genre2", "genre3", "genre4", "genre5"],
  "artist_hints": ["artist1", "artist2", "artist3"]
}}

Rules:
- Suggest 3-6 genres that are similar or adjacent to the user's taste
- Include the user's main genre(s) PLUS at least 2 related/adjacent genres
- Suggest 2-4 artist names whose music would complement the user's taste
- Think about cross-genre connections (e.g. a reggaeton fan might enjoy dance pop or latin pop)
"""

    fallback = {
        "genres": [g.strip() for g in (genre_pref or "").split(",") if g.strip()],
        "artist_hints": [],
    }

    try:
        raw = _call_dedalus(system_prompt, user_prompt)
        result = json.loads(raw)
        genres = result.get("genres", [])
        artist_hints = result.get("artist_hints", [])
        # Ensure we got something useful
        if not genres and not artist_hints:
            return fallback
        return {"genres": genres, "artist_hints": artist_hints}
    except Exception:
        return fallback


# ── Dedalus curation call ─────────────────────────────────────────────

def _ask_dedalus_to_curate(
    phase: str,
    candidates: list[dict],
    target_duration_ms: int,
    bpm_range: list[int],
) -> list[str]:
    """
    Send candidate tracks to Dedalus and ask it to pick and order the
    best selection for a phase. Returns ordered list of track IDs.
    Falls back to a simple sort if the API call fails.
    """
    # Build compact track list for the prompt
    track_info = []
    for t in candidates:
        track_info.append({
            "id": t["id"],
            "name": t["name"],
            "artist": t["artist"],
            "bpm": t["bpm"],
            "duration_ms": t["duration_ms"],
            "source": t.get("source", "familiar"),
        })

    target_min = round(target_duration_ms / 60000, 1)

    system_prompt = (
        "You are a music curator specializing in workout playlists. "
        "You create smooth BPM transitions and balance familiar songs with "
        "new discoveries. Always respond with valid JSON only."
    )

    user_prompt = f"""Select and order tracks for the {phase.upper()} phase of a running workout.

Requirements:
- Target duration: AT LEAST {target_min} minutes (this is critical — you MUST select enough tracks so their total duration_ms reaches at least {target_duration_ms} ms). It is better to slightly overshoot than undershoot.
- BPM range: {bpm_range[0]}-{bpm_range[1]} BPM
- Aim for ~70% familiar tracks and ~30% discovery tracks
- {"Warmup: arrange BPM ascending (low to high)" if phase == "warmup" else ""}
- {"Peak: keep BPM high, vary slightly to maintain energy" if phase == "peak" else ""}
- {"Cooldown: arrange BPM descending (high to low)" if phase == "cooldown" else ""}
- Ensure smooth BPM transitions between consecutive tracks
- Do NOT repeat any track ID — every entry in track_ids must be unique

Available tracks:
{json.dumps(track_info, indent=2)}

Return a JSON object with EXACTLY these keys:
{{
  "track_ids": ["id1", "id2", ...],
  "reasoning": "<brief explanation of your curation choices>"
}}

You MUST include enough tracks so their combined duration_ms totals at least {target_duration_ms} ms (~{target_min} min). Prefer including more tracks rather than fewer. If there aren't enough tracks to reach the target, include ALL available ones.
"""

    try:
        raw = _call_dedalus(system_prompt, user_prompt)
        result = json.loads(raw)
        return result.get("track_ids", [])
    except Exception:
        # Fallback: sort by BPM (ascending for warmup, descending for cooldown)
        if phase == "warmup":
            candidates.sort(key=lambda t: t.get("bpm", 0))
        elif phase == "cooldown":
            candidates.sort(key=lambda t: t.get("bpm", 0), reverse=True)
        return [t["id"] for t in candidates]


# ── Health insights (kept from ai_coach.py) ───────────────────────────

def generate_health_insights(
    age: int,
    fitness_level: str,
    goal: str,
    health_notes: str,
    workout_minutes: int,
    total_tracks: int,
    avg_bpm: int,
    min_bpm: int,
    max_bpm: int,
    total_duration_min: float,
) -> dict:
    """
    After the playlist is built, generate health insights about the workout.

    Returns a dict with keys:
        estimated_calories, hr_zone_breakdown, recovery_tips,
        next_workout, safety_notes
    """
    system_prompt = (
        "You are a certified running coach and exercise physiologist. "
        "You provide evidence-based health insights about workouts. "
        "Always respond with valid JSON only."
    )

    user_prompt = f"""Analyse this completed workout plan and provide health insights.

Runner profile:
- Age: {age}
- Fitness level: {fitness_level}
- Goal: {goal}
- Health notes: {health_notes if health_notes else 'None'}

Workout summary:
- Planned duration: {workout_minutes} minutes
- Actual playlist duration: {total_duration_min} minutes
- Total tracks: {total_tracks}
- Music BPM range: {min_bpm} - {max_bpm}
- Average music BPM: {avg_bpm}

Using the runner's max HR (220 - {age} = {220 - age} bpm), provide a health analysis.

Return a JSON object with EXACTLY these keys:
{{
  "estimated_calories": "<calorie burn estimate range, e.g. '300-400 kcal'>",
  "hr_zone_breakdown": {{
    "warmup": "<description of warmup zone, target HR, and % of workout>",
    "peak": "<description of peak zone, target HR, and % of workout>",
    "cooldown": "<description of cooldown zone, target HR, and % of workout>"
  }},
  "recovery_tips": "<2-3 actionable recovery recommendations>",
  "next_workout": "<suggestion for the next workout session based on their goal>",
  "safety_notes": "<any safety considerations based on their health notes, or general safety advice if no conditions reported>"
}}
"""

    default = {
        "estimated_calories": f"{int(workout_minutes * 8)}-{int(workout_minutes * 12)} kcal",
        "hr_zone_breakdown": {
            "warmup": "50-60% max HR — light effort to warm up muscles",
            "peak": "70-85% max HR — vigorous effort for cardiovascular benefit",
            "cooldown": "50-60% max HR — gradual recovery",
        },
        "recovery_tips": (
            "Hydrate well after your run. Stretch for 5-10 minutes focusing on "
            "calves, quads, and hip flexors. Consider a protein-rich snack within "
            "30 minutes."
        ),
        "next_workout": (
            "Try to maintain consistency. Aim for your next run in 1-2 days, "
            "adjusting intensity based on how you feel."
        ),
        "safety_notes": (
            "Listen to your body. If you feel dizzy, nauseous, or experience "
            "chest pain, stop immediately and seek medical attention."
        ),
    }

    try:
        raw = _call_dedalus(system_prompt, user_prompt)
        insights = json.loads(raw)

        required = [
            "estimated_calories", "hr_zone_breakdown",
            "recovery_tips", "next_workout", "safety_notes",
        ]
        for key in required:
            if key not in insights:
                return default

        return insights

    except Exception:
        return default


# ── Main curation entry point ─────────────────────────────────────────

def curate_playlist(
    workout_plan: dict,
    familiar_tracks: list[dict],
    workout_minutes: int,
    genre_pref: str | None = None,
) -> list[dict]:
    """
    Build a curated playlist using the workout plan from Agent 1.

    Parameters
    ----------
    workout_plan : dict
        Output from the Workout Designer (Agent 1). Must include:
        warmup_frac, peak_frac, cooldown_frac,
        warmup_bpm_range, peak_bpm_range, cooldown_bpm_range
    familiar_tracks : list[dict]
        Tracks from user's selected playlists, already enriched with BPM.
    workout_minutes : int
        Target workout duration.
    genre_pref : str or None
        User-provided genre preference (used when no playlists selected).

    Returns
    -------
    list[dict]
        Ordered playlist with each track tagged with 'source' and 'phase'.
    """
    warmup_range = workout_plan["warmup_bpm_range"]
    peak_range = workout_plan["peak_bpm_range"]
    cooldown_range = workout_plan["cooldown_bpm_range"]

    # Tag familiar tracks
    for t in familiar_tracks:
        if "source" not in t:
            t["source"] = "familiar"

    # 1. Bucket familiar tracks by phase
    familiar_with_bpm = [t for t in familiar_tracks if t.get("bpm") is not None]
    buckets = _bucket_tracks_by_phase(
        familiar_with_bpm, warmup_range, peak_range, cooldown_range
    )

    # Collect all familiar IDs to exclude from discovery
    familiar_ids = {t["id"] for t in familiar_with_bpm}

    # Infer genre from familiar tracks if user didn't provide one
    if not genre_pref:
        genre_pref = _infer_genres(familiar_with_bpm)

    # ── Ask Dedalus for discovery hints (genres + artist hints) ─────
    # This gives us AI-suggested genres and artists to diversify the pool
    discovery_hints = _ask_dedalus_discovery_hints(familiar_with_bpm, genre_pref)
    hint_genres = discovery_hints.get("genres", [])
    hint_artists = discovery_hints.get("artist_hints", [])

    # Merge Dedalus-suggested genres with user/inferred genre
    all_genres_list = list(hint_genres)
    if genre_pref:
        for g in genre_pref.split(","):
            g = g.strip().lower()
            if g and g not in [x.lower() for x in all_genres_list]:
                all_genres_list.append(g)
    discovery_genre_str = ", ".join(all_genres_list) if all_genres_list else None

    # 2. For each phase, check if we have enough tracks; fill gaps with discoveries
    phases = ["warmup", "peak", "cooldown"]
    phase_ranges = {
        "warmup": warmup_range,
        "peak": peak_range,
        "cooldown": cooldown_range,
    }
    phase_fracs = {
        "warmup": workout_plan["warmup_frac"],
        "peak": workout_plan["peak_frac"],
        "cooldown": workout_plan["cooldown_frac"],
    }

    final_playlist: list[dict] = []

    for phase in phases:
        target_ms = _phase_target_ms(workout_minutes, phase_fracs[phase])
        phase_familiar = buckets[phase]
        familiar_ms = _total_duration_ms(phase_familiar)

        # Check if we need discovery tracks
        candidates = list(phase_familiar)
        if familiar_ms < target_ms:
            needed_ms = target_ms - familiar_ms
            # Use ~3 min avg and generous buffer so we never under-fill
            est_needed = min(80, max(12, int(needed_ms / 180_000) + 6))

            bpm_range = phase_ranges[phase]
            discovery = search_tracks_by_bpm(
                min_bpm=bpm_range[0],
                max_bpm=bpm_range[1],
                genre=discovery_genre_str,
                exclude_ids=familiar_ids,
                limit=est_needed,
                artist_hints=hint_artists if hint_artists else None,
                diverse=True,
            )
            candidates.extend(discovery)

            # Track new IDs to avoid duplicates across phases
            for d in discovery:
                familiar_ids.add(d["id"])

        if not candidates:
            continue

        # 3. Ask Dedalus to curate and order this phase
        ordered_ids = _ask_dedalus_to_curate(
            phase=phase,
            candidates=candidates,
            target_duration_ms=target_ms,
            bpm_range=phase_ranges[phase],
        )

        # Build ordered track list from IDs (skip duplicates)
        id_to_track = {t["id"]: t for t in candidates}
        phase_tracks: list[dict] = []
        added_ids: set[str] = set()
        total_ms = 0

        for tid in ordered_ids:
            if tid in id_to_track and tid not in added_ids and total_ms < target_ms:
                track = id_to_track[tid]
                track["phase"] = phase
                phase_tracks.append(track)
                added_ids.add(tid)
                total_ms += track.get("duration_ms", 0)

        # If Dedalus didn't return enough, add remaining candidates
        if total_ms < target_ms:
            remaining = [t for t in candidates if t["id"] not in added_ids]
            if phase == "warmup":
                remaining.sort(key=lambda t: t.get("bpm", 0))
            elif phase == "cooldown":
                remaining.sort(key=lambda t: t.get("bpm", 0), reverse=True)

            for track in remaining:
                if total_ms >= target_ms:
                    break
                track["phase"] = phase
                phase_tracks.append(track)
                added_ids.add(track["id"])
                total_ms += track.get("duration_ms", 0)

        final_playlist.extend(phase_tracks)

    # ── Global duration top-up ──────────────────────────────────────
    # If the playlist is still more than 2 minutes short, add tracks
    # to the last phase (cooldown) to fill the gap.
    target_total_ms = workout_minutes * 60 * 1000
    current_total_ms = _total_duration_ms(final_playlist)
    shortfall_ms = target_total_ms - current_total_ms

    if shortfall_ms > 2 * 60 * 1000:  # more than 2 min short
        all_used_ids = {t["id"] for t in final_playlist}
        # Use cooldown BPM range for top-up (ending songs)
        topup_tracks = search_tracks_by_bpm(
            min_bpm=cooldown_range[0],
            max_bpm=cooldown_range[1],
            genre=None,  # relaxed — any genre
            exclude_ids=all_used_ids,
            limit=20,
        )
        for track in topup_tracks:
            if shortfall_ms <= 0:
                break
            track["phase"] = "cooldown"
            final_playlist.append(track)
            shortfall_ms -= track.get("duration_ms", 0)

    # ── Final safety-net deduplication (keep first occurrence) ──────
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for t in final_playlist:
        if t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            deduped.append(t)

    return deduped
