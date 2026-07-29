"""Explicit-runtime orchestration for deterministic Screen 2 agent blocks."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, List, Optional

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


def initialize_screen2_state_defaults(state: StateDict) -> List[str]:
    """Initialize missing Screen 2 state keys and return the keys added."""

    defaults = {
        "messages": [],
        "criterion_answers": {},
        "criterion_result_map": {},
        "criterion_trace_map": {},
        "criterion_ui_map": {},
        "logic_evaluation": {},
        "screen_2_payload": {},
        "screen_2_review_tool_input": {},
        "screen_2_review_result": {},
    }
    initialized: List[str] = []
    for key, value in defaults.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, (dict, list)) else value
            initialized.append(key)
    return initialized


def _parse_reasoning_result(raw_result: Any) -> tuple[Dict[str, Any], Optional[str]]:
    try:
        if isinstance(raw_result, str):
            parsed_result = json.loads(raw_result)
        elif isinstance(raw_result, dict) and isinstance(raw_result.get("text"), str):
            parsed_result = json.loads(raw_result["text"])
        elif isinstance(raw_result, dict):
            parsed_result = raw_result
        else:
            parsed_result = {}
    except Exception as exc:  # pragma: no cover - defensive for DSS runtime
        return {}, str(exc)

    return (parsed_result if isinstance(parsed_result, dict) else {}), None


def accumulate_current_reasoning_result(
    state: StateDict,
    scratchpad: ScratchpadDict,
    trace: Any = None,
) -> None:
    """Persist one criterion trace and merge its raw reasoning result into state."""

    current_result = scratchpad.get("current_reasoning_result")
    current_plan_item = scratchpad.get("current_plan_item", {}) or {}
    selected_scope_context = get_selected_scope_context(state)
    parsed_result, parse_error = _parse_reasoning_result(current_result)

    cluster_id = selected_scope_context.get("selected_cluster_id")
    cluster_label = (
        (selected_scope_context.get("selected_cluster_summary") or {}).get("condition_label")
        or (selected_scope_context.get("selected_cluster") or {}).get("condition_label")
        or (selected_scope_context.get("selected_cluster") or {}).get("label")
    )
    current_plan_criterion_id = current_plan_item.get("criterion_id")
    criterion_id = parsed_result.get("criterion_id")
    structured_count = len((parsed_result.get("sources", {}) or {}).get("structured", []))
    note_count = len((parsed_result.get("sources", {}) or {}).get("notes", []))

    if trace:
        with trace.subspan(
            f"accumulate_result:{criterion_id or current_plan_criterion_id or 'UNKNOWN'}"
        ) as span:
            span.attributes["selected_cluster_id"] = cluster_id
            span.attributes["selected_cluster_label"] = cluster_label
            span.attributes["plan_item_criterion_id"] = current_plan_criterion_id
            span.attributes["result_criterion_id"] = criterion_id
            span.outputs["parsed_result"] = parsed_result
            span.outputs["trace_summary"] = {
                "criterion_id": criterion_id,
                "status": parsed_result.get("status"),
                "meets_criterion": parsed_result.get("meets_criterion"),
                "structured_source_count": structured_count,
                "note_source_count": note_count,
                "parse_error": parse_error,
            }
            span.outputs["accumulation_status"] = (
                "merged" if criterion_id else "skipped_missing_criterion_id"
            )

    messages = state.setdefault("messages", [])
    if not isinstance(messages, list):
        messages = []
        state["messages"] = messages

    if not criterion_id:
        messages.append(
            f"Missing criterion_id while accumulating result for cluster {cluster_id}."
        )
        scratchpad["current_reasoning_result"] = {}
        return

    state.setdefault("criterion_trace_map", {})
    state["criterion_trace_map"][criterion_id] = {
        "trace_schema_version": "criterion_trace_v1",
        "plan_item": deepcopy(current_plan_item),
        "raw_reasoning_result": deepcopy(parsed_result),
        "accumulation": {
            "plan_item_criterion_id": current_plan_criterion_id,
            "result_criterion_id": criterion_id,
            "parse_error": parse_error,
        },
    }
    state.setdefault("criterion_result_map", {})
    state["criterion_result_map"][criterion_id] = parsed_result
    messages.append(f"Processed criterion {criterion_id} for cluster {cluster_id}.")
    scratchpad["current_reasoning_result"] = {}


def evaluate_logic_tree_from_state(state: StateDict, trace: Any = None) -> None:
    """Compute and persist the selected-scope logic evaluation."""

    selected_scope_context = get_selected_scope_context(state)
    criterion_result_map = state.get("criterion_result_map", {}) or {}
    logic_evaluation = evaluate_logic_tree(selected_scope_context, criterion_result_map)
    state["logic_evaluation"] = logic_evaluation

    if trace:
        with trace.subspan("evaluate_logic_tree") as span:
            span.attributes["selected_cluster_id"] = selected_scope_context.get(
                "selected_cluster_id"
            )
            span.attributes["criterion_result_count"] = len(criterion_result_map)
            span.outputs["logic_evaluation"] = logic_evaluation


def build_criterion_ui_map_from_state(state: StateDict, trace: Any = None) -> None:
    """Build and persist the deterministic Screen 2 UI view model."""

    selected_scope_context = get_selected_scope_context(state)
    criterion_ui_map = build_criterion_ui_map_data(
        selected_scope_context=selected_scope_context,
        criterion_result_map=state.get("criterion_result_map", {}),
        criterion_answers=state.get("criterion_answers", {}),
        retrieval_plan=state.get("retrieval_plan_v1"),
    )
    state["criterion_ui_map"] = criterion_ui_map

    if trace:
        with trace.subspan("build_criterion_ui_map") as span:
            span.attributes["selected_cluster_id"] = selected_scope_context.get(
                "selected_cluster_id"
            )
            span.outputs["criterion_count"] = len(criterion_ui_map)


def build_screen2_payload_from_state(state: StateDict, trace: Any = None) -> Dict[str, Any]:
    """Build and persist the Screen 2 payload, creating a missing UI map first."""

    if not isinstance(state.get("criterion_ui_map"), dict) or not state.get("criterion_ui_map"):
        build_criterion_ui_map_from_state(state, trace)

    payload = build_screen2_payload_data(state)
    state["screen_2_payload"] = payload

    if trace:
        with trace.subspan("build_screen_2_payload") as span:
            span.outputs["status"] = payload.get("status")
            span.outputs["next_action"] = (payload.get("payload", {}) or {}).get(
                "next_action"
            )
    return payload


def prepare_screen2_review_payload(state: StateDict, trace: Any = None) -> None:
    """Build the Screen 2 payload and managed-review tool input from state."""

    build_screen2_payload_from_state(state, trace)
    state["screen_2_review_tool_input"] = build_screen2_review_tool_input_data(state)
    state.setdefault("screen_2_review_result", {})

    if trace:
        with trace.subspan("prepare_screen_2_review_payload") as span:
            tool_input = state["screen_2_review_tool_input"]
            span.outputs["has_screen_2_payload"] = bool(tool_input.get("screen_2_payload"))
            span.outputs["criterion_answer_count"] = len(
                tool_input.get("criterion_answers", {}) or {}
            )
            span.outputs["selected_scope"] = tool_input.get("selected_scope", {})
