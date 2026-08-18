import uuid
from scoring import compute_score
from reasoning import generate_reasoning
from config import INCIDENT_THRESHOLD, USE_ML_MODEL, ML_THRESHOLD

# ── ML predictor (loaded lazily on first use) ──────────────────────────────
if USE_ML_MODEL:
    from ml.predictor import get_predictor


def _get_score(alert: dict, incident: dict) -> float:
    """
    Return a correlation score for (alert, incident).

    - USE_ML_MODEL=True  → XGBoost probability (0.0 – 1.0)
    - USE_ML_MODEL=False → original weighted rule-based score
    """
    if USE_ML_MODEL:
        predictor = get_predictor()
        # Build a synthetic "alert_b" dict from the stored incident fields
        # so build_pair_features can extract the same keys it expects.
        incident_as_alert = {
            "created_at":  incident.get("created_at"),
            "area":        incident.get("area"),
            "source_id":   incident.get("source_id"),
            "event_type":  incident.get("event_type"),
            "severity":    incident.get("severity"),
            "confidence":  incident.get("confidence", 1.0),
        }
        return predictor.predict_proba(alert, incident_as_alert)
    else:
        return compute_score(alert, incident)


def process_alert(alert, incidents, obs_count):
    best_incident = None
    best_score = 0.0

    # Determine threshold based on active scoring mode
    threshold = ML_THRESHOLD if USE_ML_MODEL else INCIDENT_THRESHOLD
    mode_label = "XGB-ML" if USE_ML_MODEL else "RULE"

    # If no open incidents → create new immediately
    if not incidents:
        incident_id = str(uuid.uuid4())
        reasoning = generate_reasoning(
            alert=alert,
            incident_id=incident_id,
            score=0.0,
            is_new=True
        )

        print("-" * 60)
        print(f"INCIDENT ID : {incident_id}")
        print(f"OBS COUNT   : {obs_count}")
        print(f"MODE        : {mode_label}")
        print(f"SIGNAL      : {alert['event_type']} | Sev={alert['severity']} | conf={alert['confidence']} | {alert['area']}")
        print(f"SCORE       : 0.0")
        print(f"MERGED      : NO (New Incident)")
        print(f"REASONING   : {reasoning.strip()}")
        print("-" * 60)

        return incident_id, True, 0.0, reasoning

    # Compare with every existing open incident
    for inc in incidents:
        score = _get_score(alert, inc)
        print(f"[DEBUG] [{mode_label}] Comparing with incident {inc['incident_id']} → score = {score:.4f}")

        if score > best_score:
            best_score = score
            best_incident = inc

    # Merge decision
    if best_score >= threshold:
        incident_id = best_incident["incident_id"]
        is_new = False
    else:
        incident_id = str(uuid.uuid4())
        is_new = True

    reasoning = generate_reasoning(
        alert=alert,
        incident_id=incident_id,
        score=best_score,
        is_new=is_new
    )

    print("-" * 60)
    print(f"INCIDENT ID : {incident_id}")
    print(f"OBS COUNT   : {obs_count}")
    print(f"MODE        : {mode_label}")
    print(f"SIGNAL      : {alert['event_type']} | Sev={alert['severity']} | conf={alert['confidence']} | {alert['area']}")
    print(f"SCORE       : {best_score:.4f}")
    print(f"THRESHOLD   : {threshold}")
    print(f"MERGED      : {'NO (New Incident)' if is_new else 'YES (Existing Incident)'}")
    print(f"REASONING   : {reasoning.strip()}")
    print("-" * 60)

    return incident_id, is_new, best_score, reasoning