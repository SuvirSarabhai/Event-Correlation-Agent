from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class AlertOut(BaseModel):
    alert_id: UUID          # PostgreSQL returns UUID objects; FastAPI serialises to str in JSON
    event_type: str
    area: str
    severity: int
    confidence: float
    processed: bool
    source_id: str
    geo_lat: Optional[float] = None
    geo_lng: Optional[float] = None
    created_at: datetime
    incident_id: Optional[UUID] = None
    correlation_score: Optional[float] = None

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    event_type: str
    area: str
    severity: int
    confidence: float
    source_id: str
    geo_lat: Optional[float] = None
    geo_lng: Optional[float] = None


class IncidentOut(BaseModel):
    incident_id: UUID       # PostgreSQL returns UUID objects; FastAPI serialises to str in JSON
    status: str
    alert_count: int
    area: str
    severity: int
    confidence: float
    first_seen: datetime
    last_seen: datetime
    explanation: Optional[str] = None
    event_type: Optional[str] = None
    geo_lat: Optional[float] = None
    geo_lng: Optional[float] = None

    model_config = {"from_attributes": True}


class IncidentDetailOut(IncidentOut):
    alerts: list[AlertOut] = []


class SeverityBreakdown(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class StatsOut(BaseModel):
    incidents_today: int
    incidents_week: int
    alerts_processed: int
    alerts_pending: int
    severity_breakdown: SeverityBreakdown


class AgentStatusOut(BaseModel):
    db_connected: bool
    alerts_pending: int
    last_processed: Optional[datetime] = None
    total_processed: int
