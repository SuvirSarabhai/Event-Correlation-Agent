"""
Feature engineering for alert-pair correlation model.
Produces the same 13 features as ICRE, adapted to the
correlation agent's alert schema:
    area, source_id, event_type, severity, confidence, created_at
"""

from __future__ import annotations

import math
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

FEATURE_NAMES: tuple[str, ...] = (
    "f_time_delta_minutes",
    "f_same_site",
    "f_same_zone",
    "f_location_similarity",
    "f_source_match",
    "f_source_complement",
    "f_severity_delta",
    "f_alert_type_match",
    "f_alert_type_semantic_sim",
    "f_distance_meters",
    "f_time_window_score",
    "f_severity_score",
    "f_certainty_delta",
)

# Numeric severity mapping  (LOW=0, MEDIUM=1, HIGH=2, CRITICAL=3)
SEVERITY_NUM: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Known semantically-similar event-type pairs and their similarity score
def _pk(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a.upper(), b.upper())))  # type: ignore[return-value]


SEMANTIC_SIMILARITY: dict[tuple[str, str], float] = {
    # ── Intrusion / Access ───────────────────────────────────────────
    _pk("INTRUSION", "PERIMETER_BREACH"): 0.90,
    _pk("INTRUSION", "MOTION_DETECTED"): 0.82,
    _pk("INTRUSION", "UNAUTHORIZED_ACCESS"): 0.88,
    _pk("PERIMETER_BREACH", "MOTION_DETECTED"): 0.85,
    _pk("PERIMETER_BREACH", "UNAUTHORIZED_ACCESS"): 0.87,
    _pk("MOTION_DETECTED", "PERSON_DETECTED"): 0.88,
    _pk("MOTION_DETECTED", "LOITERING"): 0.80,
    _pk("PERSON_DETECTED", "LOITERING"): 0.85,
    _pk("PERSON_DETECTED", "TAILGATING"): 0.80,
    _pk("ACCESS_DENIED", "BADGE_FAIL"): 0.90,
    _pk("ACCESS_DENIED", "DOOR_FORCED"): 0.88,
    _pk("ACCESS_DENIED", "UNKNOWN_BADGE"): 0.85,
    _pk("DOOR_FORCED", "TAILGATING"): 0.80,
    _pk("BADGE_FAIL", "UNKNOWN_BADGE"): 0.82,
    _pk("VIBRATION", "DOOR_FORCED"): 0.83,
    _pk("VIBRATION", "PERIMETER_BREACH"): 0.78,
    _pk("CAMERA_TAMPER", "PERIMETER_BREACH"): 0.72,
    _pk("CROWD_DETECTED", "LOITERING"): 0.80,
    _pk("CROWD_DETECTED", "PERIMETER_BREACH"): 0.75,
    # ── Fire / Hazard ────────────────────────────────────────────────
    _pk("FIRE", "SMOKE"): 0.95,
    _pk("FIRE", "TEMPERATURE_HIGH"): 0.85,
    _pk("FIRE", "EXPLOSION"): 0.88,
    _pk("SMOKE", "TEMPERATURE_HIGH"): 0.80,
    _pk("GAS_LEAK", "FIRE"): 0.78,
    _pk("GAS_LEAK", "SMOKE"): 0.75,
    _pk("GAS_LEAK", "EXPLOSION"): 0.82,
    # ── Road / Vehicle incidents ─────────────────────────────────────
    _pk("ACCIDENT", "CRASH"): 0.92,
    _pk("ACCIDENT", "COLLISION"): 0.90,
    _pk("ACCIDENT", "HIT_AND_RUN"): 0.85,
    _pk("ACCIDENT", "VEHICLE_BREAKDOWN"): 0.70,
    _pk("CRASH", "COLLISION"): 0.90,
    _pk("CRASH", "HIT_AND_RUN"): 0.83,
    _pk("COLLISION", "HIT_AND_RUN"): 0.80,
    _pk("ACCIDENT", "FIRE"): 0.72,       # Vehicle fire after accident
    _pk("CRASH", "FIRE"): 0.70,
    _pk("ACCIDENT", "SMOKE"): 0.68,
    # ── Medical / Emergency ──────────────────────────────────────────
    _pk("MEDICAL_EMERGENCY", "FALL_DETECTED"): 0.80,
    _pk("MEDICAL_EMERGENCY", "PANIC_ALERT"): 0.75,
}

