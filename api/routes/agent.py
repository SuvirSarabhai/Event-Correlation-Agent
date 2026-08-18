from fastapi import APIRouter
from sqlalchemy import text

from db import SessionLocal
from api.schemas import AgentStatusOut

router = APIRouter()


@router.get("/agent/status", response_model=AgentStatusOut)
def get_agent_status():
    try:
        with SessionLocal() as session:
            alerts_pending = session.execute(text(
                "SELECT COUNT(*) FROM alerts WHERE processed = false"
            )).scalar() or 0

            last_processed = session.execute(text(
                "SELECT MAX(updated_at) FROM incidents"
            )).scalar()

            total_processed = session.execute(text(
                "SELECT COUNT(*) FROM alerts WHERE processed = true"
            )).scalar() or 0

            return AgentStatusOut(
                db_connected=True,
                alerts_pending=alerts_pending,
                last_processed=last_processed,
                total_processed=total_processed,
            )
    except Exception:
        return AgentStatusOut(
            db_connected=False,
            alerts_pending=0,
            last_processed=None,
            total_processed=0,
        )
