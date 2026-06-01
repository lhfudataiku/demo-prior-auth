from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Optional


PHASE_LABELS = {
    "initial": "Initial",
    "continuation": "Continuation",
    "other": "Other",
}


def phase_label(phase: str) -> str:
    return PHASE_LABELS.get(phase, phase.title())


def selected_scope_display(selected_scope_context: dict) -> dict:
    selected_route = selected_scope_context.get("selected_route", {}) or {}
    selected_cluster_summary = selected_scope_context.get("selected_cluster_summary", {}) or {}
    selected_cluster = selected_scope_context.get("selected_cluster", {}) or {}
    return {
        "route_label": (
            selected_route.get("label")
            or selected_scope_context.get("selected_route_label")
            or selected_scope_context.get("selected_route_id")
        ),
        "phase_label": (
            selected_scope_context.get("selected_phase_label")
            or phase_label(selected_scope_context.get("selected_phase", "other"))
        ),
        "cluster_label": (
            selected_cluster.get("label")
            or selected_cluster_summary.get("condition_label")
            or selected_scope_context.get("selected_cluster_label")
            or selected_scope_context.get("selected_cluster_id")
        ),
    }


def ensure_selected_scope_display(screen_2_response: dict, scope_display: dict) -> dict:
    enriched = deepcopy(screen_2_response)
    enriched.setdefault("payload", {})
    enriched["payload"]["selected_scope_display"] = scope_display
    return enriched


def resolve_selected_scope_display(
    selected_scope_context: Optional[dict],
    screen_2_response: Optional[dict] = None,
) -> dict:
    if isinstance(selected_scope_context, dict) and selected_scope_context:
        return selected_scope_display(selected_scope_context)

    payload = (screen_2_response or {}).get("payload", {})
    display = payload.get("selected_scope_display")
    if isinstance(display, dict) and display:
        return display

    selected_scope = payload.get("selected_scope", {}) or {}
    return {
        "route_label": selected_scope.get("selected_route_id", "Unknown route"),
        "phase_label": phase_label(selected_scope.get("selected_phase", "other")),
        "cluster_label": selected_scope.get("selected_cluster_id", "Unknown cluster"),
    }


def enrich_screen3_payload(screen_3_response: dict, scope_display: dict) -> dict:
    enriched = deepcopy(screen_3_response)
    enriched.setdefault("payload", {})
    review_summary = enriched["payload"].setdefault("review_summary", {})
    review_summary["selected_scope_display"] = scope_display
    return enriched


def calculate_age(birth_date_value) -> Optional[int]:
    if not birth_date_value:
        return None

    if isinstance(birth_date_value, datetime):
        birth_date = birth_date_value.date()
    elif isinstance(birth_date_value, date):
        birth_date = birth_date_value
    elif hasattr(birth_date_value, "date") and callable(birth_date_value.date):
        try:
            birth_date = birth_date_value.date()
        except (TypeError, ValueError):
            return None
        if not isinstance(birth_date, date):
            return None
    elif isinstance(birth_date_value, str):
        try:
            birth_date = date.fromisoformat(birth_date_value)
        except ValueError:
            return None
    else:
        return None

    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def reviewed_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_prefill_value(criterion: dict):
    return criterion.get("ui_resolution", {}).get("prefill_value")


