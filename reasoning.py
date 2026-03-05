import ollama
from config import OLLAMA_MODEL


def generate_reasoning(alert, incident_id, score, is_new):
    decision = "NEW INCIDENT CREATED" if is_new else "MERGED INTO EXISTING INCIDENT"

    prompt = f"""
You are an incident correlation explanation generator.

IMPORTANT:
- Do NOT invent facts.
- Use ONLY the provided alert details and correlation score.
- If event types differ, explicitly mention that.
- Be technical and concise (max 3 sentences).

Alert:
Event Type: {alert['event_type']}
Severity: {alert['severity']}
Confidence: {alert['confidence']}
Area: {alert['area']}
Source: {alert['source_id']}

Incident ID: {incident_id}
Correlation Score: {score}
Decision: {decision}

Explain why this alert was { "created as a new incident" if is_new else "merged with an existing incident" }.
"""

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={
            "temperature": 0.0
        }
    )

    return response["message"]["content"]