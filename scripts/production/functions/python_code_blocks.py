"""Reusable helpers for Structured Agent Python code blocks.

These helpers are intentionally self-contained so DSS Python blocks can import a
single module without depending on notebook-only project-library behavior.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Set

CriterionResult = Dict[str, Any]
CriterionResultMap = Dict[str, CriterionResult]
StateDict = Dict[str, Any]
ScratchpadDict = Dict[str, Any]

DEFAULT_SCOPE_STATE_KEY = "selected_scope_context"


def get_selected_scope_context(state: StateDict) -> Dict[str, Any]:
    """Return the inner selected-scope context from agent state.

    Screen 2 should persist the inner scoped selection object under a dedicated
    state key, but this helper also tolerates the older wrapper payload shape to
    keep debugging smoother while flows are being migrated.
    """

    scope_context = state.get(DEFAULT_SCOPE_STATE_KEY, {}) or {}
    if isinstance(scope_context, dict):
        inner = scope_context.get("scoped_policy_context")
        if isinstance(inner, dict):
            return inner
        return scope_context
    return {}


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
        "screen_3_payload": {},
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, (dict, list)) else value
            initialized.append(key)
    with trace.subspan("initialize_placeholder_state") as span:
        span.outputs["initialized_keys"] = initialized


def accumulate_current_reasoning_result(
    trace: Any,
) -> None:
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
    return


# ---- Logic-tree evaluation helpers ----

def _empty_eval() -> Dict[str, Any]:
    return {
        "satisfied": False,
        "status": "unresolved",
        "satisfied_criterion_ids": [],
        "not_satisfied_criterion_ids": [],
        "unresolved_criterion_ids": [],
        "criterion_counts": {
            "satisfied": 0,
            "not_satisfied": 0,
            "unresolved": 0,
        },
        "_satisfied_ids": set(),
        "_not_satisfied_ids": set(),
        "_unresolved_ids": set(),
    }


def _finalize_eval(result: Dict[str, Any]) -> Dict[str, Any]:
    satisfied_ids = result.pop("_satisfied_ids")
    not_satisfied_ids = result.pop("_not_satisfied_ids")
    unresolved_ids = result.pop("_unresolved_ids")

    result["satisfied_criterion_ids"] = sorted(satisfied_ids)
    result["not_satisfied_criterion_ids"] = sorted(not_satisfied_ids)
    result["unresolved_criterion_ids"] = sorted(unresolved_ids)
    result["criterion_counts"] = {
        "satisfied": len(satisfied_ids),
        "not_satisfied": len(not_satisfied_ids),
        "unresolved": len(unresolved_ids),
    }
    return result


def _normalize_criterion_result(criterion_id: str, criterion_result_map: CriterionResultMap) -> Dict[str, Any]:
    raw = criterion_result_map.get(criterion_id, {})
    if not isinstance(raw, dict):
        raw = {}

    status = str(raw.get("status", "Unreviewed"))
    meets_criterion = bool(raw.get("meets_criterion", False))

    normalized = _empty_eval()
    if status == "Found" and meets_criterion:
        normalized["satisfied"] = True
        normalized["status"] = "satisfied"
        normalized["_satisfied_ids"].add(criterion_id)
    elif status == "Found" and not meets_criterion:
        normalized["status"] = "not_satisfied"
        normalized["_not_satisfied_ids"].add(criterion_id)
    else:
        normalized["status"] = "unresolved"
        normalized["_unresolved_ids"].add(criterion_id)

    return normalized


def _merge_sets(child_results: Iterable[Dict[str, Any]]) -> Dict[str, Set[str]]:
    satisfied_ids: Set[str] = set()
    not_satisfied_ids: Set[str] = set()
    unresolved_ids: Set[str] = set()
    for child in child_results:
        satisfied_ids.update(child.get("_satisfied_ids", set()))
        not_satisfied_ids.update(child.get("_not_satisfied_ids", set()))
        unresolved_ids.update(child.get("_unresolved_ids", set()))
    return {
        "_satisfied_ids": satisfied_ids,
        "_not_satisfied_ids": not_satisfied_ids,
        "_unresolved_ids": unresolved_ids,
    }


def _extract_logic_roots_from_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        root = item.get("logic_root")
        if isinstance(root, dict):
            roots.append(root)
    return roots


def _derive_logic_inputs_from_scope_context(
    selected_scope_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(selected_scope_context, dict):
        return {"logic_root": None, "supporting_logic_roots": []}

    selected_cluster = selected_scope_context.get("selected_cluster")
    logic_root = selected_cluster.get("logic_root") if isinstance(selected_cluster, dict) else None
    if not isinstance(logic_root, dict):
        logic_root = None

    supporting_logic_roots: List[Dict[str, Any]] = []
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_route_guards", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_cluster_entry_guards", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_logic_profiles", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_inherited_diagnosis_clusters", []))
    )

    return {"logic_root": logic_root, "supporting_logic_roots": supporting_logic_roots}


def _evaluate_node(node: Optional[Dict[str, Any]], criterion_result_map: CriterionResultMap) -> Dict[str, Any]:
    if not isinstance(node, dict):
        return _empty_eval()

    node_type = node.get("node_type")
    if node_type == "criterion_ref":
        criterion_id = node.get("criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            return _empty_eval()
        return _normalize_criterion_result(criterion_id, criterion_result_map)

    if node_type != "group":
        return _empty_eval()

    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    child_results = [_evaluate_node(child, criterion_result_map) for child in children]
    merged = _merge_sets(child_results)

    satisfied_children = sum(1 for result in child_results if result["status"] == "satisfied")
    not_satisfied_children = sum(1 for result in child_results if result["status"] == "not_satisfied")
    unresolved_children = sum(1 for result in child_results if result["status"] == "unresolved")

    operator = str(node.get("operator", "all"))
    result = _empty_eval()
    result.update(merged)

    if operator == "all":
        if not_satisfied_children > 0:
            result["status"] = "not_satisfied"
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "satisfied"
            result["satisfied"] = True
        return result

    if operator == "any":
        if satisfied_children > 0:
            result["status"] = "satisfied"
            result["satisfied"] = True
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "not_satisfied"
        return result

    if operator == "none":
        if satisfied_children > 0:
            result["status"] = "not_satisfied"
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "satisfied"
            result["satisfied"] = True
        return result

    if operator.startswith("at_least:"):
        try:
            threshold = int(operator.split(":", 1)[1])
        except (IndexError, ValueError):
            threshold = 0

        possible_max = satisfied_children + unresolved_children
        if satisfied_children >= threshold:
            result["status"] = "satisfied"
            result["satisfied"] = True
        elif possible_max < threshold:
            result["status"] = "not_satisfied"
        else:
            result["status"] = "unresolved"
        return result

    return result


def evaluate_logic_tree(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_result_map: CriterionResultMap,
) -> Dict[str, Any]:
    """Evaluate the selected scope logic against a criterion-result map."""

    derived = _derive_logic_inputs_from_scope_context(selected_scope_context)
    logic_root = derived["logic_root"]
    supporting_logic_roots = derived["supporting_logic_roots"]

    roots = [logic_root] + list(supporting_logic_roots)
    valid_roots = [root for root in roots if isinstance(root, dict)]

    if not valid_roots:
        return {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": [],
            "not_satisfied_criterion_ids": [],
            "unresolved_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 0,
                "not_satisfied": 0,
                "unresolved": 0,
            },
        }

    effective_root = valid_roots[0] if len(valid_roots) == 1 else {
        "node_type": "group",
        "operator": "all",
        "children": valid_roots,
    }

    result = _evaluate_node(effective_root, criterion_result_map)
    finalized = _finalize_eval(result)
    return {
        "selected_cluster_satisfied": finalized["satisfied"],
        "selected_cluster_status": finalized["status"],
        "satisfied_criterion_ids": finalized["satisfied_criterion_ids"],
        "not_satisfied_criterion_ids": finalized["not_satisfied_criterion_ids"],
        "unresolved_criterion_ids": finalized["unresolved_criterion_ids"],
        "criterion_counts": finalized["criterion_counts"],
    }


def evaluate_logic_tree_from_state(
    trace: Any,
) -> None:
    """Compute `logic_evaluation` from current state and emit trace output."""

    state = _resolve_state()
    selected_scope_context = get_selected_scope_context(state)
    criterion_result_map = state.get("criterion_result_map", {}) or {}
    logic_evaluation = evaluate_logic_tree(selected_scope_context, criterion_result_map)
    state["logic_evaluation"] = logic_evaluation

    with trace.subspan("evaluate_logic_tree") as span:
        span.attributes["selected_cluster_id"] = selected_scope_context.get("selected_cluster_id")
        span.attributes["criterion_result_count"] = len(criterion_result_map)
        span.outputs["logic_evaluation"] = logic_evaluation


# ---- Screen 2 / Screen 3 payload helpers ----

def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return default


def _normalize_clinician_input(raw: Any) -> Dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    answer = source.get("answer")
    value = source.get("value")
    comment = source.get("comment")
    answered = answer is not None or value is not None or bool(comment)
    return {
        "answer": answer,
        "value": value,
        "comment": comment,
        "override_prefill": _coerce_bool(source.get("override_prefill"), default=False),
        "answered": answered,
    }


def _normalize_chart_result(raw: Any) -> Dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    chart_sources = source.get("sources") if isinstance(source.get("sources"), dict) else {}
    return {
        "status": str(source.get("status", "Unreviewed")),
        "meets_criterion": _coerce_bool(source.get("meets_criterion"), default=False),
        "extracted_value": source.get("extracted_value"),
        "justification": source.get("justification"),
        "sources": {
            "structured": list(chart_sources.get("structured", []) or []),
            "notes": list(chart_sources.get("notes", []) or []),
        },
    }


def _get_chart_prefill_value(chart_result: Dict[str, Any], answer_type: str) -> Any:
    if chart_result.get("status") != "Found":
        return None
    if answer_type == "boolean":
        return chart_result.get("meets_criterion")
    extracted_value = chart_result.get("extracted_value")
    if extracted_value is not None:
        return extracted_value
    return chart_result.get("meets_criterion")


def _get_clinician_final_value(clinician_input: Dict[str, Any]) -> Any:
    if clinician_input.get("value") is not None:
        return clinician_input.get("value")
    if clinician_input.get("answer") is not None:
        return clinician_input.get("answer")
    return None


def _display_state_from_boolean(boolean_value: bool) -> str:
    return "satisfied" if boolean_value else "not_satisfied"


def _derive_ui_resolution(
    chart_result: Dict[str, Any],
    clinician_input: Dict[str, Any],
    answer_type: str,
) -> Dict[str, Any]:
    chart_prefill = _get_chart_prefill_value(chart_result, answer_type)
    clinician_final_value = _get_clinician_final_value(clinician_input)
    chart_status = chart_result.get("status", "Unreviewed")
    chart_meets = _coerce_bool(chart_result.get("meets_criterion"), default=False)

    conflict_flag = False
    conflict_reason = None

    if clinician_input.get("answered") and chart_status == "Found" and clinician_final_value is not None:
        if clinician_final_value != chart_prefill:
            conflict_flag = True
            conflict_reason = (
                "Clinician answer differs from chart-backed evidence for this criterion."
            )

    if conflict_flag:
        display_state = "conflict"
        final_answer = clinician_final_value
        final_source = "clinician"
    elif clinician_input.get("answered"):
        if isinstance(clinician_input.get("answer"), bool):
            display_state = _display_state_from_boolean(clinician_input["answer"])
        else:
            display_state = "satisfied"
        final_answer = clinician_final_value
        final_source = "clinician"
    elif chart_status == "Found":
        display_state = _display_state_from_boolean(chart_meets)
        final_answer = chart_prefill
        final_source = "chart"
    elif chart_status in {"Missing", "Ambiguous"}:
        display_state = "needs_clinician"
        final_answer = None
        final_source = "unresolved"
    else:
        display_state = "unanswered"
        final_answer = None
        final_source = "unresolved"

    return {
        "display_state": display_state,
        "prefill_value": chart_prefill,
        "use_chart_as_prefill": chart_status == "Found",
        "conflict_flag": conflict_flag,
        "conflict_reason": conflict_reason,
        "final_answer": final_answer,
        "final_source": final_source,
    }


def _ordered_criterion_ids(selected_scope_context: Dict[str, Any]) -> List[str]:
    ordered_ids: List[str] = []
    candidate_groups = [
        selected_scope_context.get("selected_route_guard_criterion_ids", []),
        selected_scope_context.get("selected_cluster_entry_guard_criterion_ids", []),
        selected_scope_context.get("selected_inherited_diagnosis_criterion_ids", []),
        selected_scope_context.get("selected_cluster_criterion_ids", []),
    ]

    for group in candidate_groups:
        for criterion_id in group or []:
            if isinstance(criterion_id, str) and criterion_id and criterion_id not in ordered_ids:
                ordered_ids.append(criterion_id)

    for criterion in selected_scope_context.get("selected_criteria_catalog", []) or []:
        criterion_id = criterion.get("criterion_id") if isinstance(criterion, dict) else None
        if isinstance(criterion_id, str) and criterion_id and criterion_id not in ordered_ids:
            ordered_ids.append(criterion_id)

    return ordered_ids


def build_criterion_ui_map_data(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_result_map: Optional[CriterionResultMap],
    criterion_answers: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    scope_context = selected_scope_context if isinstance(selected_scope_context, dict) else {}
    result_map = criterion_result_map if isinstance(criterion_result_map, dict) else {}
    answers_map = criterion_answers if isinstance(criterion_answers, dict) else {}

    criteria_by_id: Dict[str, Dict[str, Any]] = {}
    for criterion in scope_context.get("selected_criteria_catalog", []) or []:
        if not isinstance(criterion, dict):
            continue
        criterion_id = criterion.get("criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            criteria_by_id[criterion_id] = criterion

    ui_map: Dict[str, Any] = {}
    for criterion_id in _ordered_criterion_ids(scope_context):
        criterion = criteria_by_id.get(criterion_id, {})
        clinician_input = _normalize_clinician_input(answers_map.get(criterion_id))
        chart_result = _normalize_chart_result(result_map.get(criterion_id))
        ui_map[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion_kind": criterion.get("criterion_kind", "cluster_criterion"),
            "prompt": criterion.get("prompt", criterion_id),
            "answer_type": criterion.get("answer_type", "boolean"),
            "required": _coerce_bool(criterion.get("required"), default=True),
            "clinician_input": clinician_input,
            "chart_result": chart_result,
            "ui_resolution": _derive_ui_resolution(
                chart_result=chart_result,
                clinician_input=clinician_input,
                answer_type=str(criterion.get("answer_type", "boolean")),
            ),
        }

    return ui_map


def build_criterion_ui_map(
    trace: Any,
) -> None:
    """Build the deterministic webapp-facing criterion UI map from current state."""

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


def _order_criterion_rows(
    selected_scope_context: Dict[str, Any],
    criterion_ui_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ordered_rows: List[Dict[str, Any]] = []
    for criterion_id in _ordered_criterion_ids(selected_scope_context):
        row = criterion_ui_map.get(criterion_id)
        if isinstance(row, dict):
            ordered_rows.append(row)
    return ordered_rows


def build_screen2_payload_data(state: Optional[StateDict]) -> Dict[str, Any]:
    runtime_state = state if isinstance(state, dict) else {}
    selected_scope_context = get_selected_scope_context(runtime_state)
    criterion_ui_map = runtime_state.get("criterion_ui_map")
    if not isinstance(criterion_ui_map, dict) or not criterion_ui_map:
        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_result_map=runtime_state.get("criterion_result_map", {}),
            criterion_answers=runtime_state.get("criterion_answers", {}),
        )

    logic_evaluation = runtime_state.get("logic_evaluation")
    if not isinstance(logic_evaluation, dict) or not logic_evaluation:
        logic_evaluation = evaluate_logic_tree(
            selected_scope_context,
            runtime_state.get("criterion_result_map", {}) or {},
        )

    criteria = _order_criterion_rows(selected_scope_context, criterion_ui_map)
    unresolved_required_ids = [
        row["criterion_id"]
        for row in criteria
        if row.get("required") and row.get("ui_resolution", {}).get("final_answer") is None
    ]
    conflict_count = sum(
        1 for row in criteria if row.get("ui_resolution", {}).get("conflict_flag")
    )

    if not criteria:
        status = "blocked"
        next_action = "stay_screen_2"
    else:
        next_action = "proceed_screen_3" if not unresolved_required_ids else "stay_screen_2"
        if unresolved_required_ids or conflict_count > 0:
            status = "warning"
        else:
            status = "ok"

    payload = {
        "status": status,
        "payload": {
            "selected_scope": {
                "selected_route_id": selected_scope_context.get("selected_route_id"),
                "selected_phase": selected_scope_context.get("selected_phase"),
                "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
            },
            "criteria": criteria,
            "logic_evaluation": logic_evaluation,
            "additional_cluster_suggestions": [],
            "next_action": next_action,
        },
        "messages": list(runtime_state.get("messages", []) or []),
    }
    return payload


def build_screen2_payload(
    trace: Any,
) -> None:
    """Build and persist the Screen 2 response payload from current state."""

    state = _resolve_state()
    if not isinstance(state.get("criterion_ui_map"), dict) or not state.get("criterion_ui_map"):
        state["criterion_ui_map"] = build_criterion_ui_map_data(
            selected_scope_context=get_selected_scope_context(state),
            criterion_result_map=state.get("criterion_result_map", {}),
            criterion_answers=state.get("criterion_answers", {}),
        )

    payload = build_screen2_payload_data(state)
    state["screen_2_payload"] = payload

    with trace.subspan("build_screen_2_payload") as span:
        span.outputs["status"] = payload.get("status")
        span.outputs["next_action"] = (
            payload.get("payload", {}) or {}
        ).get("next_action")


def build_screen3_payload_data(state: Optional[StateDict]) -> Dict[str, Any]:
    runtime_state = state if isinstance(state, dict) else {}
    selected_scope_context = get_selected_scope_context(runtime_state)
    criterion_ui_map = runtime_state.get("criterion_ui_map")
    if not isinstance(criterion_ui_map, dict) or not criterion_ui_map:
        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_result_map=runtime_state.get("criterion_result_map", {}),
            criterion_answers=runtime_state.get("criterion_answers", {}),
        )

    criteria = _order_criterion_rows(selected_scope_context, criterion_ui_map)
    answered_criteria: List[Dict[str, Any]] = []
    unanswered_required_items: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    for row in criteria:
        ui_resolution = row.get("ui_resolution", {})
        clinician_input = row.get("clinician_input", {})
        final_answer = ui_resolution.get("final_answer")
        if final_answer is None and row.get("required"):
            unanswered_required_items.append(
                {
                    "criterion_id": row.get("criterion_id"),
                    "criterion_kind": row.get("criterion_kind"),
                    "prompt": row.get("prompt"),
                    "display_state": ui_resolution.get("display_state"),
                }
            )
        else:
            answered_criteria.append(
                {
                    "criterion_id": row.get("criterion_id"),
                    "criterion_kind": row.get("criterion_kind"),
                    "prompt": row.get("prompt"),
                    "final_answer": final_answer,
                    "final_source": ui_resolution.get("final_source"),
                    "display_state": ui_resolution.get("display_state"),
                    "comment": clinician_input.get("comment"),
                }
            )

        if ui_resolution.get("conflict_flag"):
            warnings.append(
                {
                    "criterion_id": row.get("criterion_id"),
                    "type": "conflict",
                    "message": ui_resolution.get("conflict_reason")
                    or "Clinician answer conflicts with chart-backed evidence.",
                }
            )

    submission_ready = not unanswered_required_items
    status = "complete" if submission_ready and not warnings else "warning"
    if unanswered_required_items:
        status = "blocked"

    review_summary = {
        "selected_scope": {
            "selected_route_id": selected_scope_context.get("selected_route_id"),
            "selected_phase": selected_scope_context.get("selected_phase"),
            "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
        },
        "criterion_totals": {
            "total": len(criteria),
            "answered": len(answered_criteria),
            "unanswered_required": len(unanswered_required_items),
            "conflicts": len(warnings),
        },
        "logic_evaluation": runtime_state.get("logic_evaluation", {}) or {},
    }

    return {
        "status": status,
        "payload": {
            "review_summary": review_summary,
            "answered_criteria": answered_criteria,
            "unanswered_required_items": unanswered_required_items,
            "warnings": warnings,
            "submission_ready": submission_ready,
        },
        "messages": list(runtime_state.get("messages", []) or []),
    }


def build_screen3_payload(
    trace: Any,
) -> None:
    """Build and persist the Screen 3 response payload from current state."""

    state = _resolve_state()
    if not isinstance(state.get("criterion_ui_map"), dict) or not state.get("criterion_ui_map"):
        state["criterion_ui_map"] = build_criterion_ui_map_data(
            selected_scope_context=get_selected_scope_context(state),
            criterion_result_map=state.get("criterion_result_map", {}),
            criterion_answers=state.get("criterion_answers", {}),
        )

    payload = build_screen3_payload_data(state)
    state["screen_3_payload"] = payload

    with trace.subspan("build_screen_3_payload") as span:
        span.outputs["status"] = payload.get("status")
        span.outputs["submission_ready"] = (
            payload.get("payload", {}) or {}
        ).get("submission_ready")
