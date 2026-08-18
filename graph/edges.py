from langgraph.graph import END
from graph.state import AgentState


def has_alerts(state: AgentState) -> str:
    """After fetch_alerts: proceed only if there are unprocessed alerts."""
    if state["alerts"]:
        return "fetch_incidents"
    print("[DONE] No unprocessed alerts found in the database.")
    return END


def should_continue(state: AgentState) -> str:
    """Route back to fetch_incidents if more alerts remain, else END."""
    if state["alert_index"] < len(state["alerts"]):
        return "fetch_incidents"
    return END
