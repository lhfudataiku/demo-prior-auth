import json
import os
from csv import DictReader
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Blueprint, Flask, jsonify, request
from scripts.agent_flow.functions.selection_resolver import build_screen1_payload

try:
    import dataiku  # type: ignore
except ImportError:  # pragma: no cover - local fallback outside DSS
    dataiku = None


REPO_ROOT = Path(__file__).resolve().parents[3]
PATIENT_FIXTURE_PATH = REPO_ROOT / "scripts" / "artifacts" / "fixtures" / "Patient.csv"
POLICY_ARTIFACT_ROOT = REPO_ROOT / "scripts" / "artifacts" / "policy_artifacts"
POLICY_ARTIFACTS_CSV_PATH = POLICY_ARTIFACT_ROOT / "policy_artifacts.csv"
SCREEN_PAYLOAD_FIXTURE_ROOT = REPO_ROOT / "scripts" / "artifacts" / "fixtures" / "screen_payloads"
STRUCTURED_AGENT_ID = "NkBiV9OM"
STRUCTURED_AGENT_VERSION = "v2"
PATIENT_DATASET_NAME = os.environ.get("PRIOR_AUTH_PATIENT_DATASET", "Patient")
POLICY_ARTIFACTS_DATASET_NAME = os.environ.get(
    "PRIOR_AUTH_POLICY_ARTIFACTS_DATASET", "policy_artifacts"
)
USE_DSS_AGENT = os.environ.get("PRIOR_AUTH_USE_DSS_AGENT", "").lower() in {"1", "true", "yes"}


api = Blueprint("prior_auth_review_api", __name__, url_prefix="/api")


def _load_dataset_rows(dataset_name: str, columns: Optional[list[str]] = None):
    if dataiku is None:
        return None
    try:
        dataset = dataiku.Dataset(dataset_name)
        dataframe = dataset.get_dataframe()
    except Exception:
        return None
    if columns:
        available = [column for column in columns if column in dataframe.columns]
        if available:
            dataframe = dataframe[available]
    return dataframe.to_dict(orient="records")


def _load_json(policy_id: str, filename: str):
    primary = POLICY_ARTIFACT_ROOT / policy_id / filename
    fallback = SCREEN_PAYLOAD_FIXTURE_ROOT / policy_id / filename
    path = primary if primary.exists() else fallback
    with path.open() as stream:
        return json.load(stream)


def _load_policy_catalog():
    items = {}
    rows = _load_dataset_rows(
        POLICY_ARTIFACTS_DATASET_NAME,
        columns=["policy_id", "document_type", "policy_master_v4"],
    )
    if rows is None:
        with POLICY_ARTIFACTS_CSV_PATH.open() as stream:
            rows = list(DictReader(stream))
    for row in rows:
        policy_id = row.get("policy_id")
        if not policy_id:
            continue
        if not (POLICY_ARTIFACT_ROOT / policy_id / "policy_master_v4.json").exists():
            continue
        title = policy_id
        description = row.get("document_type") or "Coverage policy"
        try:
            policy_master = json.loads(row.get("policy_master_v4") or "{}")
            title = policy_master.get("title") or title
        except json.JSONDecodeError:
            pass
        items[policy_id] = {
            "policy_id": policy_id,
            "label": title,
            "description": description,
        }
    return items


def _build_screen2_agent_request(policy_id: str, subject_id: Optional[str], selected_scope_context: dict):
    criterion_answers = selected_scope_context.get("criterion_answers", {}) or {}
    return {
        "session_id": None,
        "subject_id": subject_id,
        "policy_id": policy_id,
        "screen_id": "screen_2",
        "payload": {
            "selected_route_id": selected_scope_context.get("selected_route_id"),
            "selected_phase": selected_scope_context.get("selected_phase"),
            "selected_cluster_id": selected_scope_context.get("selected_cluster_id"),
            "scoped_policy_context": selected_scope_context,
            "policy_master_v4": _load_policy_master(policy_id),
            "retrieval_plan_v1": None,
            "criterion_answers": criterion_answers,
        },
    }


