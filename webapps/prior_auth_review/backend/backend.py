from flask import Blueprint, Flask, jsonify, request

from scripts.agent_flow.functions.selection_resolver import build_screen1_payload
from webapps.prior_auth_review.backend.data_access import (
    default_billing_code,
    load_patient_id_options,
    load_patient_summary,
    load_policy_catalog,
    load_policy_master,
    load_route_index,
    load_screen2_response,
    load_selected_scope_context,
)
from webapps.prior_auth_review.backend.utils import (
    calculate_age,
    ensure_selected_scope_display,
    enrich_screen3_payload,
    merge_answers,
    resolve_selected_scope_display,
)


api = Blueprint("prior_auth_review_api", __name__, url_prefix="/api")


def _catalog_item(policy_id: str):
    return load_policy_catalog().get(policy_id)


def _with_patient_age(patient_summary):
    if not patient_summary:
        return None
    summary = dict(patient_summary)
    summary["age"] = calculate_age(summary.get("birth_date"))
    return summary


def _maybe_selected_scope_context(policy_id: str):
    try:
        return load_selected_scope_context(policy_id)
    except FileNotFoundError:
        return None


@api.route("/scenarios", methods=["GET"])
def list_scenarios():
    catalog = load_policy_catalog()
    items = [catalog[policy_id] for policy_id in sorted(catalog)]
    return jsonify({"items": items})


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


@api.route("/scenarios/<policy_id>/bootstrap", methods=["GET"])
def get_bootstrap(policy_id: str):
    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    subject_id = request.args.get("subject_id")
    patient_summary = _with_patient_age(load_patient_summary(subject_id)) if subject_id else None
    raw_screen_2_response = load_screen2_response(policy_id, subject_id)
    scope_display = resolve_selected_scope_display(
        selected_scope_context=_maybe_selected_scope_context(policy_id),
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


@api.route("/scenarios/<policy_id>/review", methods=["POST"])
def submit_review(policy_id: str):
    scenario = _catalog_item(policy_id)
    if scenario is None:
        return jsonify({"error": f"Unknown policy_id: {policy_id}"}), 404

    body = request.get_json(force=True) or {}
    screen_2_response = load_screen2_response(policy_id, body.get("subject_id"))
    scope_display = resolve_selected_scope_display(
        selected_scope_context=_maybe_selected_scope_context(policy_id),
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
