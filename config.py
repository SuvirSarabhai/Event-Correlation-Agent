DB_URL = "postgresql+psycopg2://postgres:password@localhost:5432/AGENT"

INCIDENT_THRESHOLD = 0.70
MAX_OBSERVATIONS = 5

WEIGHTS = {
    "temporal": 0.30,
    "spatial": 0.25,
    "semantic": 0.20,
    "source": 0.15,
    "severity": 0.10
}

OLLAMA_MODEL = "llama3"