def merge_answers(screen_2_response: dict, approved_answers: dict):
    merged = deepcopy(screen_2_response)
    criteria = merged["payload"]["criteria"]

    satisfied_ids = []
    not_satisfied_ids = []
    unresolved_ids = []
    answered_criteria = []
    unanswered_required = []
    warnings = []
    conflict_count = 0

    for criterion in criteria:
        criterion_id = criterion["criterion_id"]
        answer = approved_answers.get(criterion_id)
        clinician_input = criterion["clinician_input"]
        ui_resolution = criterion["ui_resolution"]
        prefill_value = get_prefill_value(criterion)

        if answer is not None:
            clinician_answer = answer.get("answer")
            clinician_comment = answer.get("comment")
            clinician_value = answer.get("value")
            override_prefill = bool(answer.get("override_prefill", False))
            answered = clinician_answer is not None or bool(clinician_comment)

            clinician_input.update(
                {
                    "answer": clinician_answer,
                    "value": clinician_value,
                    "comment": clinician_comment,
                    "override_prefill": override_prefill,
                    "answered": answered,
                }
            )

            conflict_flag = (
                clinician_answer is not None
                and prefill_value is not None
                and clinician_answer != prefill_value
            )
            final_answer = clinician_answer
            final_source = "clinician"
            if conflict_flag:
                display_state = "conflict"
                conflict_count += 1
                warnings.append(f"{criterion_id}: clinician answer differs from chart prefill.")
            elif clinician_answer is True:
                display_state = "satisfied"
            elif clinician_answer is False:
                display_state = "not_satisfied"
            else:
                display_state = "unanswered"

            ui_resolution.update(
                {
                    "display_state": display_state,
                    "conflict_flag": conflict_flag,
                    "conflict_reason": (
                        "Clinician answer differs from chart prefill." if conflict_flag else None
                    ),
                    "final_answer": final_answer,
                    "final_source": final_source,
                }
            )

        final_answer = ui_resolution.get("final_answer")
        final_source = ui_resolution.get("final_source", "unresolved")
        display_state = ui_resolution.get("display_state", "unanswered")

        if final_answer is True:
            satisfied_ids.append(criterion_id)
            answered_criteria.append(
                {
                    "criterion_id": criterion_id,
                    "criterion_kind": criterion["criterion_kind"],
                    "prompt": criterion["prompt"],
                    "final_answer": True,
                    "final_source": final_source,
                    "display_state": display_state,
                    "comment": criterion["clinician_input"].get("comment"),
                }
            )
        elif final_answer is False:
            not_satisfied_ids.append(criterion_id)
            answered_criteria.append(
                {
                    "criterion_id": criterion_id,
                    "criterion_kind": criterion["criterion_kind"],
                    "prompt": criterion["prompt"],
                    "final_answer": False,
                    "final_source": final_source,
                    "display_state": display_state,
                    "comment": criterion["clinician_input"].get("comment"),
                }
            )
        else:
            unresolved_ids.append(criterion_id)
            if criterion.get("required", False):
                unanswered_required.append(
                    {
                        "criterion_id": criterion_id,
                        "prompt": criterion["prompt"],
                    }
                )

    if not_satisfied_ids:
        cluster_status = "not_satisfied"
        cluster_satisfied = False
    elif unresolved_ids:
        cluster_status = "unresolved"
        cluster_satisfied = False
    else:
        cluster_status = "satisfied"
        cluster_satisfied = True

    merged["payload"]["logic_evaluation"] = {
        "selected_cluster_satisfied": cluster_satisfied,
        "selected_cluster_status": cluster_status,
        "satisfied_criterion_ids": satisfied_ids,
        "not_satisfied_criterion_ids": not_satisfied_ids,
        "unresolved_criterion_ids": unresolved_ids,
        "criterion_counts": {
            "satisfied": len(satisfied_ids),
            "not_satisfied": len(not_satisfied_ids),
            "unresolved": len(unresolved_ids),
        },
    }
    merged["payload"]["next_action"] = (
        "stay_screen_2" if unresolved_ids else "proceed_screen_3"
    )

    review_result = {
        "approval_status": "edited" if approved_answers else "approved",
        "approved_criterion_answers": approved_answers,
        "reviewed_screen_2_payload": merged,
        "review_metadata": {
            "reviewer": None,
            "reviewed_at": reviewed_at(),
            "comment": None,
        },
        "human_validated": True,
    }

    review_summary = {
        "selected_scope": merged["payload"]["selected_scope"],
        "criterion_totals": {
            "total": len(criteria),
            "answered": len(answered_criteria),
            "unanswered_required": len(unanswered_required),
            "conflicts": conflict_count,
        },
        "logic_evaluation": merged["payload"]["logic_evaluation"],
    }

    if unanswered_required or conflict_count:
        screen3_status = "warning"
    else:
        screen3_status = "complete"

    screen3_response = {
        "status": screen3_status,
        "payload": {
            "review_summary": review_summary,
            "answered_criteria": answered_criteria,
            "unanswered_required_items": unanswered_required,
            "warnings": warnings,
            "submission_ready": not unanswered_required,
        },
        "messages": merged.get("messages", []),
    }

    return review_result, screen3_response
