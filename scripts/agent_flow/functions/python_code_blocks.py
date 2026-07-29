"""Compatibility wrappers for local simulation of DSS Screen 2 Python blocks.

Production DSS blocks should call the explicit-runtime functions in
``screen2_agent_runtime`` directly. These wrappers retain the historical local
simulation interface, where DSS globals are emulated in this module.
"""

from __future__ import annotations

from typing import Any

from scripts.agent_flow.functions.common import ScratchpadDict, StateDict
from scripts.agent_flow.functions.screen2_agent_runtime import (
    accumulate_current_reasoning_result as _accumulate_current_reasoning_result,
    build_criterion_ui_map_from_state as _build_criterion_ui_map_from_state,
    build_screen2_payload_from_state as _build_screen2_payload_from_state,
    evaluate_logic_tree_from_state as _evaluate_logic_tree_from_state,
    initialize_screen2_state_defaults as _initialize_screen2_state_defaults,
    prepare_screen2_review_payload as _prepare_screen2_review_payload,
)
from scripts.agent_flow.functions.screen2_summary_helpers import (
    build_agent_review_summary,
    get_agent_review_summary_metadata,
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
    initialized = _initialize_screen2_state_defaults(_resolve_state())
    if trace:
        with trace.subspan("initialize_placeholder_state") as span:
            span.outputs["initialized_keys"] = initialized


def accumulate_current_reasoning_result(trace: Any) -> None:
    _accumulate_current_reasoning_result(_resolve_state(), _resolve_scratchpad(), trace)


def evaluate_logic_tree_from_state(trace: Any) -> None:
    _evaluate_logic_tree_from_state(_resolve_state(), trace)


def build_criterion_ui_map(trace: Any) -> None:
    _build_criterion_ui_map_from_state(_resolve_state(), trace)


def build_screen2_payload(trace: Any) -> None:
    _build_screen2_payload_from_state(_resolve_state(), trace)


def prepare_screen2_review_payload(trace: Any) -> None:
    _prepare_screen2_review_payload(_resolve_state(), trace)


def build_agent_review_summary_from_state(trace: Any) -> None:
    state = _resolve_state()
    state["agent_review_summary"] = build_agent_review_summary(
        state.get("screen_2_review_result"),
        criterion_result_map=state.get("criterion_result_map"),
        retrieval_plan=state.get("retrieval_plan_v1"),
    )
    if trace:
        with trace.subspan("build_agent_review_summary") as span:
            span.attributes.update(
                get_agent_review_summary_metadata(state.get("screen_2_review_result"))
            )
