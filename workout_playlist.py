"""
BPM-curve playlist builder.

Builds a trapezoidal BPM profile:
  Warmup (25%) ──▶ Peak (50%) ──▶ Cooldown (25%)
   low → mid       highest BPMs      mid → low
"""

from __future__ import annotations
import random


# ── Phase splits (fractions of total workout duration) ──────────────────
WARMUP_FRAC = 0.25
PEAK_FRAC = 0.50
COOLDOWN_FRAC = 0.25


def _fill_phase(
    candidates: list[dict],
    target_ms: int,
) -> list[dict]:
    """
    Greedily pick tracks from *candidates* (already in desired order)
    until we reach ~target_ms of total duration.  Tries not to overshoot
    by more than one song.
    """
    picked: list[dict] = []
    total = 0
    for track in candidates:
        picked.append(track)
        total += track["duration_ms"]
        if total >= target_ms:
            break
    return picked


def build_workout_playlist(
    tracks: list[dict],
    workout_minutes: int,
    warmup_frac: float | None = None,
    peak_frac: float | None = None,
    cooldown_frac: float | None = None,
) -> list[dict]:
    """
    Given *tracks* (each must have 'bpm' and 'duration_ms') and a workout
    duration in minutes, return an ordered list of tracks following the
    BPM curve:  warmup (ascending) → peak (high) → cooldown (descending).

    Custom phase fractions can be supplied (from the AI coach); if omitted
    the module-level defaults are used.

    Tracks with bpm=None are excluded.
    """
    wf = warmup_frac if warmup_frac is not None else WARMUP_FRAC
    pf = peak_frac if peak_frac is not None else PEAK_FRAC
    cf = cooldown_frac if cooldown_frac is not None else COOLDOWN_FRAC

    # Filter out tracks with no BPM data and deduplicate by track id
    seen_ids: set[str] = set()
    valid: list[dict] = []
    for t in tracks:
        if t.get("bpm") is not None and t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            valid.append(t)

    if not valid:
        return []

    # Sort all tracks by BPM
    valid.sort(key=lambda t: t["bpm"])

    total_ms = workout_minutes * 60 * 1000
    warmup_ms = int(total_ms * wf)
    peak_ms = int(total_ms * pf)
    cooldown_ms = int(total_ms * cf)

    # ── Split into BPM tiers ────────────────────────────────────────────
    n = len(valid)
    low_end = int(n * 0.25)       # bottom 25% BPM
    high_start = int(n * 0.50)    # top 50% BPM

    low_pool = valid[:low_end] if low_end > 0 else valid[:1]
    mid_pool = valid[low_end:high_start] if low_end < high_start else []
    high_pool = valid[high_start:] if high_start < n else valid[-1:]

    # For warmup: low → mid (ascending BPM)
    warmup_candidates = sorted(low_pool + mid_pool, key=lambda t: t["bpm"])

    # For peak: highest BPM tracks, shuffled so it's not monotone
    peak_candidates = list(high_pool)
    random.shuffle(peak_candidates)

    # For cooldown: mid → low (descending BPM), reuse low/mid pools
    cooldown_candidates = sorted(
        low_pool + mid_pool, key=lambda t: t["bpm"], reverse=True
    )

    # ── Fill each phase ─────────────────────────────────────────────────
    warmup = _fill_phase(warmup_candidates, warmup_ms)
    peak = _fill_phase(peak_candidates, peak_ms)
    cooldown = _fill_phase(cooldown_candidates, cooldown_ms)

    # ── Handle edge case: not enough tracks ─────────────────────────────
    # If a phase is empty, redistribute whatever we have
    if not warmup and not cooldown:
        # Everything is peak
        return _fill_phase(
            sorted(valid, key=lambda t: t["bpm"]), total_ms
        )

    playlist = warmup + peak + cooldown
    return playlist


def playlist_stats(playlist: list[dict]) -> dict:
    """Return summary stats for the generated playlist."""
    if not playlist:
        return {"total_tracks": 0, "total_duration_min": 0, "avg_bpm": 0,
                "min_bpm": 0, "max_bpm": 0}

    bpms = [t["bpm"] for t in playlist if t.get("bpm")]
    total_dur_ms = sum(t["duration_ms"] for t in playlist)
    return {
        "total_tracks": len(playlist),
        "total_duration_min": round(total_dur_ms / 60000, 1),
        "avg_bpm": round(sum(bpms) / len(bpms)) if bpms else 0,
        "min_bpm": min(bpms) if bpms else 0,
        "max_bpm": max(bpms) if bpms else 0,
    }
