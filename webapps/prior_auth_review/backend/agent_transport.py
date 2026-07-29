"""Pure helpers for reading Structured Agent state from DSS completion context."""

from typing import Any, Optional

from scripts.agent_flow.functions.screen_payload_helpers import normalize_review_result_data


def extract_graph_state(value: Any) -> Optional[dict]:
    """Find the Structured Agent block-graph state in a DSS context envelope."""
    if not isinstance(value, dict):
        return None

    if "_currentBlockId" in value:
        return value

    context = value.get("context")
    if isinstance(context, dict):
        graph_state = extract_graph_state(context)
        if graph_state is not None:
            return graph_state

    for nested in value.values():
        if isinstance(nested, dict) and "_currentBlockId" in nested:
            return nested

    event_data = value.get("eventData")
    if isinstance(event_data, dict):
        context = event_data.get("context")
        if isinstance(context, dict):
            return extract_graph_state(context)
    return None


def extract_review_result_from_graph(graph_state: Any) -> Optional[dict]:
    """Return the reviewed Screen 2 artifact persisted by the Structured Agent."""
    if not isinstance(graph_state, dict):
        return None

    review_result = normalize_review_result_data(graph_state.get("screen_2_review_result"))
    return review_result or None