def _load_screen2_response_from_dss_agent(policy_id: str, subject_id: Optional[str] = None):
    if dataiku is None or not USE_DSS_AGENT:
        return None
    selected_scope_context = _load_selected_scope_context(policy_id)
    agent_request = _build_screen2_agent_request(policy_id, subject_id, selected_scope_context)
    try:
        client = dataiku.api_client()
        project = client.get_default_project()
        llm = project.get_llm(f"agent:{STRUCTURED_AGENT_ID}:{STRUCTURED_AGENT_VERSION}")
        completion = llm.new_completion()
        response = completion.with_message(json.dumps(agent_request), role="user").execute()
        if not getattr(response, "success", True):
            return None
        text = getattr(response, "text", None)
        if not text:
            return None
        payload = json.loads(text)
        if isinstance(payload, dict) and "payload" in payload:
            return payload
    except Exception:
        return None
    return None


POLICY_CATALOG = _load_policy_catalog()


def _load_structured_agent_state(policy_id: str):
    raw = _load_json(policy_id, "structured_agent_context.json")
    context = raw.get("context", {})
    graph_state_key = next(
        (key for key in context if key.startswith("_blocksGraphState_")),
        None,
    )
    if not graph_state_key:
        raise KeyError(f"No block graph state found in structured_agent_context for {policy_id}")
    return context[graph_state_key]


def _load_selected_scope_context(policy_id: str):
    try:
        state = _load_structured_agent_state(policy_id)
        scoped = state.get("selected_scope_context")
        if isinstance(scoped, dict) and scoped:
            return scoped
    except FileNotFoundError:
        pass

    candidates = sorted((POLICY_ARTIFACT_ROOT / policy_id).glob("selected_scope_context*.json"))
    if not candidates:
        candidates = sorted((SCREEN_PAYLOAD_FIXTURE_ROOT / policy_id).glob("selected_scope_context*.json"))
    if not candidates:
        raise FileNotFoundError(f"No selected_scope_context artifact found for {policy_id}")
    with candidates[0].open() as stream:
        raw = json.load(stream)
    return raw.get("scoped_policy_context", raw) if isinstance(raw, dict) else raw


def _load_screen2_response(policy_id: str, subject_id: Optional[str] = None):
    live_payload = _load_screen2_response_from_dss_agent(policy_id, subject_id)
    if isinstance(live_payload, dict):
        return live_payload

    # Local/dev fallback: read the regenerated artifact or frozen fixture.
    try:
        state = _load_structured_agent_state(policy_id)
        payload = state.get("screen_2_payload")
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        pass

    fixture_path = SCREEN_PAYLOAD_FIXTURE_ROOT / policy_id / "screen_2_response.json"
    with fixture_path.open() as stream:
        return json.load(stream)


def _load_route_index(policy_id: str):
    path = POLICY_ARTIFACT_ROOT / policy_id / "route_index_v4.json"
    with path.open() as stream:
        return json.load(stream)


def _load_policy_master(policy_id: str):
    path = POLICY_ARTIFACT_ROOT / policy_id / "policy_master_v4.json"
    with path.open() as stream:
        return json.load(stream)


def _default_billing_code(policy_id: str):
    route_index = _load_route_index(policy_id)
    try:
        selected_scope_context = _load_selected_scope_context(policy_id)
        selected_route_id = selected_scope_context.get("selected_route_id")
    except FileNotFoundError:
        selected_route_id = None
    for route in route_index.get("routes", []):
        if not isinstance(route, dict):
            continue
        if selected_route_id and route.get("route_id") != selected_route_id:
            continue
        for code in route.get("billing_codes", []):
            if isinstance(code, str) and code:
                return code
    return None


def _phase_label(phase: str):
    return {
        "initial": "Initial",
        "continuation": "Continuation",
        "other": "Other",
    }.get(phase, phase.title())


