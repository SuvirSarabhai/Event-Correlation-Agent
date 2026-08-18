from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import DB_URL, MAX_OBSERVATIONS

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


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


# ✅ UPDATED: update_incident keeps original context but updates explanation
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
        "id": incident_id,
        "ts": alert["created_at"],
        "sev": alert["severity"],
        "conf": alert["confidence"],
        "exp": explanation
    })


def update_alert(session, alert_id, incident_id):
    session.execute(text("""
        UPDATE alerts
        SET processed = true,
            incident_id = :iid
        WHERE alert_id = :aid
    """), {
        "aid": alert_id,
        "iid": incident_id
    })
    session.commit()