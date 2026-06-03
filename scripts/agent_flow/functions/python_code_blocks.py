"""DSS Python block wrappers for Screen 2 Structured Agent flow.

Dataiku Structured Agents provide `state` and `scratchpad` as globals at block
runtime. This module keeps production block functions thin and delegates pure
transformations to focused helper modules.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from scripts.agent_flow.functions.common import (
    ScratchpadDict,
    StateDict,
    get_selected_scope_context,
)
from scripts.agent_flow.functions.logic_tree_helpers import evaluate_logic_tree
from scripts.agent_flow.functions.screen_payload_helpers import (
    build_criterion_ui_map_data,
    build_screen2_payload_data,
    build_screen2_review_tool_input_data,
)


def _resolve_state() -> StateDict:
    runtime_state = globals().get("state")
    if isinstance(runtime_state, dict):
        return runtime_state
    raise ValueError("DSS Python block state is unavailable")


def _resolve_scratchpad() -> ScratchpadDict:
    runtime_scratchpad = globals().get("scratchpad")
    if isinstance(runtime_scratchpad, dict):
        return runtime_scratchpad
    raise ValueError("DSS Python block scratchpad is unavailable")


def initialize_placeholder_state(trace: Any) -> None:
    """Initialize the minimum Screen 2 state keys needed for local simulation."""

    state = _resolve_state()
    initialized: List[str] = []
    defaults = {
        "messages": [],
        "criterion_answers": {},
        "criterion_result_map": {},
        "criterion_ui_map": {},
        "logic_evaluation": {},
        "screen_2_payload": {},
        "screen_2_review_tool_input": {},
        "screen_2_review_result": {},
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, (dict, list)) else value
            initialized.append(key)
    with trace.subspan("initialize_placeholder_state") as span:
        span.outputs["initialized_keys"] = initialized


def accumulate_current_reasoning_result(trace: Any) -> None:
    """Merge the current criterion reasoning result into `criterion_result_map`."""

    state = _resolve_state()
    scratchpad = _resolve_scratchpad()

    current_result = scratchpad.get("current_reasoning_result")
    current_plan_item = scratchpad.get("current_plan_item", {}) or {}
    selected_scope_context = get_selected_scope_context(state)

    cluster_id = selected_scope_context.get("selected_cluster_id")
    cluster_label = (
        (selected_scope_context.get("selected_cluster_summary") or {}).get("condition_label")
        or (selected_scope_context.get("selected_cluster") or {}).get("condition_label")
        or (selected_scope_context.get("selected_cluster") or {}).get("label")
    )
    current_plan_criterion_id = current_plan_item.get("criterion_id")

    parse_error = None
    parsed_result: Dict[str, Any] = {}

    try:
        if isinstance(current_result, str):
            parsed_result = json.loads(current_result)
        elif isinstance(current_result, dict) and isinstance(current_result.get("text"), str):
            parsed_result = json.loads(current_result["text"])
        elif isinstance(current_result, dict):
            parsed_result = current_result
        else:
            parsed_result = {}
    except Exception as exc:  # pragma: no cover - defensive for DSS runtime
        parse_error = str(exc)
        parsed_result = {}

    if not isinstance(parsed_result, dict):
        parsed_result = {}

    criterion_id = parsed_result.get("criterion_id")
    status = parsed_result.get("status")
    meets_criterion = parsed_result.get("meets_criterion")
    structured_count = len((parsed_result.get("sources", {}) or {}).get("structured", []))
    note_count = len((parsed_result.get("sources", {}) or {}).get("notes", []))

    with trace.subspan(f"accumulate_result:{criterion_id or current_plan_criterion_id or 'UNKNOWN'}") as span:
        span.attributes["selected_cluster_id"] = cluster_id
        span.attributes["selected_cluster_label"] = cluster_label
        span.attributes["plan_item_criterion_id"] = current_plan_criterion_id
        span.attributes["result_criterion_id"] = criterion_id
        span.outputs["parsed_result"] = parsed_result
        span.outputs["trace_summary"] = {
            "criterion_id": criterion_id,
            "status": status,
            "meets_criterion": meets_criterion,
            "structured_source_count": structured_count,
            "note_source_count": note_count,
            "parse_error": parse_error,
        }
        span.outputs["accumulation_status"] = "merged" if criterion_id else "skipped_missing_criterion_id"

    state.setdefault("messages", [])
    if not criterion_id:
        state["messages"].append(
            f"Missing criterion_id while accumulating result for cluster {cluster_id}."
        )
        scratchpad["current_reasoning_result"] = {}
        return

    state.setdefault("criterion_result_map", {})
    state["criterion_result_map"][criterion_id] = parsed_result
    state["messages"].append(f"Processed criterion {criterion_id} for cluster {cluster_id}.")
    scratchpad["current_reasoning_result"] = {}


def evaluate_logic_tree_from_state(trace: Any) -> None:
    """Compute `logic_evaluation` from current global DSS state."""

    state = _resolve_state()
    selected_scope_context = get_selected_scope_context(state)
    criterion_result_map = state.get("criterion_result_map", {}) or {}
    logic_evaluation = evaluate_logic_tree(selected_scope_context, criterion_result_map)
    state["logic_evaluation"] = logic_evaluation

    with trace.subspan("evaluate_logic_tree") as span:
        span.attributes["selected_cluster_id"] = selected_scope_context.get("selected_cluster_id")
        span.attributes["criterion_result_count"] = len(criterion_result_map)
        span.outputs["logic_evaluation"] = logic_evaluation


def build_criterion_ui_map(trace: Any) -> None:
    """Build the deterministic webapp-facing criterion UI map from DSS state."""

    state = _resolve_state()
    selected_scope_context = get_selected_scope_context(state)
    criterion_ui_map = build_criterion_ui_map_data(
        selected_scope_context=selected_scope_context,
        criterion_result_map=state.get("criterion_result_map", {}),
        criterion_answers=state.get("criterion_answers", {}),
    )
    state["criterion_ui_map"] = criterion_ui_map

    with trace.subspan("build_criterion_ui_map") as span:
        span.attributes["selected_cluster_id"] = selected_scope_context.get("selected_cluster_id")
        span.outputs["criterion_count"] = len(criterion_ui_map)


def build_screen2_payload(trace: Any) -> None:
    """Build and persist the Screen 2 review payload from DSS state."""

    state = _resolve_state()
    if not isinstance(state.get("criterion_ui_map"), dict) or not state.get("criterion_ui_map"):
        state["criterion_ui_map"] = build_criterion_ui_map_data(
            selected_scope_context=get_selected_scope_context(state),
            criterion_result_map=state.get("criterion_result_map", {}),
            criterion_answers=state.get("criterion_answers", {}),
        )

    payload = build_screen2_payload_data(state)
    state.setdefault("screen_2_payload", {})
    state["screen_2_payload"] = payload

    with trace.subspan("build_screen_2_payload") as span:
        span.outputs["status"] = payload.get("status")
        span.outputs["next_action"] = (
            payload.get("payload", {}) or {}
        ).get("next_action")


def prepare_screen2_review_payload(trace: Any) -> None:
    """Build Screen 2 payload and the approval-tool input from DSS state."""

    state = _resolve_state()
    build_screen2_payload(trace)
    state.setdefault("screen_2_review_tool_input", {})
    state["screen_2_review_tool_input"] = build_screen2_review_tool_input_data(state)

    with trace.subspan("prepare_screen_2_review_payload") as span:
        tool_input = state["screen_2_review_tool_input"]
        span.outputs["has_screen_2_payload"] = bool(tool_input.get("screen_2_payload"))
        span.outputs["criterion_answer_count"] = len(tool_input.get("criterion_answers", {}) or {})
        span.outputs["selected_scope"] = tool_input.get("selected_scope", {})
