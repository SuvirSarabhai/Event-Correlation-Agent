from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, incidents, stats, agent

app = FastAPI(
    title="Correlation Agent API",
    version="1.0.0",
    description="REST API for the Incident Correlation Agent backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts.router,    prefix="/api", tags=["Alerts"])
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
app.include_router(stats.router,     prefix="/api", tags=["Stats"])
app.include_router(agent.router,     prefix="/api", tags=["Agent"])


@app.get("/")
def root():
    return {"status": "Correlation Agent API is running", "docs": "/docs"}
