import json
import threading
import time
import uuid

from flask import Blueprint, Flask, jsonify, request

try:
    import dataiku  # type: ignore
except ImportError:  # pragma: no cover
    dataiku = None

from scripts.agent_flow.functions.selection_resolver import build_screen1_payload
from webapps.prior_auth_review.backend.data_access import (
    _build_screen2_agent_request,
    _parse_json_object_from_text,
    default_billing_code,
    get_data_source,
    load_patient_id_options,
    load_patient_summary,
    load_policy_catalog,
    load_policy_master,
    load_route_index,
    load_screen2_response,
)
from webapps.prior_auth_review.backend.utils import (
    calculate_age,
    ensure_selected_scope_display,
    enrich_screen3_payload,
    merge_answers,
    resolve_selected_scope_display,
)


api = Blueprint("prior_auth_review_api", __name__, url_prefix="/api")
_run_lock = threading.Lock()
_runs = {}


def _catalog_item(policy_id: str):
    return load_policy_catalog().get(policy_id)


def _with_patient_age(patient_summary):
    if not patient_summary:
        return None
    summary = dict(patient_summary)
    summary["age"] = calculate_age(summary.get("birth_date"))
    return summary


def _resolve_selected_scope_context(policy_id: str, body: dict):
    payload = build_screen1_payload(
        route_index_v4=load_route_index(policy_id),
        policy_master_v4=load_policy_master(policy_id),
        billing_code=body.get("billing_code"),
        selected_phase=body.get("selected_phase"),
        selected_cluster_id=body.get("selected_cluster_id"),
        criterion_answers=body.get("criterion_answers"),
    )
    return payload.get("payload", {}).get("selected_scope_context")


def _safe_json_value(value):
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


def _append_run_event(run_id: str, event: dict):
    event["ts"] = time.time()
    with _run_lock:
        run = _runs.get(run_id)
        if run is not None:
            run["events"].append(event)


def _get_agent_llm():
    if dataiku is None:
        raise RuntimeError("Dataiku Python package is required when data source is 'dss'.")
    project = dataiku.api_client().get_default_project()
    return project.get_llm("agent:NkBiV9OM")


def _find_review_request_payload(hitl_requests, memory_fragment):
    def parse_json_string(raw):
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            return _parse_json_object_from_text(raw)
        except Exception:
            return None

    def search(value):
        if isinstance(value, dict):
            review_request = value.get("review_request")
            if isinstance(review_request, dict):
                return review_request
            for nested in value.values():
                found = search(nested)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = search(item)
                if found is not None:
                    return found
        elif isinstance(value, str):
            parsed = parse_json_string(value)
            if parsed is not None:
                found = search(parsed)
                if found is not None:
                    return found
        return None

    found = search(hitl_requests)
    if found is not None:
        return found
    return search(memory_fragment)


def _build_review_result(screen_2_response: dict, approved_answers: dict, review_metadata: dict):
    criteria = ((screen_2_response or {}).get("payload", {}) or {}).get("criteria", []) or []
    changed = False
    for criterion in criteria:
        criterion_id = criterion.get("criterion_id")
        if not isinstance(criterion_id, str):
            continue
        original = ((criterion.get("clinician_input") or {}).get("answer"))
        updated = ((approved_answers.get(criterion_id) or {}).get("answer"))
        if updated is not None and updated != original:
            changed = True
            break
    return {
        "approval_status": "edited" if changed else "approved",
        "approved_criterion_answers": approved_answers,
        "reviewed_screen_2_payload": screen_2_response,
        "review_metadata": {
            "reviewer": review_metadata.get("reviewer"),
            "reviewed_at": review_metadata.get("reviewed_at"),
            "comment": review_metadata.get("comment"),
        },
        "human_validated": True,
    }


