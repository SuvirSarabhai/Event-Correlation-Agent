import uuid
from scoring import compute_score
from reasoning import generate_reasoning
from config import INCIDENT_THRESHOLD


def process_alert(alert, incidents, obs_count):
    best_incident = None
    best_score = 0.0

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
        print(f"SIGNAL      : {alert['event_type']} | Sev={alert['severity']} | conf={alert['confidence']} | {alert['area']}")
        print(f"SCORE       : 0.0")
        print(f"MERGED      : NO (New Incident)")
        print(f"REASONING   : {reasoning.strip()}")
        print("-" * 60)

        return incident_id, True, 0.0, reasoning

    # Compare with existing incidents
    for inc in incidents:
        score = compute_score(alert, inc)
        print(f"[DEBUG] Comparing alert with incident {inc['incident_id']} → score = {score}")

        if score > best_score:
            best_score = score
            best_incident = inc

    # Decision based purely on threshold
    if best_score >= INCIDENT_THRESHOLD:
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
    print(f"SIGNAL      : {alert['event_type']} | Sev={alert['severity']} | conf={alert['confidence']} | {alert['area']}")
    print(f"SCORE       : {best_score}")
    print(f"MERGED      : {'NO (New Incident)' if is_new else 'YES (Existing Incident)'}")
    print(f"REASONING   : {reasoning.strip()}")
    print("-" * 60)

    return incident_id, is_new, best_score, reasoning