from db import (
    SessionLocal,
    fetch_unprocessed_alerts,
    fetch_open_incidents,
    create_incident,
    update_incident,
    update_alert,
)

from agent import process_alert


def main():
    with SessionLocal() as session:
        alerts = fetch_unprocessed_alerts(session)

    print(f"\n[START] Alerts to process: {len(alerts)}\n")

    obs_count = 0

    for alert in alerts:
        obs_count += 1

        # Fetch open incidents
        with SessionLocal() as session:
            incidents = fetch_open_incidents(session)

        # Agent processing (returns explanation now)
        incident_id, is_new, score, reasoning = process_alert(
            alert, incidents, obs_count
        )

        # Persist results
        with SessionLocal() as session:
            if is_new:
                create_incident(session, incident_id, alert, reasoning)
            else:
                update_incident(session, incident_id, alert, reasoning)

            update_alert(session, alert["alert_id"], incident_id)


if __name__ == "__main__":
    main()