def _selected_scope_display(selected_scope_context: dict):
    selected_route = selected_scope_context.get("selected_route", {}) or {}
    selected_cluster_summary = selected_scope_context.get("selected_cluster_summary", {}) or {}
    selected_cluster = selected_scope_context.get("selected_cluster", {}) or {}
    return {
        "route_label": selected_route.get("label") or selected_scope_context.get("selected_route_label") or selected_scope_context.get("selected_route_id"),
        "phase_label": selected_scope_context.get("selected_phase_label") or _phase_label(selected_scope_context.get("selected_phase", "other")),
        "cluster_label": (
            selected_cluster.get("label")
            or selected_cluster_summary.get("condition_label")
            or selected_scope_context.get("selected_cluster_label")
            or selected_scope_context.get("selected_cluster_id")
        ),
    }


def _ensure_selected_scope_display(screen_2_response: dict, selected_scope_display: dict):
    enriched = deepcopy(screen_2_response)
    enriched.setdefault("payload", {})
    enriched["payload"]["selected_scope_display"] = selected_scope_display
    return enriched


def _resolve_selected_scope_display(policy_id: str, screen_2_response: Optional[dict] = None):
    try:
        return _selected_scope_display(_load_selected_scope_context(policy_id))
    except FileNotFoundError:
        payload = (screen_2_response or {}).get("payload", {})
        display = payload.get("selected_scope_display")
        if isinstance(display, dict) and display:
            return display
        selected_scope = payload.get("selected_scope", {})
        return {
            "route_label": selected_scope.get("selected_route_id", "Unknown route"),
            "phase_label": _phase_label(selected_scope.get("selected_phase", "other")),
            "cluster_label": selected_scope.get("selected_cluster_id", "Unknown cluster"),
        }


def _enrich_screen3_payload(screen_3_response: dict, selected_scope_display: dict):
    enriched = deepcopy(screen_3_response)
    enriched.setdefault("payload", {})
    review_summary = enriched["payload"].setdefault("review_summary", {})
    review_summary["selected_scope_display"] = selected_scope_display
    return enriched


def _calculate_age(birth_date_value: Optional[str]):
    if not birth_date_value:
        return None
    try:
        birth_date = date.fromisoformat(birth_date_value)
    except ValueError:
        return None
    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _load_patient_summary(subject_id: str):
    rows = _load_dataset_rows(
        PATIENT_DATASET_NAME,
        columns=["subject_id", "gender", "birth_date"],
    )
    if rows is None:
        # Local/dev fallback: read the fixture CSV.
        if not PATIENT_FIXTURE_PATH.exists():
            return {
                "subject_id": subject_id,
                "gender": None,
                "birth_date": None,
                "age": None,
            }
        with PATIENT_FIXTURE_PATH.open() as stream:
            rows = list(DictReader(stream))
    for row in rows:
        if row.get("subject_id") == subject_id:
            birth_date_value = row.get("birth_date")
            return {
                "subject_id": subject_id,
                "gender": row.get("gender"),
                "birth_date": birth_date_value,
                "age": _calculate_age(birth_date_value),
            }
    return {
        "subject_id": subject_id,
        "gender": None,
        "birth_date": None,
        "age": None,
    }


def _load_patient_id_options():
    rows = _load_dataset_rows(PATIENT_DATASET_NAME, columns=["subject_id"])
    if rows is None:
        if not PATIENT_FIXTURE_PATH.exists():
            return []
        with PATIENT_FIXTURE_PATH.open() as stream:
            rows = list(DictReader(stream))
    subject_ids = []
    for row in rows:
        subject_id = row.get("subject_id")
        if subject_id:
            subject_ids.append(subject_id)
    return sorted(set(subject_ids))


def _reviewed_at():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get_prefill_value(criterion: dict):
    return criterion.get("ui_resolution", {}).get("prefill_value")


