import os
from dotenv import load_dotenv

# Load .env when running locally; env vars set in ECS task definition take precedence
load_dotenv(override=False)

# ── Database ───────────────────────────────────────────────────────────────────
# CockroachDB Serverless connection string.
# Set COCKROACHDB_URL in .env (local) or ECS task definition (cloud).
DB_URL = os.environ["COCKROACHDB_URL"]

# ── Agent tuning ───────────────────────────────────────────────────────────────
INCIDENT_THRESHOLD = 0.70
MAX_OBSERVATIONS   = 5    # alerts processed per batch
POLL_INTERVAL      = 10   # seconds to wait between DB polls when no new alerts

WEIGHTS = {
    "temporal": 0.30,
    "spatial":  0.25,
    "semantic": 0.20,
    "source":   0.15,
    "severity": 0.10,
}

# ── Gemini Configuration ───────────────────────────────────────────────────────
# Set GEMINI_API_KEY in .env (local) or ECS task definition (cloud).
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
GEMINI_LLM_MODEL  = "gemini-2.0-flash"
GEMINI_EMBED_MODEL = "models/text-embedding-004"
EMBED_DIMENSION   = 768   # text-embedding-004 output dimension

# ── ML Model Configuration ─────────────────────────────────────────────────────
# Set to True to use the trained XGBoost model for correlation scoring.
# Set to False to fall back to the original rule-based weighted scoring.
USE_ML_MODEL = True

# Probability threshold for the XGBoost model merge decision (0.0 – 1.0).
ML_THRESHOLD = 0.70

# ── Debug / Logging ────────────────────────────────────────────────────────────
# Set to True to print per-pair feature values during scoring.
DEBUG_FEATURES = True