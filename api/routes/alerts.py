import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from db import SessionLocal
from api.schemas import AlertOut, AlertCreate

router = APIRouter()


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    processed: Optional[bool] = Query(None),
    area: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    with SessionLocal() as session:
        query = "SELECT * FROM alerts WHERE 1=1"
        params: dict = {}

        if processed is not None:
            query += " AND processed = :processed"
            params["processed"] = processed
        if area:
            query += " AND area ILIKE :area"
            params["area"] = f"%{area}%"
        if event_type:
            query += " AND event_type ILIKE :event_type"
            params["event_type"] = f"%{event_type}%"

        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        rows = session.execute(text(query), params).mappings().all()
        return [dict(r) for r in rows]


@router.post("/alerts", response_model=AlertOut, status_code=201)
def create_alert(body: AlertCreate):
    alert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with SessionLocal() as session:
        session.execute(
            text("""
                INSERT INTO alerts
                    (alert_id, event_type, area, severity, confidence,
                     source_id, geo_lat, geo_lng, processed, created_at)
                VALUES
                    (:alert_id, :event_type, :area, :severity, :confidence,
                     :source_id, :geo_lat, :geo_lng, false, :created_at)
            """),
            {
                "alert_id":   alert_id,
                "event_type": body.event_type,
                "area":       body.area,
                "severity":   body.severity,
                "confidence": body.confidence,
                "source_id":  body.source_id,
                "geo_lat":    body.geo_lat,
                "geo_lng":    body.geo_lng,
                "created_at": now,
            },
        )
        session.commit()

        row = session.execute(
            text("SELECT * FROM alerts WHERE alert_id = :id"),
            {"id": alert_id},
        ).mappings().one()
        return dict(row)
