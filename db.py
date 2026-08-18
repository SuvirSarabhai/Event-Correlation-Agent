from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DB_URL, MAX_OBSERVATIONS, EMBED_DIMENSION

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


# ── Core CRUD ─────────────────────────────────────────────────────────────────

def fetch_unprocessed_alerts(session, limit=MAX_OBSERVATIONS):
    return session.execute(text("""
        SELECT *
        FROM alerts
        WHERE processed = false
        ORDER BY created_at
        LIMIT :limit
    """), {"limit": limit}).mappings().all()


def fetch_open_incidents(session):
    return session.execute(text("""
        SELECT *
        FROM incidents
        WHERE status = 'open'
    """)).mappings().all()


def create_incident(session, incident_id, alert, explanation):
    session.execute(text("""
        INSERT INTO incidents (
            incident_id, status, first_seen, last_seen,
            severity, confidence, alert_count,
            created_at, updated_at, explanation,
            area, source_id, event_type,
            geo_lat, geo_lng
        )
        VALUES (
            :id, 'open', :ts, :ts,
            :sev, :conf, 1,
            :ts, :ts, :exp,
            :area, :source, :event,
            :geo_lat, :geo_lng
        )
    """), {
        "id":      incident_id,
        "ts":      alert["created_at"],
        "sev":     alert["severity"],
        "conf":    alert["confidence"],
        "exp":     explanation,
        "area":    alert["area"],
        "source":  alert["source_id"],
        "event":   alert["event_type"],
        "geo_lat": alert.get("geo_lat"),
        "geo_lng": alert.get("geo_lng"),
    })


def update_incident(session, incident_id, alert, explanation):
    session.execute(text("""
        UPDATE incidents
        SET last_seen = :ts,
            severity = GREATEST(severity, :sev),
            confidence = (confidence + :conf) / 2,
            alert_count = alert_count + 1,
            updated_at = :ts,
            explanation = :exp
        WHERE incident_id = :id
    """), {
        "id":   incident_id,
        "ts":   alert["created_at"],
        "sev":  alert["severity"],
        "conf": alert["confidence"],
        "exp":  explanation,
    })


def update_alert(session, alert_id, incident_id):
    session.execute(text("""
        UPDATE alerts
        SET processed = true,
            incident_id = :iid
        WHERE alert_id = :aid
    """), {
        "aid": alert_id,
        "iid": incident_id,
    })
    session.commit()


# ── CockroachDB Vector Indexing ───────────────────────────────────────────────

def ensure_vector_schema(session):
    """
    Add the embedding VECTOR column and a vector index to the incidents table
    if they don't already exist. Safe to call on every startup.
    """
    # Step 1: add column
    try:
        session.execute(text(f"""
            ALTER TABLE incidents
            ADD COLUMN IF NOT EXISTS embedding VECTOR({EMBED_DIMENSION})
        """))
        session.commit()
        print(f"[VECTOR] embedding column ready (VECTOR({EMBED_DIMENSION}))")
    except Exception as e:
        session.rollback()
        print(f"[VECTOR] Column setup note: {e}")

    # Step 2: create vector index (CockroachDB distributed vector index)
    try:
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_incidents_embedding
            ON incidents USING ivfflat (embedding vector_cosine_ops)
        """))
        session.commit()
        print("[VECTOR] Vector index ready (ivfflat / cosine)")
    except Exception as e:
        session.rollback()
        print(f"[VECTOR] Index setup note: {e}")


def store_embedding(session, incident_id: str, embedding: list[float]):
    """
    Persist the vector embedding for an incident.
    Called after create_incident or update_incident.
    """
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    try:
        session.execute(text(f"""
            UPDATE incidents
            SET embedding = '{vec_literal}'::vector
            WHERE incident_id = :id
        """), {"id": incident_id})
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[VECTOR] Failed to store embedding for {incident_id}: {e}")


def find_similar_incidents(session, embedding: list[float], limit: int = 3) -> list[dict]:
    """
    Return the top-k most semantically similar open incidents using
    CockroachDB's distributed vector index and cosine distance (<=>).
    Falls back to empty list if vector search is unavailable.
    """
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    try:
        rows = session.execute(text(f"""
            SELECT incident_id, event_type, area, alert_count, explanation,
                   embedding <=> '{vec_literal}'::vector AS distance
            FROM incidents
            WHERE status = 'open'
              AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[VECTOR] Similarity search failed (will skip memory context): {e}")
        return []