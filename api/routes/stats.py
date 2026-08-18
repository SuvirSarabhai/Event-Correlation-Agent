from fastapi import APIRouter
from sqlalchemy import text

from db import SessionLocal
from api.schemas import StatsOut, SeverityBreakdown

router = APIRouter()


@router.get("/stats", response_model=StatsOut)
def get_stats():
    with SessionLocal() as session:
        incidents_today = session.execute(text(
            "SELECT COUNT(*) FROM incidents WHERE DATE(first_seen) = CURRENT_DATE"
        )).scalar() or 0

        incidents_week = session.execute(text(
            "SELECT COUNT(*) FROM incidents "
            "WHERE first_seen >= CURRENT_DATE - INTERVAL '7 days'"
        )).scalar() or 0

        alerts_processed = session.execute(text(
            "SELECT COUNT(*) FROM alerts WHERE processed = true"
        )).scalar() or 0

        alerts_pending = session.execute(text(
            "SELECT COUNT(*) FROM alerts WHERE processed = false"
        )).scalar() or 0

        sev = session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE severity > 7)              AS critical,
                COUNT(*) FILTER (WHERE severity BETWEEN 6 AND 7)  AS high,
                COUNT(*) FILTER (WHERE severity BETWEEN 4 AND 5)  AS medium,
                COUNT(*) FILTER (WHERE severity <= 3)             AS low
            FROM incidents
        """)).mappings().one()

        return StatsOut(
            incidents_today=incidents_today,
            incidents_week=incidents_week,
            alerts_processed=alerts_processed,
            alerts_pending=alerts_pending,
            severity_breakdown=SeverityBreakdown(
                critical=sev["critical"] or 0,
                high=sev["high"] or 0,
                medium=sev["medium"] or 0,
                low=sev["low"] or 0,
            ),
        )