def _run_dss_completion(
    run_id: str,
    agent_request: dict,
    original_query: str,
    memory_fragment=None,
    hitl_requests=None,
    validated=None,
    approved_review_request=None,
    context=None,
    review_result=None,
):
    try:
        llm = _get_agent_llm()
        completion = llm.new_completion()
        completion.with_message(original_query, role="user")

        if memory_fragment is not None and hitl_requests is not None:
            completion.cq["messages"].append({"role": "memoryFragment", "memoryFragment": memory_fragment})
            completion.cq["messages"].append({"role": "toolValidationRequests", "toolValidationRequests": hitl_requests})
            completion.cq["messages"].append(
                {
                    "role": "toolValidationResponses",
                    "toolValidationResponses": [
                        {
                            "validationRequestId": req["id"],
                            "validated": validated,
                            "arguments": (
                                json.dumps({"review_request": approved_review_request})
                                if approved_review_request is not None
                                else None
                            ),
                        }
                        for req in hitl_requests
                    ],
                }
            )
            if context is not None:
                completion.with_context(context)

        text_buf = []
        pending_hitl_requests = None
        pending_memory_fragment = None
        pending_context = None
        pending_screen3 = None

        for chunk in completion.execute_streamed():
            if type(chunk).__name__ == "DSSLLMStreamedCompletionFooter":
                footer_data = chunk.data or {}
                upsert = footer_data.get("contextUpsert")
                if isinstance(upsert, dict):
                    pending_context = upsert

                if pending_hitl_requests is not None:
                    review_request = _find_review_request_payload(
                        pending_hitl_requests,
                        pending_memory_fragment,
                    )
                    if not isinstance(review_request, dict):
                        raise RuntimeError("Unable to extract review_request from HITL payload.")
                    screen_2_payload = review_request.get("screen_2_payload")
                    criterion_answers = review_request.get("criterion_answers", {}) or {}
                    with _run_lock:
                        _runs[run_id].update(
                            {
                                "status": "hitl_paused",
                                "hitl_payload": {
                                    "requests": pending_hitl_requests,
                                    "memory_fragment": pending_memory_fragment or {},
                                    "original_query": original_query,
                                    "message": pending_hitl_requests[0].get("message", ""),
                                    "context": pending_context,
                                    "review_request": review_request,
                                },
                                "screen_2_response": screen_2_payload,
                                "edited_answers": criterion_answers,
                            }
                        )
                else:
                    final_text = "".join(text_buf).strip()
                    parsed = _parse_json_object_from_text(final_text) if final_text else None
                    if isinstance(parsed, dict) and parsed.get("payload"):
                        pending_screen3 = parsed
                    with _run_lock:
                        _runs[run_id].update(
                            {
                                "status": "completed",
                                "final_output": final_text,
                                "screen_3_response": pending_screen3,
                                "review_result": review_result,
                                "completed_at": time.time(),
                            }
                        )
                return

            chunk_type = getattr(chunk, "type", None)
            chunk_data = getattr(chunk, "data", {}) or {}
            text = getattr(chunk, "text", None) or ""

            if chunk_type != "content":
                _append_run_event(
                    run_id,
                    {"type": "chunk", "chunk_type": chunk_type, "data": _safe_json_value(chunk_data)},
                )
                continue

            if "toolValidationRequests" in chunk_data:
                pending_hitl_requests = (pending_hitl_requests or []) + chunk_data["toolValidationRequests"]
                _append_run_event(run_id, {"type": "hitl_detected"})

            if "memoryFragment" in chunk_data:
                pending_memory_fragment = chunk_data["memoryFragment"]

            if text:
                text_buf.append(text)
                with _run_lock:
                    _runs[run_id]["text_so_far"] += text
        raise RuntimeError("Structured agent stream ended without a terminal footer.")
    except Exception as exc:
        with _run_lock:
            if run_id in _runs:
                _runs[run_id].update(
                    {
                        "status": "failed",
                        "error": str(exc),
                        "completed_at": time.time(),
                    }
                )


@api.route("/scenarios", methods=["GET"])
def list_scenarios():
    catalog = load_policy_catalog()
    items = [catalog[policy_id] for policy_id in sorted(catalog)]
    return jsonify({"items": items})


