from config import WEIGHTS


def compute_score(alert, incident):
    score = 0.0

    score += WEIGHTS["temporal"] * 1.0
    score += WEIGHTS["spatial"] * (1.0 if alert["area"] == incident["area"] else 0.0)
    score += WEIGHTS["semantic"] * (1.0 if alert["event_type"] == incident["event_type"] else 0.5)
    score += WEIGHTS["source"] * (1.0 if alert["source_id"] == incident["source_id"] else 0.0)
    score += WEIGHTS["severity"] * min(alert["severity"] / 10.0, 1.0)

    return round(float(score), 2)