# Known cross-source complementary event-type pairs
CROSS_SOURCE_COMPLEMENT: set[tuple[str, str]] = {
    _pk("INTRUSION", "ACCESS_DENIED"),
    _pk("INTRUSION", "DOOR_FORCED"),
    _pk("PERIMETER_BREACH", "ACCESS_DENIED"),
    _pk("PERIMETER_BREACH", "DOOR_FORCED"),
    _pk("MOTION_DETECTED", "DOOR_FORCED"),
    _pk("PERSON_DETECTED", "ACCESS_DENIED"),
    _pk("PERSON_DETECTED", "TAILGATING"),
    _pk("FIRE", "CAMERA_TAMPER"),
    _pk("SMOKE", "PERIMETER_BREACH"),
    _pk("VIBRATION", "DOOR_FORCED"),
    _pk("VIBRATION", "PERIMETER_BREACH"),
    _pk("TEMPERATURE_HIGH", "FIRE"),
    _pk("GAS_LEAK", "CAMERA_TAMPER"),
}

# Area adjacency map — areas that are physically next to each other.
# Add / edit to match your site layout.
AREA_ADJACENCY: dict[str, set[str]] = {
    "NORTH_WING":   {"CENTRAL_HUB", "EAST_WING"},
    "SOUTH_WING":   {"CENTRAL_HUB", "WEST_WING"},
    "EAST_WING":    {"CENTRAL_HUB", "NORTH_WING"},
    "WEST_WING":    {"CENTRAL_HUB", "SOUTH_WING"},
    "CENTRAL_HUB":  {"NORTH_WING", "SOUTH_WING", "EAST_WING", "WEST_WING"},
    "LOBBY":        {"CENTRAL_HUB", "PARKING"},
    "PARKING":      {"LOBBY", "PERIMETER"},
    "PERIMETER":    {"PARKING", "NORTH_WING", "SOUTH_WING"},
    "SERVER_ROOM":  {"CENTRAL_HUB"},
    "CAFETERIA":    {"CENTRAL_HUB", "SOUTH_WING"},
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _norm(val: Any) -> str:
    return str(val or "").strip().upper()


def _location_similarity(a: str, b: str) -> float:
    """Fuzzy string similarity between two area/location names (0.0–1.0).
    Mirrors ICRE: SequenceMatcher so 'Flat-1' vs 'Flat-10' scores ~0.89
    instead of the 0.0 a rigid adjacency map would give."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two GPS coordinates."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    hav = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2.0 * R * math.atan2(math.sqrt(hav), math.sqrt(1.0 - hav))


def _get(alert: Any, *keys: str) -> Any:
    """Retrieve a value from a dict or object, trying multiple key names."""
    for k in keys:
        if isinstance(alert, dict):
            v = alert.get(k)
        else:
            v = getattr(alert, k, None)
        if v is not None:
            return v
    return None


def _to_datetime(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    return None


def _severity_num(alert: Any) -> int:
    """Map alert severity to 0–3 (LOW/MEDIUM/HIGH/CRITICAL).
    Handles both string labels and numeric severity on a 1–10 scale.
    """
    raw = _norm(_get(alert, "severity"))
    # 1. Try direct string label first
    val = SEVERITY_NUM.get(raw.lower(), None)
    if val is not None:
        return val
    # 2. Fall back to numeric range bucketing (1–10 scale)
    try:
        n = float(raw)
        if n >= 8: return 3   # CRITICAL
        if n >= 6: return 2   # HIGH
        if n >= 4: return 1   # MEDIUM
        return 0              # LOW
    except (ValueError, TypeError):
        return 1              # default MEDIUM


def _time_window_score(delta_min: float) -> float:
    """Decayed score based on time gap (mirrors ICRE exactly)."""
    if delta_min <= 10:
        return 1.0
    if delta_min <= 20:
        return 0.85
    if delta_min <= 30:
        return 0.65
    if delta_min <= 45:
        return 0.45
    if delta_min <= 60:
        return 0.25
    if delta_min <= 90:
        return 0.10
    return 0.0


def _semantic_sim(type_a: str, type_b: str) -> float:
    """Return semantic similarity between two event types."""
    a = type_a.upper().strip()
    b = type_b.upper().strip()
    if a == b:
        return 1.0
    return SEMANTIC_SIMILARITY.get(_pk(a, b), 0.10)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def build_pair_features(alert_a: Any, alert_b: Any) -> list[float]:
    """
    Build an ordered 13-element feature vector for an alert pair.
    Field order must match FEATURE_NAMES exactly.

    Parameters
    ----------
    alert_a, alert_b : dict or ORM row
        Each alert must expose: created_at, area, source_id,
        event_type, severity, confidence.

    Returns
    -------
    list[float]  — length 13, one value per FEATURE_NAMES entry.
    """

    # ── Timestamps ──────────────────────────────────────────────
    ts_a = _to_datetime(_get(alert_a, "created_at"))
    ts_b = _to_datetime(_get(alert_b, "created_at"))
    if ts_a and ts_b:
        delta_min = abs((ts_a - ts_b).total_seconds()) / 60.0
    else:
        delta_min = 0.0

    # ── Spatial ─────────────────────────────────────────────────
    area_a = _norm(_get(alert_a, "area"))
    area_b = _norm(_get(alert_b, "area"))

    # f_same_site  — correlation agent is single-site; always 1
    f_same_site = 1.0

    # f_same_zone  — exact area match
    f_same_zone = 1.0 if (area_a and area_b and area_a == area_b) else 0.0

    # f_location_similarity — fuzzy string match on area name (ICRE style)
    # Handles free-form names like 'Flat-1' vs 'Flat-10' gracefully
    f_location_similarity = _location_similarity(area_a, area_b)

    # f_distance_meters — Haversine if geo_lat/geo_lng are present, else 0.0
    try:
        lat1 = float(_get(alert_a, "geo_lat") or 0)
        lon1 = float(_get(alert_a, "geo_lng") or 0)
        lat2 = float(_get(alert_b, "geo_lat") or 0)
        lon2 = float(_get(alert_b, "geo_lng") or 0)
        f_distance_meters = (
            _haversine_m(lat1, lon1, lat2, lon2)
            if any([lat1, lon1, lat2, lon2]) else 0.0
        )
    except (TypeError, ValueError):
        f_distance_meters = 0.0

    # ── Source ──────────────────────────────────────────────────
    src_a = _norm(_get(alert_a, "source_id"))
    src_b = _norm(_get(alert_b, "source_id"))

    f_source_match = 1.0 if (src_a and src_b and src_a == src_b) else 0.0

    # f_source_complement — are the event types a known cross-source pair?
    evt_a = _norm(_get(alert_a, "event_type"))
    evt_b = _norm(_get(alert_b, "event_type"))
    f_source_complement = (
        1.0 if (_pk(evt_a, evt_b) in CROSS_SOURCE_COMPLEMENT) else 0.0
    )

    # ── Severity ────────────────────────────────────────────────
    sev_a = _severity_num(alert_a)
    sev_b = _severity_num(alert_b)

    f_severity_delta = abs(sev_a - sev_b) / 3.0          # normalised 0-1
    f_severity_score = (sev_a + sev_b) / 6.0             # normalised 0-1

    # ── Alert type ──────────────────────────────────────────────
    f_alert_type_match = 1.0 if (evt_a and evt_b and evt_a == evt_b) else 0.0
    f_alert_type_semantic_sim = _semantic_sim(evt_a, evt_b)

    # ── Confidence / certainty ──────────────────────────────────
    conf_a = float(_get(alert_a, "confidence") or 0.0)
    conf_b = float(_get(alert_b, "confidence") or 0.0)
    f_certainty_delta = abs(conf_a - conf_b)

    # ── Temporal scores ─────────────────────────────────────────
    f_time_window_score = _time_window_score(delta_min)

    return [
        round(delta_min, 4),               # 1  f_time_delta_minutes
        float(f_same_site),                # 2  f_same_site
        float(f_same_zone),                # 3  f_same_zone
        round(f_location_similarity, 4),   # 4  f_location_similarity
        float(f_source_match),             # 5  f_source_match
        float(f_source_complement),        # 6  f_source_complement
        round(f_severity_delta, 4),        # 7  f_severity_delta
        float(f_alert_type_match),         # 8  f_alert_type_match
        round(f_alert_type_semantic_sim, 4),  # 9  f_alert_type_semantic_sim
        float(f_distance_meters),          # 10 f_distance_meters
        round(f_time_window_score, 4),     # 11 f_time_window_score
        round(f_severity_score, 4),        # 12 f_severity_score
        round(f_certainty_delta, 4),       # 13 f_certainty_delta
    ]