def _merge_answers(screen_2_response: dict, approved_answers: dict):
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
        prefill_value = _get_prefill_value(criterion)

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
            "reviewed_at": _reviewed_at(),
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

    if unanswered_required:
        screen3_status = "warning"
    elif conflict_count:
        screen3_status = "warning"
    elif not_satisfied_ids:
        screen3_status = "complete"
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


@api.route("/scenarios", methods=["GET"])
def list_scenarios():
    items = [POLICY_CATALOG[policy_id] for policy_id in sorted(POLICY_CATALOG)]
    return jsonify({"items": items})


@api.route("/scenarios/<policy_id>/screen1/bootstrap", methods=["GET"])
def get_screen1_bootstrap(policy_id: str):
    if policy_id not in POLICY_CATALOG:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    billing_code = _default_billing_code(policy_id)
    payload = build_screen1_payload(
        route_index_v4=_load_route_index(policy_id),
        policy_master_v4=_load_policy_master(policy_id),
        billing_code=billing_code,
    )
    payload["patient_summary"] = None
    payload["patient_id_options"] = _load_patient_id_options()
    payload["scenario"] = POLICY_CATALOG[policy_id]
    return jsonify(payload)


@api.route("/scenarios/<policy_id>/screen1/advance", methods=["POST"])
def advance_screen1(policy_id: str):
    if policy_id not in POLICY_CATALOG:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    payload = build_screen1_payload(
        route_index_v4=_load_route_index(policy_id),
        policy_master_v4=_load_policy_master(policy_id),
        billing_code=body.get("billing_code"),
        selected_phase=body.get("selected_phase"),
        selected_cluster_id=body.get("selected_cluster_id"),
        criterion_answers=body.get("criterion_answers"),
    )
    payload["patient_summary"] = None
    payload["patient_id_options"] = _load_patient_id_options()
    payload["scenario"] = POLICY_CATALOG[policy_id]
    return jsonify(payload)


@api.route("/scenarios/<policy_id>/bootstrap", methods=["GET"])
def get_bootstrap(policy_id: str):
    if policy_id not in POLICY_CATALOG:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    subject_id = request.args.get("subject_id")
    patient_summary = _load_patient_summary(subject_id) if subject_id else None
    raw_screen_2_response = _load_screen2_response(policy_id, subject_id)
    selected_scope_display = _resolve_selected_scope_display(policy_id, raw_screen_2_response)
    screen_2_response = _ensure_selected_scope_display(raw_screen_2_response, selected_scope_display)

    payload = {
        "scenario": POLICY_CATALOG[policy_id],
        "patient_summary": patient_summary,
        "screen_2_response": screen_2_response,
    }
    return jsonify(payload)


@api.route("/scenarios/<policy_id>/review", methods=["POST"])
def submit_review(policy_id: str):
    if policy_id not in POLICY_CATALOG:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    screen_2_response = _load_screen2_response(policy_id, body.get("subject_id"))
    selected_scope_display = _resolve_selected_scope_display(policy_id, screen_2_response)
    screen_2_response = _ensure_selected_scope_display(screen_2_response, selected_scope_display)
    approved_answers = body.get("approved_criterion_answers", {}) or {}
    review_metadata = body.get("review_metadata", {}) or {}

    review_result, screen_3_response = _merge_answers(screen_2_response, approved_answers)
    review_result["review_metadata"].update(
        {
            "reviewer": review_metadata.get("reviewer"),
            "comment": review_metadata.get("comment"),
        }
    )
    screen_3_response = _enrich_screen3_payload(screen_3_response, selected_scope_display)

    return jsonify(
        {
            "review_result": review_result,
            "screen_3_response": screen_3_response,
        }
    )


@api.route("/patients/<subject_id>", methods=["GET"])
def get_patient_summary(subject_id: str):
    return jsonify(_load_patient_summary(subject_id))


def register_routes(flask_app: Flask):
    flask_app.register_blueprint(api)


def create_app():
    flask_app = Flask(__name__)
    register_routes(flask_app)
    return flask_app


if "app" in globals():
    register_routes(app)  # type: ignore[name-defined]
