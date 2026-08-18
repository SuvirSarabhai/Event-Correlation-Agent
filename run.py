import time
import sys
from graph.graph import app
from db import SessionLocal, ensure_vector_schema
from config import POLL_INTERVAL


def run_batch() -> int:
    """Run one full pass: fetch → score → decide → reason → persist.
    Returns the number of alerts processed in this pass."""
    initial_state = {
        "alerts":          [],
        "current_alert":   {},
        "incidents":       [],
        "obs_count":       0,
        "incident_id":     "",
        "is_new":          False,
        "score":           0.0,
        "reasoning":       "",
        "alert_index":     0,
        "alert_embedding": [],   # Gemini embedding carried between reason → persist
    }
    result = app.invoke(initial_state)
    return result["obs_count"]


def main():
    print("[AGENT] Correlation agent started. Press Ctrl+C to stop.\n")

    # Ensure CockroachDB vector schema is ready before the main loop
    print("[AGENT] Initialising CockroachDB vector schema...")
    with SessionLocal() as session:
        ensure_vector_schema(session)
    print("[AGENT] Schema ready.\n")

    total_processed = 0

    try:
        while True:
            batch_count = run_batch()

            if batch_count > 0:
                total_processed += batch_count
                print(f"[AGENT] Batch complete — {batch_count} alert(s) processed "
                      f"(total: {total_processed}). Checking for more...\n")
                # Don't sleep — immediately drain any remaining alerts
            else:
                # No alerts left — sleep before next poll
                print(f"[AGENT] No new alerts. Sleeping {POLL_INTERVAL}s...", end="\r")
                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n[AGENT] Stopped. Total alerts processed this session: {total_processed}")
        sys.exit(0)


if __name__ == "__main__":
    main()