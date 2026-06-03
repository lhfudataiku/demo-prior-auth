from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Optional

from scripts.agent_flow.functions.screen_payload_helpers import (
    build_screen3_payload_from_review_result_data,
    normalize_review_result_data,
)


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


def _attention_item(criterion: dict, message: str) -> dict:
    return {
        "criterion_id": criterion["criterion_id"],
        "criterion_kind": criterion.get("criterion_kind"),
        "prompt": criterion["prompt"],
        "display_state": criterion.get("ui_resolution", {}).get("display_state"),
        "message": message,
    }


def merge_answers(screen_2_response: dict, approved_answers: dict):
    review_result = normalize_review_result_data(
        {
            "approval_status": "edited" if approved_answers else "approved",
            "approved_criterion_answers": approved_answers,
            "reviewed_screen_2_payload": deepcopy(screen_2_response),
            "review_metadata": {
                "reviewer": None,
                "reviewed_at": reviewed_at(),
                "comment": None,
            },
            "human_validated": True,
        }
    )
    screen3_response = build_screen3_payload_from_review_result_data(review_result)
    return review_result, screen3_response