@api.route("/runtime", methods=["GET"])
def get_runtime():
    return jsonify({"data_source": get_data_source()})


@api.route("/scenarios/<policy_id>/screen1/bootstrap", methods=["GET"])
def get_screen1_bootstrap(policy_id: str):
    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    payload = build_screen1_payload(
        route_index_v4=load_route_index(policy_id),
        policy_master_v4=load_policy_master(policy_id),
        billing_code=default_billing_code(policy_id),
    )
    payload["patient_summary"] = None
    payload["patient_id_options"] = load_patient_id_options()
    payload["scenario"] = scenario
    return jsonify(payload)


@api.route("/scenarios/<policy_id>/screen1/advance", methods=["POST"])
def advance_screen1(policy_id: str):
    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    payload = build_screen1_payload(
        route_index_v4=load_route_index(policy_id),
        policy_master_v4=load_policy_master(policy_id),
        billing_code=body.get("billing_code"),
        selected_phase=body.get("selected_phase"),
        selected_cluster_id=body.get("selected_cluster_id"),
        criterion_answers=body.get("criterion_answers"),
    )
    payload["patient_summary"] = None
    payload["patient_id_options"] = load_patient_id_options()
    payload["scenario"] = scenario
    return jsonify(payload)


@api.route("/scenarios/<policy_id>/bootstrap", methods=["POST"])
def get_bootstrap(policy_id: str):
    if get_data_source() == "dss":
        return jsonify({"error": "Use /api/scenarios/<policy_id>/screen2/run in dss mode."}), 400

    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    selected_scope_context = _resolve_selected_scope_context(policy_id, body)
    if not isinstance(selected_scope_context, dict) or not selected_scope_context:
        return jsonify({"error": "Screen 2 bootstrap requires a resolved Screen 1 scope."}), 400

    subject_id = body.get("subject_id")
    patient_summary = _with_patient_age(load_patient_summary(subject_id)) if subject_id else None
    raw_screen_2_response = load_screen2_response(
        policy_id,
        subject_id,
        selected_scope_context=selected_scope_context,
        criterion_answers=body.get("criterion_answers"),
    )
    scope_display = resolve_selected_scope_display(
        selected_scope_context=selected_scope_context,
        screen_2_response=raw_screen_2_response,
    )
    screen_2_response = ensure_selected_scope_display(raw_screen_2_response, scope_display)

    return jsonify(
        {
            "scenario": scenario,
            "patient_summary": patient_summary,
            "screen_2_response": screen_2_response,
        }
    )


@api.route("/scenarios/<policy_id>/screen2/run", methods=["POST"])
def start_screen2_run(policy_id: str):
    if get_data_source() != "dss":
        return jsonify({"error": "Screen 2 agent runs are only available in dss mode."}), 400

    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    selected_scope_context = _resolve_selected_scope_context(policy_id, body)
    if not isinstance(selected_scope_context, dict) or not selected_scope_context:
        return jsonify({"error": "Screen 2 run requires a resolved Screen 1 scope."}), 400

    subject_id = body.get("subject_id")
    patient_summary = _with_patient_age(load_patient_summary(subject_id)) if subject_id else None
    criterion_answers = body.get("criterion_answers", {}) or {}
    agent_request = _build_screen2_agent_request(
        policy_id,
        subject_id,
        selected_scope_context,
        criterion_answers=criterion_answers,
    )
    original_query = json.dumps(agent_request)
    run_id = str(uuid.uuid4())
    with _run_lock:
        _runs[run_id] = {
            "status": "running",
            "text_so_far": "",
            "events": [],
            "hitl_payload": None,
            "screen_2_response": None,
            "screen_3_response": None,
            "edited_answers": {},
            "review_result": None,
            "error": None,
            "completed_at": None,
        }
    threading.Thread(
        target=_run_dss_completion,
        args=(run_id, agent_request, original_query),
        daemon=True,
    ).start()
    return jsonify(
        {
            "run_id": run_id,
            "scenario": scenario,
            "patient_summary": patient_summary,
        }
    )


