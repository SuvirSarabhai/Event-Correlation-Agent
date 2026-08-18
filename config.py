DB_URL = "postgresql+psycopg2://postgres:password@localhost:5432/AGENT"

INCIDENT_THRESHOLD = 0.70
MAX_OBSERVATIONS = 5    # alerts processed per batch
POLL_INTERVAL     = 10  # seconds to wait between DB polls when no new alerts

WEIGHTS = {
    "temporal": 0.30,
    "spatial": 0.25,
    "semantic": 0.20,
    "source": 0.15,
    "severity": 0.10
}

OLLAMA_MODEL = "llama3"

# ──────────────────────────────────────────
# ML Model Configuration
# ──────────────────────────────────────────
# Set to True to use the trained XGBoost model for correlation scoring.
# Set to False to fall back to the original rule-based weighted scoring.
USE_ML_MODEL = True

# Probability threshold for the XGBoost model merge decision (0.0 – 1.0).
# An alert pair with predicted probability >= ML_THRESHOLD will be merged.
ML_THRESHOLD = 0.70

# ──────────────────────────────────────────
# Debug / Logging
# ──────────────────────────────────────────
# Set to True to print per-pair feature values during scoring (useful for
# debugging model behaviour). Set to False in production to reduce noise.
DEBUG_FEATURES = True