from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from db import SessionLocal
from api.schemas import IncidentOut, IncidentDetailOut

router = APIRouter()


@router.get("/incidents", response_model=list[IncidentOut])
def get_incidents(status: Optional[str] = Query(None)):
    with SessionLocal() as session:
        query = "SELECT * FROM incidents WHERE 1=1"
        params: dict = {}

        if status:
            query += " AND LOWER(status) = LOWER(:status)"
            params["status"] = status

        query += " ORDER BY first_seen DESC"
        rows = session.execute(text(query), params).mappings().all()
        return [dict(r) for r in rows]


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: str):
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT * FROM incidents WHERE incident_id = :id"),
            {"id": incident_id},
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")

        alert_rows = session.execute(
            text("SELECT * FROM alerts WHERE incident_id = :id ORDER BY created_at"),
            {"id": incident_id},
        ).mappings().all()

        incident = dict(row)
        incident["alerts"] = [dict(a) for a in alert_rows]
        return incident
