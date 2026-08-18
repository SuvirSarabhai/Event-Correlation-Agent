import uuid
from graph.state import AgentState
from db import (
    SessionLocal,
    fetch_unprocessed_alerts,
    fetch_open_incidents,
    create_incident,
    update_incident,
    update_alert,
    find_similar_incidents,
    store_embedding,
)
from scoring import compute_score
from reasoning import generate_reasoning
from config import INCIDENT_THRESHOLD, USE_ML_MODEL, ML_THRESHOLD
from ml.embeddings import embed_text

if USE_ML_MODEL:
    from ml.predictor import get_predictor

# Active threshold depends on scoring mode
_THRESHOLD = ML_THRESHOLD if USE_ML_MODEL else INCIDENT_THRESHOLD


def _get_score(alert: dict, incident: dict) -> float:
    """Return a correlation score respecting the USE_ML_MODEL config flag."""
    if USE_ML_MODEL:
        predictor = get_predictor()
        incident_as_alert = {
            "created_at": incident.get("created_at"),
            "area":       incident.get("area"),
            "source_id":  incident.get("source_id"),
            "event_type": incident.get("event_type"),
            "severity":   incident.get("severity"),
            "confidence": incident.get("confidence", 1.0),
            "geo_lat":    incident.get("geo_lat"),
            "geo_lng":    incident.get("geo_lng"),
        }
        return predictor.predict_proba(alert, incident_as_alert)
    return compute_score(alert, incident)


def fetch_alerts_node(state: AgentState) -> dict:
    """Fetch all unprocessed alerts from the DB."""
    with SessionLocal() as session:
        alerts = fetch_unprocessed_alerts(session)

    alerts = [dict(a) for a in alerts]
    print(f"\n[START] Alerts to process: {len(alerts)}\n")
    return {"alerts": alerts, "alert_index": 0, "obs_count": 0}


def fetch_incidents_node(state: AgentState) -> dict:
    """Load the next alert and fetch current open incidents."""
    index = state["alert_index"]
    alert = dict(state["alerts"][index])

    with SessionLocal() as session:
        incidents = fetch_open_incidents(session)
    incidents = [dict(i) for i in incidents]

    return {
        "current_alert": alert,
        "incidents": incidents,
        "obs_count": state["obs_count"] + 1,
    }


def score_alert_node(state: AgentState) -> dict:
    """Score the current alert against all open incidents."""
    alert = state["current_alert"]
    incidents = state["incidents"]
    mode_label = "XGB-ML" if USE_ML_MODEL else "RULE"

    best_score = 0.0
    best_incident = None

    for inc in incidents:
        score = _get_score(alert, inc)
        print(f"[DEBUG] [{mode_label}] Comparing alert with incident {inc['incident_id']} → score = {score:.4f}")
        if score > best_score:
            best_score = score
            best_incident = inc

    return {"score": best_score, "incidents": incidents if best_incident else []}


def decide_node(state: AgentState) -> dict:
    """Decide whether to create a new incident or merge into existing."""
    incidents = state["incidents"]
    best_score = state["score"]

    if not incidents or best_score < _THRESHOLD:
        incident_id = str(uuid.uuid4())
        is_new = True
    else:
        best_incident = max(incidents, key=lambda i: _get_score(state["current_alert"], i))
        incident_id = best_incident["incident_id"]
        is_new = False

    return {"incident_id": incident_id, "is_new": is_new}


def reason_node(state: AgentState) -> dict:
    """
    1. Embed the current alert using Gemini text-embedding-004.
    2. Query CockroachDB vector index for the 3 most similar past incidents.
    3. Call Gemini Flash with that memory context to generate a grounded explanation.
    """
    alert = state["current_alert"]

    # ── Step 1: Embed current alert ──────────────────────────────────────────
    query_text = (
        f"{alert['event_type']} severity={alert['severity']} "
        f"confidence={alert['confidence']} area={alert['area']}"
    )
    alert_embedding: list[float] = []
    memory_context = ""

    try:
        alert_embedding = embed_text(query_text)

        # ── Step 2: Semantic memory retrieval from CockroachDB ───────────────
        with SessionLocal() as session:
            similar = find_similar_incidents(session, alert_embedding, limit=3)

        if similar:
            lines = []
            for s in similar:
                explanation_snippet = str(s.get("explanation") or "")[:120]
                lines.append(
                    f"  • {s['event_type']} in {s['area']} "
                    f"({s['alert_count']} alert(s)): {explanation_snippet}"
                )
            memory_context = "\n".join(lines)
            print(f"[MEMORY] Retrieved {len(similar)} similar past incident(s) from CockroachDB vector index")

    except Exception as e:
        print(f"[MEMORY] Embedding/retrieval failed (continuing without memory): {e}")

    # ── Step 3: Generate reasoning with memory context ───────────────────────
    reasoning = generate_reasoning(
        alert=alert,
        incident_id=state["incident_id"],
        score=state["score"],
        is_new=state["is_new"],
        memory_context=memory_context,
    )

    print("-" * 60)
    print(f"INCIDENT ID : {state['incident_id']}")
    print(f"OBS COUNT   : {state['obs_count']}")
    print(f"SIGNAL      : {alert['event_type']} | Sev={alert['severity']} | conf={alert['confidence']} | {alert['area']}")
    print(f"SCORE       : {state['score']}")
    print(f"MERGED      : {'NO (New Incident)' if state['is_new'] else 'YES (Existing Incident)'}")
    print(f"MEMORY CTX  : {'Yes (' + str(len(memory_context)) + ' chars)' if memory_context else 'None'}")
    print(f"REASONING   : {reasoning.strip()}")
    print("-" * 60)

    return {"reasoning": reasoning, "alert_embedding": alert_embedding}


def persist_node(state: AgentState) -> dict:
    """
    1. Write the merge/create decision to CockroachDB.
    2. Store the Gemini embedding vector alongside the incident.
    """
    alert       = state["current_alert"]
    incident_id = state["incident_id"]
    reasoning   = state["reasoning"]
    embedding   = state.get("alert_embedding", [])

    with SessionLocal() as session:
        if state["is_new"]:
            create_incident(session, incident_id, alert, reasoning)
        else:
            update_incident(session, incident_id, alert, reasoning)
        update_alert(session, alert["alert_id"], incident_id)

    # Store vector embedding in CockroachDB (separate session for clarity)
    if embedding:
        with SessionLocal() as session:
            store_embedding(session, incident_id, embedding)
        print(f"[VECTOR] Embedding stored for incident {incident_id}")

    return {"alert_index": state["alert_index"] + 1}
