import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_LLM_MODEL

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_LLM_MODEL)


def generate_reasoning(alert, incident_id, score, is_new, memory_context=""):
    decision = "NEW INCIDENT CREATED" if is_new else "MERGED INTO EXISTING INCIDENT"

    memory_section = ""
    if memory_context:
        memory_section = f"\n\nRelevant past incidents retrieved from semantic memory:\n{memory_context}"

    prompt = f"""
You are an incident correlation explanation generator.

IMPORTANT:
- Do NOT invent facts.
- Use ONLY the provided alert details, correlation score, and memory context below.
- If event types differ, explicitly mention that.
- If memory context is provided, reference it briefly to ground your explanation.
- Be technical and concise (max 3 sentences).

Alert:
Event Type: {alert['event_type']}
Severity: {alert['severity']}
Confidence: {alert['confidence']}
Area: {alert['area']}
Source: {alert['source_id']}

Incident ID: {incident_id}
Correlation Score: {score}
Decision: {decision}{memory_section}

Explain why this alert was { "created as a new incident" if is_new else "merged with an existing incident" }.
"""

    response = _model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.0),
    )
    return response.text