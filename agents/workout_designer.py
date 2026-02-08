"""
Agent 1 – Workout Designer (K2-Think v2)

Creates a scientifically-sound workout structure with personalised
BPM targets, heart rate zones, and phase durations.
"""

import json
import os
import re
import requests

K2_API_URL = "https://api.k2think.ai/v1/chat/completions"
MODEL = "MBZUAI-IFM/K2-Think-v2"


def _k2_api_key() -> str:
    return os.getenv("K2_API_KEY", "")


def _extract_json(text: str) -> str:
    """
    Extract the JSON object from K2-Think's response.

    K2-Think is a reasoning model that returns a <think>...</think> block
    with chain-of-thought reasoning, followed by the actual JSON answer.
    This function strips the thinking block and extracts the JSON.
    """
    # Strip everything up to and including </think>
    if "</think>" in text:
        text = text.split("</think>", 1)[1]

    # Find the first { ... } JSON object in the remaining text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    return text.strip()


def _call_k2think(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion to K2-Think v2."""
    api_key = _k2_api_key()
    if not api_key:
        raise ValueError("K2_API_KEY is not set")

    resp = requests.post(
        K2_API_URL,
        headers={
            "accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.3,
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    print(data)
    raw_content = data["choices"][0]["message"]["content"]
    return _extract_json(raw_content)


# ── Hardcoded defaults (used when the API is unavailable) ──────────────
_DEFAULT_PLAN = {
    "warmup_frac": 0.25,
    "peak_frac": 0.50,
    "cooldown_frac": 0.25,
    "warmup_bpm_range": [90, 120],
    "peak_bpm_range": [140, 180],
    "cooldown_bpm_range": [90, 120],
    "target_hr_zones": {
        "resting": "60-80 bpm",
        "warmup": "100-120 bpm",
        "peak": "140-170 bpm",
        "cooldown": "100-120 bpm",
    },
    "coaching_notes": (
        "This is a balanced workout plan. Warm up gradually, "
        "push hard during the peak phase, then bring your heart rate "
        "back down in the cooldown."
    ),
    "safety_notes": (
        "Listen to your body. If you feel dizzy, nauseous, or "
        "experience chest pain, stop immediately and seek medical attention."
    ),
}


def design_workout(
    age: int,
    fitness_level: str,
    goal: str,
    health_notes: str,
    workout_minutes: int,
) -> dict:
    """
    Use K2-Think to produce a personalised workout plan.

    Returns a dict with keys:
        warmup_frac, peak_frac, cooldown_frac,
        warmup_bpm_range, peak_bpm_range, cooldown_bpm_range,
        target_hr_zones, coaching_notes, safety_notes
    """
    system_prompt = (
        "You are a certified running coach and exercise physiologist. "
        "You design evidence-based, personalised running workout plans. "
        "Always respond with valid JSON only — no markdown, no commentary."
    )

    user_prompt = f"""Design a personalised running workout plan.

Runner profile:
- Age: {age}
- Fitness level: {fitness_level}
- Goal: {goal}
- Health notes: {health_notes if health_notes else 'None'}
- Workout duration: {workout_minutes} minutes

Use the Karvonen formula (max HR = 220 - age) to compute heart rate zones.
Adjust the warmup / peak / cooldown phase durations based on fitness level and goal:
  - Beginners need longer warmups and cooldowns (e.g. 30/40/30)
  - Weight loss benefits from a longer peak phase at moderate intensity
  - Race training needs a shorter warmup and longer peak at high intensity
  - Stress relief benefits from longer warmup/cooldown and moderate peak

Return a JSON object with EXACTLY these keys:
{{
  "warmup_frac": <float 0-1, fraction of workout for warmup>,
  "peak_frac": <float 0-1, fraction of workout for peak>,
  "cooldown_frac": <float 0-1, fraction of workout for cooldown>,
  "warmup_bpm_range": [<min_music_bpm_int>, <max_music_bpm_int>],
  "peak_bpm_range": [<min_music_bpm_int>, <max_music_bpm_int>],
  "cooldown_bpm_range": [<min_music_bpm_int>, <max_music_bpm_int>],
  "target_hr_zones": {{
    "resting": "<heart rate range string>",
    "warmup": "<heart rate range string>",
    "peak": "<heart rate range string>",
    "cooldown": "<heart rate range string>"
  }},
  "coaching_notes": "<2-3 sentences of personalised coaching advice>",
  "safety_notes": "<safety considerations based on health notes, or general advice>"
}}

The three fractions MUST sum to 1.0.
Music BPM ranges should be realistic: warmup 80-120, peak 130-185, cooldown 80-120.
"""

    try:
        raw = _call_k2think(system_prompt, user_prompt)
        plan = json.loads(raw)

        # Validate required keys
        required = [
            "warmup_frac", "peak_frac", "cooldown_frac",
            "warmup_bpm_range", "peak_bpm_range", "cooldown_bpm_range",
            "target_hr_zones", "coaching_notes",
        ]
        for key in required:
            if key not in plan:
                return _DEFAULT_PLAN

        # Normalise fractions to sum to 1
        total = plan["warmup_frac"] + plan["peak_frac"] + plan["cooldown_frac"]
        if total <= 0:
            return _DEFAULT_PLAN
        plan["warmup_frac"] /= total
        plan["peak_frac"] /= total
        plan["cooldown_frac"] /= total

        # Ensure BPM ranges are [int, int] lists
        for key in ("warmup_bpm_range", "peak_bpm_range", "cooldown_bpm_range"):
            val = plan.get(key)
            if not isinstance(val, list) or len(val) != 2:
                plan[key] = _DEFAULT_PLAN[key]
            else:
                plan[key] = [int(val[0]), int(val[1])]

        # Ensure safety_notes exists
        if "safety_notes" not in plan:
            plan["safety_notes"] = _DEFAULT_PLAN["safety_notes"]

        return plan

    except Exception:
        return _DEFAULT_PLAN
