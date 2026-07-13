"""Pure Screen 2 and Screen 3 payload helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from scripts.agent_flow.functions.common import (
    CriterionResultMap,
    StateDict,
    get_selected_scope_context,
)
from scripts.agent_flow.functions.logic_tree_helpers import evaluate_logic_tree


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
    justification = source.get("justification")
    extracted_value = source.get("extracted_value")
    normalized_status = str(source.get("status", "Unreviewed"))
    if (
        normalized_status == "Found"
        and _coerce_bool(source.get("meets_criterion"), default=False) is False
        and extracted_value is not None
        and isinstance(justification, str)
    ):
        lowered = justification.lower()
        partial_evidence_markers = (
            "does not document the required",
            "does not document",
            "no records describe",
            "cannot be confirmed",
            "insufficient evidence",
            "missing qualifier",
            "required severity qualifier",
            "not documented",
        )
        if any(marker in lowered for marker in partial_evidence_markers):
            normalized_status = "Ambiguous"
    return {
        "status": normalized_status,
        "meets_criterion": _coerce_bool(source.get("meets_criterion"), default=False),
        "extracted_value": extracted_value,
        "justification": justification,
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


def _plan_items_by_criterion_id(retrieval_plan: Any) -> Dict[str, Dict[str, Any]]:
    plan = retrieval_plan if isinstance(retrieval_plan, dict) else {}
    plan_items = plan.get("plan_items") if isinstance(plan.get("plan_items"), list) else []
    indexed: Dict[str, Dict[str, Any]] = {}
    for item in plan_items:
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            indexed[criterion_id] = item
    return indexed


def _planner_context_for_criterion(plan_item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    item = plan_item if isinstance(plan_item, dict) else {}
    execution_hints = item.get("execution_hints") if isinstance(item.get("execution_hints"), dict) else {}
    return {
        "criterion_archetype": execution_hints.get("criterion_archetype"),
        "retrieval_strategy": execution_hints.get("retrieval_strategy"),
    }


def _derive_comment_requirement(
    conflict_flag: bool,
    clinician_input: Dict[str, Any],
) -> Dict[str, Any]:
    comment = clinician_input.get("comment")
    has_comment = isinstance(comment, str) and bool(comment.strip())
    comment_required = conflict_flag and not has_comment
    comment_guidance = None
    if comment_required:
        comment_guidance = (
            "Clinician answer differs from chart-backed evidence. Please add a clinician comment."
        )
    elif conflict_flag:
        comment_guidance = (
            "Clinician answer differs from chart-backed evidence. A clinician comment is recommended."
        )
    return {
        "comment_required": comment_required,
        "comment_guidance": comment_guidance,
    }


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

    if clinician_input.get("answered") and chart_prefill is not None and clinician_final_value is not None:
        if clinician_final_value != chart_prefill:
            conflict_flag = True
            conflict_reason = (
                "Clinician answer differs from chart-backed evidence for this criterion."
            )

    if clinician_input.get("answered"):
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

    comment_requirement = _derive_comment_requirement(conflict_flag, clinician_input)

    return {
        "display_state": display_state,
        "prefill_value": chart_prefill,
        "use_chart_as_prefill": chart_status == "Found",
        "conflict_flag": conflict_flag,
        "conflict_reason": conflict_reason,
        "comment_required": comment_requirement["comment_required"],
        "comment_guidance": comment_requirement["comment_guidance"],
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


def _selected_scope_display(selected_scope_context: Dict[str, Any]) -> Dict[str, Any]:
    selected_route = selected_scope_context.get("selected_route", {}) or {}
    selected_cluster_summary = selected_scope_context.get("selected_cluster_summary", {}) or {}
    selected_cluster = selected_scope_context.get("selected_cluster", {}) or {}

    return {
        "route_label": (
            selected_scope_context.get("selected_route_label")
            or selected_route.get("label")
            or selected_route.get("ui_label")
            or selected_scope_context.get("selected_route_id")
        ),
        "phase_label": (
            selected_scope_context.get("selected_phase_label")
            or {
                "initial": "Initial",
                "continuation": "Continuation",
                "other": "Other",
            }.get(selected_scope_context.get("selected_phase"), selected_scope_context.get("selected_phase"))
        ),
        "cluster_label": (
            selected_scope_context.get("selected_cluster_label")
            or selected_cluster.get("label")
            or selected_cluster.get("condition_label")
            or selected_cluster_summary.get("condition_label")
            or selected_scope_context.get("selected_cluster_id")
        ),
    }


def build_criterion_ui_map_data(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_result_map: Optional[CriterionResultMap],
    criterion_answers: Optional[Dict[str, Any]],
    retrieval_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scope_context = selected_scope_context if isinstance(selected_scope_context, dict) else {}
    result_map = criterion_result_map if isinstance(criterion_result_map, dict) else {}
    answers_map = criterion_answers if isinstance(criterion_answers, dict) else {}
    plan_items_by_id = _plan_items_by_criterion_id(retrieval_plan)

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
        plan_item = plan_items_by_id.get(criterion_id)
        ui_map[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion_kind": criterion.get("criterion_kind", "cluster_criterion"),
            "prompt": criterion.get("prompt", criterion_id),
            "answer_type": criterion.get("answer_type", "boolean"),
            "required": _coerce_bool(criterion.get("required"), default=True),
            "planner_context": _planner_context_for_criterion(plan_item),
            "clinician_input": clinician_input,
            "chart_result": chart_result,
            "ui_resolution": _derive_ui_resolution(
                chart_result=chart_result,
                clinician_input=clinician_input,
                answer_type=str(criterion.get("answer_type", "boolean")),
            ),
        }

    return ui_map


def _normalize_existing_criterion_ui_map_data(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_ui_map: Optional[Dict[str, Any]],
    criterion_answers: Optional[Dict[str, Any]],
    retrieval_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scope_context = selected_scope_context if isinstance(selected_scope_context, dict) else {}
    raw_ui_map = criterion_ui_map if isinstance(criterion_ui_map, dict) else {}
    answers_map = criterion_answers if isinstance(criterion_answers, dict) else {}
    plan_items_by_id = _plan_items_by_criterion_id(retrieval_plan)

    criteria_by_id: Dict[str, Dict[str, Any]] = {}
    for criterion in scope_context.get("selected_criteria_catalog", []) or []:
        if not isinstance(criterion, dict):
            continue
        criterion_id = criterion.get("criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            criteria_by_id[criterion_id] = criterion

    normalized_ui_map: Dict[str, Any] = {}
    for criterion_id in _ordered_criterion_ids(scope_context):
        existing_row = raw_ui_map.get(criterion_id) if isinstance(raw_ui_map.get(criterion_id), dict) else {}
        catalog_row = criteria_by_id.get(criterion_id, {})
        answer_type = str(
            existing_row.get("answer_type")
            or catalog_row.get("answer_type")
            or "boolean"
        )
        raw_clinician_input = (
            answers_map.get(criterion_id)
            if criterion_id in answers_map
            else existing_row.get("clinician_input")
        )
        clinician_input = _normalize_clinician_input(raw_clinician_input)
        chart_result = _normalize_chart_result(existing_row.get("chart_result"))
        plan_item = plan_items_by_id.get(criterion_id)
        planner_context = (
            _planner_context_for_criterion(plan_item)
            if plan_item
            else existing_row.get("planner_context", {}) if isinstance(existing_row.get("planner_context"), dict) else {}
        )
        normalized_ui_map[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion_kind": existing_row.get("criterion_kind", catalog_row.get("criterion_kind", "cluster_criterion")),
            "prompt": existing_row.get("prompt", catalog_row.get("prompt", criterion_id)),
            "answer_type": answer_type,
            "required": _coerce_bool(existing_row.get("required", catalog_row.get("required")), default=True),
            "planner_context": planner_context,
            "clinician_input": clinician_input,
            "chart_result": chart_result,
            "ui_resolution": _derive_ui_resolution(
                chart_result=chart_result,
                clinician_input=clinician_input,
                answer_type=answer_type,
            ),
        }

    return normalized_ui_map


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
    if isinstance(criterion_ui_map, dict) and criterion_ui_map:
        criterion_ui_map = _normalize_existing_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_ui_map=criterion_ui_map,
            criterion_answers=runtime_state.get("criterion_answers", {}),
            retrieval_plan=runtime_state.get("retrieval_plan_v1"),
        )
    else:
        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_result_map=runtime_state.get("criterion_result_map", {}),
            criterion_answers=runtime_state.get("criterion_answers", {}),
            retrieval_plan=runtime_state.get("retrieval_plan_v1"),
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

    return {
        "status": status,
        "payload": {
            "selected_scope": {
                "selected_route_id": selected_scope_context.get("selected_route_id"),
                "selected_phase": selected_scope_context.get("selected_phase"),
                "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
            },
            "selected_scope_display": _selected_scope_display(selected_scope_context),
            "criteria": criteria,
            "logic_evaluation": logic_evaluation,
            "additional_cluster_suggestions": [],
            "next_action": next_action,
        },
        "messages": list(runtime_state.get("messages", []) or []),
    }


def build_screen2_review_tool_input_data(state: Optional[StateDict]) -> Dict[str, Any]:
    runtime_state = state if isinstance(state, dict) else {}
    selected_scope_context = get_selected_scope_context(runtime_state)
    screen_2_payload = runtime_state.get("screen_2_payload")
    if not isinstance(screen_2_payload, dict) or not screen_2_payload:
        screen_2_payload = build_screen2_payload_data(runtime_state)

    criterion_answers = runtime_state.get("criterion_answers", {})
    if not isinstance(criterion_answers, dict):
        criterion_answers = {}

    return {
        "session_id": runtime_state.get("session_id"),
        "subject_id": runtime_state.get("subject_id"),
        "policy_id": runtime_state.get("policy_id") or selected_scope_context.get("policy_id"),
        "selected_scope": {
            "selected_route_id": selected_scope_context.get("selected_route_id"),
            "selected_phase": selected_scope_context.get("selected_phase"),
            "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
        },
        "screen_2_payload": screen_2_payload,
        "criterion_answers": criterion_answers,
    }


def _extract_review_result_data(raw_review_result: Any) -> Dict[str, Any]:
    if isinstance(raw_review_result, str):
        try:
            parsed = json.loads(raw_review_result)
        except Exception:
            return {}
        return _extract_review_result_data(parsed)

    if not isinstance(raw_review_result, dict):
        return {}

    output = raw_review_result.get("output")
    if isinstance(output, (dict, str)):
        extracted = _extract_review_result_data(output)
        if extracted:
            return extracted

    return raw_review_result


def _merge_reviewed_screen2_payload(
    screen_2_payload: Dict[str, Any],
    approved_answers: Dict[str, Any],
) -> Dict[str, Any]:
    merged_payload = deepcopy(screen_2_payload)
    payload = merged_payload.setdefault("payload", {})
    criteria = payload.get("criteria")
    if not isinstance(criteria, list):
        payload["criteria"] = []
        criteria = payload["criteria"]

    satisfied_ids: List[str] = []
    not_satisfied_ids: List[str] = []
    unresolved_ids: List[str] = []

    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue

        criterion_id = criterion.get("criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            continue

        answer_type = str(criterion.get("answer_type", "boolean"))
        chart_result = _normalize_chart_result(criterion.get("chart_result"))
        existing_input = criterion.get("clinician_input")
        if criterion_id in approved_answers:
            clinician_input = _normalize_clinician_input(approved_answers.get(criterion_id))
        else:
            clinician_input = _normalize_clinician_input(existing_input)

        ui_resolution = _derive_ui_resolution(
            chart_result=chart_result,
            clinician_input=clinician_input,
            answer_type=answer_type,
        )

        criterion["clinician_input"] = clinician_input
        criterion["chart_result"] = chart_result
        criterion["ui_resolution"] = ui_resolution

        final_answer = ui_resolution.get("final_answer")
        if final_answer is True:
            satisfied_ids.append(criterion_id)
        elif final_answer is False:
            not_satisfied_ids.append(criterion_id)
        else:
            unresolved_ids.append(criterion_id)

    if not_satisfied_ids:
        selected_cluster_status = "not_satisfied"
        selected_cluster_satisfied = False
    elif unresolved_ids:
        selected_cluster_status = "unresolved"
        selected_cluster_satisfied = False
    else:
        selected_cluster_status = "satisfied"
        selected_cluster_satisfied = True

    payload["logic_evaluation"] = {
        "selected_cluster_satisfied": selected_cluster_satisfied,
        "selected_cluster_status": selected_cluster_status,
        "satisfied_criterion_ids": satisfied_ids,
        "not_satisfied_criterion_ids": not_satisfied_ids,
        "unresolved_criterion_ids": unresolved_ids,
        "criterion_counts": {
            "satisfied": len(satisfied_ids),
            "not_satisfied": len(not_satisfied_ids),
            "unresolved": len(unresolved_ids),
        },
    }
    payload["next_action"] = "stay_screen_2" if unresolved_ids else "proceed_screen_3"
    merged_payload["status"] = "warning" if unresolved_ids else "ok"
    return merged_payload


def _build_screen3_sections(
    criteria: List[Dict[str, Any]],
) -> Dict[str, Any]:
    satisfied_criteria: List[Dict[str, Any]] = []
    rejected_criteria: List[Dict[str, Any]] = []
    unresolved_criteria: List[Dict[str, Any]] = []

    for row in criteria:
        if not isinstance(row, dict):
            continue

        ui_resolution = row.get("ui_resolution", {}) or {}
        clinician_input = row.get("clinician_input", {}) or {}
        final_answer = ui_resolution.get("final_answer")
        conflict_flag = _coerce_bool(ui_resolution.get("conflict_flag"), default=False)
        comment_required = _coerce_bool(ui_resolution.get("comment_required"), default=False)

        criterion_summary = {
            "criterion_id": row.get("criterion_id"),
            "criterion_kind": row.get("criterion_kind"),
            "prompt": row.get("prompt"),
            "final_answer": final_answer,
            "final_source": ui_resolution.get("final_source"),
            "display_state": ui_resolution.get("display_state"),
            "justification": ((row.get("chart_result", {}) or {}).get("justification")),
            "comment": clinician_input.get("comment"),
            "conflict_flag": conflict_flag,
            "conflict_reason": (
                ui_resolution.get("comment_guidance")
                if comment_required
                else ui_resolution.get("conflict_reason")
            )
            or None,
        }

        if final_answer is True:
            satisfied_criteria.append(criterion_summary)
        elif final_answer is False:
            rejected_criteria.append(criterion_summary)
        elif row.get("required"):
            unresolved_criteria.append(criterion_summary)

    status = "complete"
    if unresolved_criteria:
        status = "blocked"

    return {
        "satisfied_criteria": satisfied_criteria,
        "rejected_criteria": rejected_criteria,
        "unresolved_criteria": unresolved_criteria,
        "status": status,
    }


def normalize_review_result_data(raw_review_result: Any) -> Dict[str, Any]:
    review_result = _extract_review_result_data(raw_review_result)
    if not review_result:
        return {}

    approved_answers = review_result.get("approved_criterion_answers")
    if not isinstance(approved_answers, dict):
        approved_answers = {}

    screen_2_payload = review_result.get("reviewed_screen_2_payload")
    if not isinstance(screen_2_payload, dict):
        screen_2_payload = {}

    normalized = dict(review_result)
    normalized["approved_criterion_answers"] = approved_answers
    normalized["reviewed_screen_2_payload"] = _merge_reviewed_screen2_payload(
        screen_2_payload,
        approved_answers,
    ) if screen_2_payload else {}
    normalized["human_validated"] = bool(review_result.get("human_validated", True))
    normalized.setdefault(
        "review_metadata",
        {
            "reviewer": None,
            "reviewed_at": None,
            "comment": None,
        },
    )
    return normalized


def build_screen3_payload_data(state: Optional[StateDict]) -> Dict[str, Any]:
    runtime_state = state if isinstance(state, dict) else {}
    selected_scope_context = get_selected_scope_context(runtime_state)
    criterion_ui_map = runtime_state.get("criterion_ui_map")
    if isinstance(criterion_ui_map, dict) and criterion_ui_map:
        criterion_ui_map = _normalize_existing_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_ui_map=criterion_ui_map,
            criterion_answers=runtime_state.get("criterion_answers", {}),
            retrieval_plan=runtime_state.get("retrieval_plan_v1"),
        )
    else:
        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=selected_scope_context,
            criterion_result_map=runtime_state.get("criterion_result_map", {}),
            criterion_answers=runtime_state.get("criterion_answers", {}),
            retrieval_plan=runtime_state.get("retrieval_plan_v1"),
        )

    criteria = _order_criterion_rows(selected_scope_context, criterion_ui_map)
    sections = _build_screen3_sections(criteria)

    review_summary = {
        "selected_scope": {
            "selected_route_id": selected_scope_context.get("selected_route_id"),
            "selected_phase": selected_scope_context.get("selected_phase"),
            "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
        },
        "selected_scope_display": _selected_scope_display(selected_scope_context),
        "criterion_totals": {
            "total": len(criteria),
            "satisfied": len(sections["satisfied_criteria"]),
            "rejected": len(sections["rejected_criteria"]),
            "unresolved": len(sections["unresolved_criteria"]),
        },
        "logic_evaluation": runtime_state.get("logic_evaluation", {}) or {},
    }

    logic_evaluation = runtime_state.get("logic_evaluation", {}) or {}
    cluster_status = logic_evaluation.get("selected_cluster_status") if isinstance(logic_evaluation, dict) else None
    if cluster_status not in {"satisfied", "not_satisfied", "unresolved"}:
        if sections["rejected_criteria"]:
            cluster_status = "not_satisfied"
        elif sections["unresolved_criteria"]:
            cluster_status = "unresolved"
        else:
            cluster_status = "satisfied"

    return {
        "status": sections["status"],
        "payload": {
            "review_summary": review_summary,
            "satisfied_criteria": sections["satisfied_criteria"],
            "rejected_criteria": sections["rejected_criteria"],
            "unresolved_criteria": sections["unresolved_criteria"],
            "review_alerts": [],
            "submission_ready": cluster_status == "satisfied",
        },
        "messages": list(runtime_state.get("messages", []) or []),
    }


def build_screen3_payload_from_review_result_data(raw_review_result: Any) -> Dict[str, Any]:
    review_result = normalize_review_result_data(raw_review_result)
    if not review_result:
        return {
            "status": "error",
            "payload": {
                "review_summary": {
                    "selected_scope": {
                        "selected_route_id": None,
                        "selected_phase": None,
                        "selected_cluster_id": None,
                    },
                    "criterion_totals": {
                        "total": 0,
                        "satisfied": 0,
                        "rejected": 0,
                        "unresolved": 0,
                    },
                    "logic_evaluation": {},
                },
                "satisfied_criteria": [],
                "rejected_criteria": [],
                "unresolved_criteria": [],
                "review_alerts": [
                    {
                        "type": "missing_review_result",
                        "message": "Structured Agent did not return a valid screen_2_review_result artifact.",
                    }
                ],
                "submission_ready": False,
            },
            "messages": [],
        }

    screen_2_payload = review_result.get("reviewed_screen_2_payload")
    if not isinstance(screen_2_payload, dict) or not isinstance(screen_2_payload.get("payload"), dict):
        return {
            "status": "error",
            "payload": {
                "review_summary": {
                    "selected_scope": {
                        "selected_route_id": None,
                        "selected_phase": None,
                        "selected_cluster_id": None,
                    },
                    "criterion_totals": {
                        "total": 0,
                        "satisfied": 0,
                        "rejected": 0,
                        "unresolved": 0,
                    },
                    "logic_evaluation": {},
                },
                "satisfied_criteria": [],
                "rejected_criteria": [],
                "unresolved_criteria": [],
                "review_alerts": [
                    {
                        "type": "missing_reviewed_screen_2_payload",
                        "message": "Review result did not include a valid reviewed_screen_2_payload.",
                    }
                ],
                "submission_ready": False,
            },
            "messages": [],
        }

    payload = screen_2_payload.get("payload", {})
    criteria = payload.get("criteria") if isinstance(payload.get("criteria"), list) else []
    logic_evaluation = payload.get("logic_evaluation") if isinstance(payload.get("logic_evaluation"), dict) else {}
    review_summary = {
        "selected_scope": payload.get("selected_scope", {}) or {},
        "selected_scope_display": payload.get("selected_scope_display"),
        "criterion_totals": {
            "total": len(criteria),
            "satisfied": 0,
            "rejected": 0,
            "unresolved": 0,
        },
        "logic_evaluation": logic_evaluation,
    }

    sections = _build_screen3_sections(criteria)

    review_summary["criterion_totals"] = {
        "total": len(criteria),
        "satisfied": len(sections["satisfied_criteria"]),
        "rejected": len(sections["rejected_criteria"]),
        "unresolved": len(sections["unresolved_criteria"]),
    }

    review_alerts: List[Dict[str, Any]] = []
    cluster_status = (logic_evaluation.get("selected_cluster_status") if isinstance(logic_evaluation, dict) else None)
    if cluster_status not in {"satisfied", "not_satisfied", "unresolved"}:
        if sections["rejected_criteria"]:
            cluster_status = "not_satisfied"
        elif sections["unresolved_criteria"]:
            cluster_status = "unresolved"
        else:
            cluster_status = "satisfied"
    submission_ready = cluster_status == "satisfied"
    status = sections["status"]
    if review_result.get("approval_status") == "rejected":
        status = "blocked"
        review_alerts.insert(
            0,
            {
                "type": "human_review_rejected",
                "message": "Human reviewer rejected the Screen 2 review payload.",
            },
        )
        submission_ready = False

    return {
        "status": status,
        "payload": {
            "review_summary": review_summary,
            "satisfied_criteria": sections["satisfied_criteria"],
            "rejected_criteria": sections["rejected_criteria"],
            "unresolved_criteria": sections["unresolved_criteria"],
            "review_alerts": review_alerts,
            "submission_ready": submission_ready,
        },
        "messages": list(screen_2_payload.get("messages", []) or []),
    }
