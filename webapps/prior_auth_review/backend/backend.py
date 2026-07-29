import json
import threading
import time
import uuid

from flask import Blueprint, Flask, jsonify, request

try:
    import dataiku  # type: ignore
except ImportError:  # pragma: no cover
    dataiku = None

from scripts.agent_flow.functions.selection_resolver import (
    build_screen1_payload,
    resolve_selection_scope,
)
from scripts.agent_flow.functions.screen_payload_helpers import (
    build_screen3_payload_from_review_result_data,
    normalize_review_result_data,
)
from webapps.prior_auth_review.backend.agent_transport import (
    extract_graph_state,
    extract_review_result_from_graph,
)
from webapps.prior_auth_review.backend.data_access import (
    _build_screen2_agent_request,
    _parse_json_object_from_text,
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
    resolved = resolve_selection_scope(
        route_index_v4=load_route_index(policy_id),
        policy_master_v4=load_policy_master(policy_id),
        billing_code=body.get("billing_code"),
        selected_phase=body.get("selected_phase"),
        selected_cluster_id=body.get("selected_cluster_id"),
    )
    if not isinstance(resolved, dict):
        return None
    return resolved.get("scoped_policy_context")


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


def _parse_embedded_json(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _parse_json_object_from_text(value)
    except Exception:
        return None


def _extract_review_request_from_graph(graph_state):
    if not isinstance(graph_state, dict):
        return None
    request_human_review = graph_state.get("request_human_review")
    if not isinstance(request_human_review, dict):
        return None
    tool_input = request_human_review.get("screen_2_review_tool_input")
    if isinstance(tool_input, dict) and isinstance(tool_input.get("screen_2_payload"), dict):
        return tool_input
    return None


def _extract_tool_validation_requests_from_footer(footer_data):
    if not isinstance(footer_data, dict):
        return []

    if isinstance(footer_data.get("toolValidationRequests"), list):
        return footer_data["toolValidationRequests"]

    additional = footer_data.get("additionalInformation")
    if not isinstance(additional, dict):
        return []

    trajectory = additional.get("trajectory")
    if not isinstance(trajectory, dict):
        return []

    for key in ("outputs", "output"):
        candidate = trajectory.get(key)
        if isinstance(candidate, dict) and isinstance(candidate.get("toolValidationRequests"), list):
            return candidate["toolValidationRequests"]
    return []


def _extract_review_request_from_tool_validation_requests(tool_validation_requests):
    if not isinstance(tool_validation_requests, list):
        return None

    for request in tool_validation_requests:
        if not isinstance(request, dict):
            continue
        tool_call = request.get("toolCall")
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict):
            continue
        arguments = function.get("arguments")
        if isinstance(arguments, dict):
            review_request = arguments.get("review_request")
            if isinstance(review_request, dict):
                return review_request
        parsed = _parse_embedded_json(arguments)
        if isinstance(parsed, dict):
            review_request = parsed.get("review_request")
            if isinstance(review_request, dict):
                return review_request
    return None


def _count_total_criteria(graph_state):
    if not isinstance(graph_state, dict):
        return None

    retrieval_plan = graph_state.get("retrieval_plan_v1")
    if isinstance(retrieval_plan, dict):
        flattened = retrieval_plan.get("flattened_criteria")
        if isinstance(flattened, list):
            return len(flattened)

        total = 0
        found = False
        for key in (
            "selected_route_guard_criterion_ids",
            "selected_cluster_entry_guard_criterion_ids",
            "selected_inherited_diagnosis_criterion_ids",
            "selected_cluster_criterion_ids",
        ):
            items = retrieval_plan.get(key)
            if isinstance(items, list):
                total += len(items)
                found = True
        if found:
            return total

    screen_2_payload = graph_state.get("screen_2_payload")
    if isinstance(screen_2_payload, dict):
        criteria = ((screen_2_payload.get("payload") or {}).get("criteria") or [])
        if isinstance(criteria, list):
            return len(criteria)

    return None


def _extract_current_criterion(graph_state):
    if not isinstance(graph_state, dict):
        return None

    loop_state = graph_state.get("plain_item_loop")
    if isinstance(loop_state, dict):
        current_item = loop_state.get("currentItem")
        if isinstance(current_item, dict):
            return current_item

    reasoning_result = _parse_embedded_json(graph_state.get("current_reasoning_result"))
    if isinstance(reasoning_result, dict):
        return {
            "criterion_id": reasoning_result.get("criterion_id"),
            "prompt": reasoning_result.get("prompt"),
        }
    return None


def _extract_progress_from_graph(graph_state, chunk_data):
    if not isinstance(graph_state, dict):
        return None

    current_item = _extract_current_criterion(graph_state) or {}
    execution = ((chunk_data.get("eventData") or {}).get("execution") or {}) if isinstance(chunk_data, dict) else {}
    iteration_number = execution.get("iterationNumber")
    criterion_result_map = graph_state.get("criterion_result_map")
    completed = len(criterion_result_map) if isinstance(criterion_result_map, dict) else 0
    if isinstance(iteration_number, int):
        completed = max(completed, iteration_number)

    total = _count_total_criteria(graph_state)
    return {
        "current_block_id": graph_state.get("_currentBlockId"),
        "current_criterion_id": current_item.get("criterion_id"),
        "current_criterion_prompt": current_item.get("prompt"),
        "completed_criteria": completed,
        "total_criteria": total,
    }


def _extract_screen2_snapshot_from_graph(graph_state):
    if not isinstance(graph_state, dict):
        return None

    payload = graph_state.get("screen_2_payload")
    if isinstance(payload, dict) and isinstance(payload.get("payload"), dict):
        return payload

    review_request = _extract_review_request_from_graph(graph_state)
    if isinstance(review_request, dict):
        nested_payload = review_request.get("screen_2_payload")
        if isinstance(nested_payload, dict) and isinstance(nested_payload.get("payload"), dict):
            return nested_payload
    return None


def _extract_criterion_answers_from_graph(graph_state):
    if not isinstance(graph_state, dict):
        return None

    criterion_answers = graph_state.get("criterion_answers")
    if isinstance(criterion_answers, dict):
        return criterion_answers

    review_request = _extract_review_request_from_graph(graph_state)
    if isinstance(review_request, dict):
        nested_answers = review_request.get("criterion_answers")
        if isinstance(nested_answers, dict):
            return nested_answers
    return None


def _extract_stream_state(chunk_data):
    if not isinstance(chunk_data, dict):
        return {}

    graph_state = extract_graph_state(chunk_data)
    review_request = _extract_review_request_from_graph(graph_state)
    progress = _extract_progress_from_graph(graph_state, chunk_data)
    screen2_snapshot = _extract_screen2_snapshot_from_graph(graph_state)
    criterion_answers = _extract_criterion_answers_from_graph(graph_state)
    event_data = chunk_data.get("eventData") if isinstance(chunk_data.get("eventData"), dict) else {}
    execution = event_data.get("execution") if isinstance(event_data.get("execution"), dict) else {}

    event = {
        "type": "agent_event",
        "event_kind": chunk_data.get("eventKind"),
        "block_id": event_data.get("blockId"),
        "iteration_number": execution.get("iterationNumber"),
    }
    if isinstance(progress, dict):
        event["progress"] = progress

    return {
        "event": event,
        "graph_state": graph_state,
        "review_request": review_request,
        "progress": progress,
        "screen2_snapshot": screen2_snapshot,
        "criterion_answers": criterion_answers,
    }


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
    return normalize_review_result_data(
        {
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
    )


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
        pending_review_request = None
        pending_progress = None
        pending_screen2_snapshot = None
        pending_criterion_answers = None

        for chunk in completion.execute_streamed():
            if type(chunk).__name__ == "DSSLLMStreamedCompletionFooter":
                footer_data = chunk.data or {}
                upsert = footer_data.get("contextUpsert")
                if isinstance(upsert, dict):
                    pending_context = upsert

                footer_hitl_requests = _extract_tool_validation_requests_from_footer(footer_data)
                if footer_hitl_requests:
                    pending_hitl_requests = footer_hitl_requests

                footer_review_request = _extract_review_request_from_tool_validation_requests(pending_hitl_requests)
                if isinstance(footer_review_request, dict):
                    pending_review_request = footer_review_request
                    footer_screen2_snapshot = footer_review_request.get("screen_2_payload")
                    if isinstance(footer_screen2_snapshot, dict):
                        pending_screen2_snapshot = footer_screen2_snapshot
                    footer_answers = footer_review_request.get("criterion_answers")
                    if isinstance(footer_answers, dict):
                        pending_criterion_answers = footer_answers

                if pending_hitl_requests is not None:
                    review_request = pending_review_request
                    if not isinstance(review_request, dict):
                        raise RuntimeError("Unable to extract review_request from HITL payload.")
                    screen_2_payload = review_request.get("screen_2_payload") or pending_screen2_snapshot
                    criterion_answers = review_request.get("criterion_answers", {}) or pending_criterion_answers or {}
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
                                "screen_2_snapshot": screen_2_payload,
                                "edited_answers": criterion_answers,
                                "progress": pending_progress,
                            }
                        )
                else:
                    final_text = "".join(text_buf).strip()
                    final_graph_state = extract_graph_state(pending_context)
                    final_review_result = (
                        extract_review_result_from_graph(final_graph_state)
                        or normalize_review_result_data(review_result)
                    )
                    if isinstance(final_review_result, dict) and final_review_result:
                        pending_screen3 = build_screen3_payload_from_review_result_data(final_review_result)
                        pending_screen2_snapshot = final_review_result.get("reviewed_screen_2_payload")
                    else:
                        raise RuntimeError(
                            "Structured Agent completed without a valid screen_2_review_result artifact in its context."
                        )
                    with _run_lock:
                        _runs[run_id].update(
                            {
                                "status": "completed",
                                "final_output": final_text,
                                "screen_3_response": pending_screen3,
                                "review_result": final_review_result or review_result,
                                "completed_at": time.time(),
                                "progress": pending_progress,
                                "screen_2_snapshot": pending_screen2_snapshot,
                            }
                        )
                return

            chunk_type = getattr(chunk, "type", None)
            chunk_data = getattr(chunk, "data", {}) or {}
            text = getattr(chunk, "text", None) or ""

            if chunk_type != "content":
                stream_state = _extract_stream_state(chunk_data)
                if stream_state.get("review_request") is not None:
                    pending_review_request = stream_state["review_request"]
                if stream_state.get("progress") is not None:
                    pending_progress = stream_state["progress"]
                    with _run_lock:
                        if run_id in _runs:
                            _runs[run_id]["progress"] = pending_progress
                if stream_state.get("screen2_snapshot") is not None:
                    pending_screen2_snapshot = stream_state["screen2_snapshot"]
                    with _run_lock:
                        if run_id in _runs:
                            _runs[run_id]["screen_2_snapshot"] = pending_screen2_snapshot
                if stream_state.get("criterion_answers") is not None:
                    pending_criterion_answers = stream_state["criterion_answers"]
                    with _run_lock:
                        if run_id in _runs:
                            _runs[run_id]["edited_answers"] = pending_criterion_answers
                if stream_state.get("event"):
                    _append_run_event(run_id, stream_state["event"])
                else:
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
            "screen_2_snapshot": None,
            "screen_3_response": None,
            "edited_answers": {},
            "review_result": None,
            "error": None,
            "completed_at": None,
            "progress": {
                "current_block_id": None,
                "current_criterion_id": None,
                "current_criterion_prompt": None,
                "completed_criteria": 0,
                "total_criteria": None,
            },
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
