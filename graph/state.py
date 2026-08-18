from typing import TypedDict


class AgentState(TypedDict):
    alerts:          list    # all unprocessed alerts fetched from DB
    current_alert:   dict    # alert currently being processed
    incidents:       list    # open incidents fetched from DB
    obs_count:       int     # 1-based counter of alerts processed
    incident_id:     str     # decided incident UUID
    is_new:          bool    # True = create new incident, False = merge
    score:           float   # best correlation score found
    reasoning:       str     # LLM-generated explanation
    alert_index:     int     # which alert we are currently processing
    alert_embedding: list    # Gemini embedding for current alert (used by persist_node)