@api.route("/runs/<run_id>/state", methods=["GET"])
def get_run_state(run_id: str):
    with _run_lock:
        run = dict(_runs.get(run_id, {}))
    if not run:
        return jsonify({"error": f"Unknown run_id: {run_id}"}), 404
    return jsonify(run)


@api.route("/runs/<run_id>/hitl/respond", methods=["POST"])
def respond_run_hitl(run_id: str):
    if get_data_source() != "dss":
        return jsonify({"error": "HITL responses are only available in dss mode."}), 400

    body = request.get_json(force=True) or {}
    with _run_lock:
        run = _runs.get(run_id)
        if run is None:
            return jsonify({"error": f"Unknown run_id: {run_id}"}), 404
        hitl_payload = run.get("hitl_payload")
        screen_2_response = run.get("screen_2_response")
    if not isinstance(hitl_payload, dict):
        return jsonify({"error": "Run is not waiting for human validation."}), 400

    approved_answers = body.get("approved_criterion_answers", {}) or {}
    review_metadata = body.get("review_metadata", {}) or {}
    approved_review_request = dict(hitl_payload.get("review_request") or {})
    approved_review_request["criterion_answers"] = approved_answers
    review_result = _build_review_result(screen_2_response, approved_answers, review_metadata)

    with _run_lock:
        run = _runs[run_id]
        run.update(
            {
                "status": "running",
                "text_so_far": "",
                "events": [],
                "review_result": review_result,
                "edited_answers": approved_answers,
                "error": None,
            }
        )

    threading.Thread(
        target=_run_dss_completion,
        args=(
            run_id,
            {},
            hitl_payload["original_query"],
        ),
        kwargs={
            "memory_fragment": hitl_payload.get("memory_fragment"),
            "hitl_requests": hitl_payload.get("requests"),
            "validated": True,
            "approved_review_request": approved_review_request,
            "context": hitl_payload.get("context"),
            "review_result": review_result,
        },
        daemon=True,
    ).start()
    return jsonify({"status": "resuming"})


@api.route("/scenarios/<policy_id>/review", methods=["POST"])
def submit_review(policy_id: str):
    if get_data_source() == "dss":
        return jsonify({"error": "Use /api/runs/<run_id>/hitl/respond in dss mode."}), 400

    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    selected_scope_context = _resolve_selected_scope_context(policy_id, body)
    if not isinstance(selected_scope_context, dict) or not selected_scope_context:
        return jsonify({"error": "Review submission requires a resolved Screen 1 scope."}), 400

    screen_2_response = load_screen2_response(
        policy_id,
        body.get("subject_id"),
        selected_scope_context=selected_scope_context,
        criterion_answers=body.get("criterion_answers"),
    )
    scope_display = resolve_selected_scope_display(
        selected_scope_context=selected_scope_context,
        screen_2_response=screen_2_response,
    )
    screen_2_response = ensure_selected_scope_display(screen_2_response, scope_display)

    approved_answers = body.get("approved_criterion_answers", {}) or {}
    review_metadata = body.get("review_metadata", {}) or {}
    review_result, screen_3_response = merge_answers(screen_2_response, approved_answers)

    review_result["review_metadata"].update(
        {
            "reviewer": review_metadata.get("reviewer"),
            "comment": review_metadata.get("comment"),
        }
    )
    screen_3_response = enrich_screen3_payload(screen_3_response, scope_display)

    return jsonify(
        {
            "review_result": review_result,
            "screen_3_response": screen_3_response,
        }
    )


@api.route("/patients/<subject_id>", methods=["GET"])
def get_patient_summary(subject_id: str):
    return jsonify(_with_patient_age(load_patient_summary(subject_id)))


def register_routes(flask_app: Flask):
    flask_app.register_blueprint(api)


def create_app():
    flask_app = Flask(__name__)
    register_routes(flask_app)
    return flask_app


if "app" in globals():
    register_routes(app)  # type: ignore[name-defined]
