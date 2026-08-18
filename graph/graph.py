from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    fetch_alerts_node,
    fetch_incidents_node,
    score_alert_node,
    decide_node,
    reason_node,
    persist_node,
)
from graph.edges import should_continue, has_alerts


def build_graph():
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("fetch_alerts", fetch_alerts_node)
    graph.add_node("fetch_incidents", fetch_incidents_node)
    graph.add_node("score_alert", score_alert_node)
    graph.add_node("decide", decide_node)
    graph.add_node("reason", reason_node)
    graph.add_node("persist", persist_node)

    # Entry: exit early if no alerts, else begin processing loop
    graph.set_entry_point("fetch_alerts")
    graph.add_conditional_edges("fetch_alerts", has_alerts, {
        "fetch_incidents": "fetch_incidents",
        END: END,
    })
    graph.add_edge("fetch_incidents", "score_alert")
    graph.add_edge("score_alert", "decide")
    graph.add_edge("decide", "reason")
    graph.add_edge("reason", "persist")

    # Loop back or end
    graph.add_conditional_edges("persist", should_continue, {
        "fetch_incidents": "fetch_incidents",
        END: END,
    })

    return graph.compile()


app = build_graph()
