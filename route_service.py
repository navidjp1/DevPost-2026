"""
Running route generation via OpenRouteService.

Geocodes a start location, computes a round-trip route by target distance
(derived from workout duration and average BPM/pace), and returns geometry
plus elevation profile for display.
"""

import math
import os
from typing import Any

import requests

ORS_BASE = "https://api.openrouteservice.org"
DEFAULT_STRIDE_M = 1.35


# ── Pace helpers (BPM → running pace) ─────────────────────────────────────

def bpm_to_pace_min_per_km(bpm: int, stride_m: float = DEFAULT_STRIDE_M) -> float:
    """
    Estimated pace in min/km when cadence (steps/min) matches BPM.
    speed (m/min) = stride_m * bpm  =>  pace (min/km) = 1000 / (stride_m * bpm)
    """
    if bpm <= 0 or stride_m <= 0:
        return 0.0
    return 1000.0 / (stride_m * bpm)


def format_pace(min_per_km: float, unit: str = "km") -> str:
    """Format pace as e.g. '4:32 /km' or '7:18 /mi'."""
    if min_per_km <= 0 or not math.isfinite(min_per_km):
        return "—"
    if unit == "mi":
        # 1 mile = 1.60934 km => pace in min/mi = pace in min/km * 1.60934
        min_per_km = min_per_km * 1.60934
    total_sec = min_per_km * 60
    mins = int(total_sec // 60)
    secs = int(round(total_sec % 60))
    if secs >= 60:
        secs = 0
        mins += 1
    return f"{mins}:{secs:02d} /{unit}"


# ── Polyline decoding (with optional elevation) ─────────────────────────────

def _decode_polyline(encoded: str, is_3d: bool = False) -> list[list[float]]:
    """Decode ORS encoded polyline into list of [lon, lat] or [lon, lat, elev]."""
    points = []
    index = 0
    lat = 0
    lng = 0
    z = 0
    n = len(encoded)

    while index < n:
        result = 1
        shift = 0
        while True:
            b = ord(encoded[index]) - 63 - 1
            index += 1
            result += b << shift
            shift += 5
            if b < 0x1F:
                break
        lat += ~(result >> 1) if (result & 1) != 0 else (result >> 1)

        result = 1
        shift = 0
        while True:
            b = ord(encoded[index]) - 63 - 1
            index += 1
            result += b << shift
            shift += 5
            if b < 0x1F:
                break
        lng += ~(result >> 1) if (result & 1) != 0 else (result >> 1)

        if is_3d:
            result = 1
            shift = 0
            while True:
                b = ord(encoded[index]) - 63 - 1
                index += 1
                result += b << shift
                shift += 5
                if b < 0x1F:
                    break
                if index >= n:
                    break
            if index <= n:
                z += ~(result >> 1) if (result & 1) != 0 else (result >> 1)
            points.append([round(lng * 1e-5, 6), round(lat * 1e-5, 6), round(z * 1e-2, 1)])
        else:
            points.append([round(lng * 1e-5, 6), round(lat * 1e-5, 6)])

    return points


# ── Geocoding ─────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.getenv("OPENROUTE_SERVICE_API_KEY", "").strip()


def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Geocode a free-text address via ORS. Returns (lon, lat) or None.
    """
    key = _api_key()
    if not key:
        return None
    url = f"{ORS_BASE}/geocode/search"
    params = {"api_key": key, "text": address}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        features = data.get("features") or []
        if not features:
            return None
        coords = features[0].get("geometry", {}).get("coordinates")
        if coords and len(coords) >= 2:
            return (float(coords[0]), float(coords[1]))
    except Exception:
        pass
    return None


def parse_coords(lat_lng_str: str) -> tuple[float, float] | None:
    """
    Parse "lat,lng" or "lat, lng" string. Returns (lon, lat) for API use.
    """
    s = lat_lng_str.strip().replace(" ", "")
    if not s:
        return None
    parts = s.split(",")
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
        return (lon, lat)
    except ValueError:
        return None


# ── Turn point (project distance from start) ──────────────────────────────

def _project_point(lon: float, lat: float, distance_m: float, bearing_deg: float = 0.0) -> tuple[float, float]:
    """Project a point by distance_m in direction bearing_deg (0=North, 90=East)."""
    # Approximate: 1 deg lat ≈ 111320 m; 1 deg lon ≈ 111320*cos(lat) m
    d_km = distance_m / 1000.0
    br = math.radians(bearing_deg)
    # Simple spherical approximation
    R = 6371  # km
    lat2 = math.asin(
        math.sin(math.radians(lat)) * math.cos(d_km / R)
        + math.cos(math.radians(lat)) * math.sin(d_km / R) * math.cos(br)
    )
    lon2 = math.radians(lon) + math.atan2(
        math.sin(br) * math.sin(d_km / R) * math.cos(math.radians(lat)),
        math.cos(d_km / R) - math.sin(math.radians(lat)) * math.sin(lat2),
    )
    return (math.degrees(lon2), math.degrees(lat2))


# ── Directions (round trip with elevation) ──────────────────────────────────

def get_running_route(
    start_address_or_coords: str,
    workout_minutes: int,
    avg_bpm: int,
    stride_m: float = DEFAULT_STRIDE_M,
    use_lat_lng: bool = False,
) -> dict[str, Any] | None:
    """
    Generate a round-trip running route from start location and workout params.

    start_address_or_coords: Either an address string or "lat,lng" if use_lat_lng=True.
    workout_minutes: Target run duration (minutes).
    avg_bpm: Average BPM of the playlist (used to estimate pace and distance).
    stride_m: Stride length in meters for pace/distance (default 1.35).

    Returns a dict with:
        geometry: list of [lon, lat] or [lon, lat, elev] for the full route
        summary: { "distance_m", "duration_s" }
        elevation_profile: list of { "distance_m", "elev_m" } (cumulative distance, elevation)
        start_coords: [lon, lat]
    or None if geocoding/routing fails.
    """
    key = _api_key()
    if not key:
        return None

    # Resolve start to (lon, lat)
    if use_lat_lng:
        start = parse_coords(start_address_or_coords)
    else:
        start = geocode_address(start_address_or_coords)
    if not start:
        return None

    lon, lat = start

    # Target distance: pace (m/min) * workout_minutes
    pace_min_per_km = bpm_to_pace_min_per_km(avg_bpm, stride_m)
    if pace_min_per_km <= 0:
        return None
    speed_m_per_min = 1000.0 / pace_min_per_km
    target_distance_m = speed_m_per_min * workout_minutes
    half_m = target_distance_m / 2.0

    # Turn point (north then back)
    turn_lon, turn_lat = _project_point(lon, lat, half_m, 0.0)

    # ORS: coordinates as [lon, lat]
    coordinates = [[lon, lat], [turn_lon, turn_lat], [lon, lat]]

    url = f"{ORS_BASE}/v2/directions/foot-walking"
    headers = {"Authorization": key, "Content-Type": "application/json"}
    body = {
        "coordinates": coordinates,
        "elevation": True,
    }

    try:
        r = requests.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    routes = data.get("routes") or []
    if not routes:
        return None

    route = routes[0]
    summary = route.get("summary", {})
    distance_m = int(summary.get("distance", 0))
    duration_s = int(summary.get("duration", 0))

    # Geometry: encoded polyline string or list of coordinates
    geom = route.get("geometry")
    if not geom:
        return None

    if isinstance(geom, list):
        points = geom
    else:
        try:
            points = _decode_polyline(geom, is_3d=True)
        except Exception:
            points = _decode_polyline(geom, is_3d=False)

    # Close the loop so the route visibly ends at the start (ORS may snap and not close exactly)
    if points and len(points) >= 2:
        first_pt = points[0]
        last_pt = points[-1]
        gap_m = _haversine_m(last_pt[0], last_pt[1], lon, lat)
        if gap_m > 10:
            if len(first_pt) >= 3:
                points.append([lon, lat, first_pt[2]])
            else:
                points.append([lon, lat])

    # Build elevation profile (cumulative distance, elevation)
    elevation_profile: list[dict[str, float]] = []
    has_elev = points and len(points[0]) >= 3
    cum = 0.0
    for i, pt in enumerate(points):
        if i > 0:
            lon0, lat0 = points[i - 1][0], points[i - 1][1]
            cum += _haversine_m(lon0, lat0, pt[0], pt[1])
        elev = pt[2] if has_elev and len(pt) >= 3 else 0.0
        elevation_profile.append({"distance_m": round(cum, 1), "elev_m": elev})

    return {
        "geometry": points,
        "summary": {"distance_m": distance_m, "duration_s": duration_s},
        "elevation_profile": elevation_profile,
        "start_coords": [lon, lat],
    }


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distance in meters between two WGS84 points."""
    R = 6371000  # m
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
