"""
AI Running Coach powered by Dedalus Labs.

Uses the Dedalus unified API to generate personalised workout plans
and post-workout health insights.
"""

import json
import os
import requests
import streamlit as st

DEDALUS_API_URL = "https://api.dedaluslabs.ai/v1/chat/completions"
MODEL = "openai/gpt-4o"


def _dedalus_api_key() -> str:
    return os.getenv("DEDALUS_API_KEY", "")


def _call_dedalus(system_prompt: str, user_prompt: str) -> str:
    """
    Send a chat completion request to the Dedalus API and return the
    assistant's text response.
    """
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
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ── Default fallback values ────────────────────────────────────────────
_DEFAULT_PLAN = {
    "warmup_frac": 0.25,
    "peak_frac": 0.50,
    "cooldown_frac": 0.25,
    "target_hr_zones": {
        "resting": "60-80 bpm",
        "warmup": "100-120 bpm",
        "peak": "140-170 bpm",
        "cooldown": "100-120 bpm",
    },
    "warmup_bpm_range": "90-120 BPM",
    "peak_bpm_range": "140-180 BPM",
    "cooldown_bpm_range": "90-120 BPM",
    "coaching_notes": (
        "This is a balanced workout plan. Warm up gradually, "
        "push hard during the peak phase, then bring your heart rate "
        "back down in the cooldown."
    ),
}


def generate_personalized_plan(
    age: int,
    fitness_level: str,
    goal: str,
    health_notes: str,
    workout_minutes: int,
) -> dict:
    """
    Ask the AI coach to produce a personalised BPM-curve plan.

    Returns a dict with keys:
        warmup_frac, peak_frac, cooldown_frac,
        target_hr_zones, warmup_bpm_range, peak_bpm_range,
        cooldown_bpm_range, coaching_notes
    Falls back to sensible defaults if the API call fails.
    """
    system_prompt = (
        "You are a certified running coach and exercise physiologist. "
        "You provide evidence-based, personalised running plans. "
        "Always respond with valid JSON only."
    )

    user_prompt = f"""Given this runner profile and workout, create a personalised plan.

Runner profile:
- Age: {age}
- Fitness level: {fitness_level}
- Goal: {goal}
- Health notes: {health_notes if health_notes else 'None'}
- Workout duration: {workout_minutes} minutes

Use the Karvonen formula (max HR = 220 - age) to compute heart rate zones.
Adjust the warmup / peak / cooldown phase durations based on fitness level and goal:
  - Beginners need longer warmups and cooldowns
  - Weight loss benefits from a longer peak phase at moderate intensity
  - Race training needs a shorter warmup and longer peak at high intensity
  - Stress relief benefits from longer warmup/cooldown and moderate peak

Return a JSON object with EXACTLY these keys:
{{
  "warmup_frac": <float 0-1, fraction of workout for warmup>,
  "peak_frac": <float 0-1, fraction of workout for peak>,
  "cooldown_frac": <float 0-1, fraction of workout for cooldown>,
  "target_hr_zones": {{
    "resting": "<heart rate range string>",
    "warmup": "<heart rate range string>",
    "peak": "<heart rate range string>",
    "cooldown": "<heart rate range string>"
  }},
  "warmup_bpm_range": "<music BPM range for warmup phase>",
  "peak_bpm_range": "<music BPM range for peak phase>",
  "cooldown_bpm_range": "<music BPM range for cooldown phase>",
  "coaching_notes": "<2-3 sentences of personalized coaching advice explaining why this plan is right for the runner>"
}}

The three fractions MUST sum to 1.0.
"""

    try:
        raw = _call_dedalus(system_prompt, user_prompt)
        plan = json.loads(raw)

        # Validate required keys and fracs
        required = [
            "warmup_frac", "peak_frac", "cooldown_frac",
            "target_hr_zones", "coaching_notes",
        ]
        for key in required:
            if key not in plan:
                return _DEFAULT_PLAN

        # Normalise fractions to ensure they sum to 1
        total = plan["warmup_frac"] + plan["peak_frac"] + plan["cooldown_frac"]
        if total <= 0:
            return _DEFAULT_PLAN
        plan["warmup_frac"] /= total
        plan["peak_frac"] /= total
        plan["cooldown_frac"] /= total

        return plan

    except Exception:
        return _DEFAULT_PLAN


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
    After the playlist is built, generate health insights about the
    workout.

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
