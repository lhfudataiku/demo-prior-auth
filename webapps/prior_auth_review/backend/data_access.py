import json
import os
from csv import DictReader
from pathlib import Path
from typing import Optional

try:
    import dataiku  # type: ignore
except ImportError:  # pragma: no cover
    dataiku = None


REPO_ROOT = Path(__file__).resolve().parents[3]
PATIENT_FIXTURE_PATH = REPO_ROOT / "scripts" / "artifacts" / "fixtures" / "Patient.csv"
POLICY_ARTIFACT_ROOT = REPO_ROOT / "scripts" / "artifacts" / "policy_artifacts"
POLICY_ARTIFACTS_CSV_PATH = POLICY_ARTIFACT_ROOT / "policy_artifacts.csv"
SCREEN_PAYLOAD_FIXTURE_ROOT = REPO_ROOT / "scripts" / "artifacts" / "fixtures" / "screen_payloads"
STRUCTURED_AGENT_ID = "NkBiV9OM"
STRUCTURED_AGENT_VERSION = "v2"
PATIENT_DATASET_NAME = "Patient"
POLICY_ARTIFACTS_DATASET_NAME = "policy_artifacts"
DATA_SOURCE = "local"
VALID_DATA_SOURCES = {"local", "dss"}


def get_data_source(source: Optional[str] = None) -> str:
    raw_source = source if source is not None else DATA_SOURCE
    resolved_source = raw_source.strip().lower()
    if resolved_source not in VALID_DATA_SOURCES:
        raise ValueError(
            f"Unsupported data source value: {raw_source!r}. Expected 'local' or 'dss'."
        )
    return resolved_source


def _require_dataiku():
    if dataiku is None:
        raise RuntimeError("Dataiku Python package is required when data source is 'dss'.")
    return dataiku


def _load_dataset_rows(dataset_name: str, columns: Optional[list[str]] = None):
    dku = _require_dataiku()
    dataset = dku.Dataset(dataset_name)
    dataframe = dataset.get_dataframe(infer_with_pandas=False)
    if columns:
        available = [column for column in columns if column in dataframe.columns]
        if available:
            dataframe = dataframe[available]
    return dataframe.to_dict(orient="records")


def _load_json(policy_id: str, filename: str):
    path = POLICY_ARTIFACT_ROOT / policy_id / filename
    with path.open() as stream:
        return json.load(stream)


def _parse_json_object_from_text(text: str):
    decoder = json.JSONDecoder()
    stripped = text.lstrip()
    if not stripped:
        raise ValueError("Structured agent returned empty text.")

    for start_char in ("{", "["):
        start_index = stripped.find(start_char)
        if start_index == -1:
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[start_index:])
            return payload
        except json.JSONDecodeError:
            continue

    raise ValueError("Structured agent response did not contain a valid JSON payload.")


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


def _build_screen2_agent_request(
    policy_id: str,
    subject_id: Optional[str],
    selected_scope_context: dict,
    criterion_answers: Optional[dict] = None,
):
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
            "policy_master_v4": load_policy_master(policy_id),
            "retrieval_plan_v1": None,
            "criterion_answers": criterion_answers or {},
        },
    }


def _load_policy_catalog_local():
    items = {}
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


def _load_policy_catalog_dss():
    items = {}
    rows = _load_dataset_rows(
        POLICY_ARTIFACTS_DATASET_NAME,
        columns=["policy_id", "document_type", "policy_master_v4"],
    )
    for row in rows:
        policy_id = row.get("policy_id")
        if not policy_id:
            continue
        if not isinstance(policy_id, str):
            policy_id = str(policy_id)
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


def load_policy_catalog(data_source: Optional[str] = None):
    if get_data_source(data_source) == "dss":
        return _load_policy_catalog_dss()
    return _load_policy_catalog_local()


def _load_policy_row_dss(policy_id: str):
    rows = _load_dataset_rows(
        POLICY_ARTIFACTS_DATASET_NAME,
        columns=["policy_id", "policy_master_v4", "route_index_v4"],
    )
    for row in rows:
        value = row.get("policy_id")
        if value is not None and str(value) == policy_id:
            return row
    raise FileNotFoundError(f"Policy {policy_id} not found in DSS dataset {POLICY_ARTIFACTS_DATASET_NAME}.")


def _load_policy_row_local(policy_id: str):
    with POLICY_ARTIFACTS_CSV_PATH.open() as stream:
        for row in DictReader(stream):
            if row.get("policy_id") == policy_id:
                return row
    raise FileNotFoundError(f"Policy {policy_id} not found in local {POLICY_ARTIFACTS_CSV_PATH}.")


def load_policy_master(policy_id: str, data_source: Optional[str] = None):
    if get_data_source(data_source) == "dss":
        row = _load_policy_row_dss(policy_id)
        return json.loads(row.get("policy_master_v4") or "{}")
    try:
        row = _load_policy_row_local(policy_id)
        return json.loads(row.get("policy_master_v4") or "{}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _load_json(policy_id, "policy_master_v4.json")


def load_route_index(policy_id: str, data_source: Optional[str] = None):
    if get_data_source(data_source) == "dss":
        row = _load_policy_row_dss(policy_id)
        return json.loads(row.get("route_index_v4") or "{}")
    try:
        row = _load_policy_row_local(policy_id)
        return json.loads(row.get("route_index_v4") or "{}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _load_json(policy_id, "route_index_v4.json")


def _load_screen2_response_local(policy_id: str, _subject_id: Optional[str] = None):
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


def _load_screen2_response_dss(
    policy_id: str,
    subject_id: Optional[str] = None,
    selected_scope_context: Optional[dict] = None,
    criterion_answers: Optional[dict] = None,
):
    dku = _require_dataiku()
    if not isinstance(selected_scope_context, dict) or not selected_scope_context:
        raise ValueError("selected_scope_context is required when loading Screen 2 in dss mode.")
    agent_request = _build_screen2_agent_request(policy_id, subject_id, selected_scope_context)
    agent_request["payload"]["criterion_answers"] = criterion_answers or {}
    client = dku.api_client()
    project = client.get_default_project()
    llm = project.get_llm(f"agent:{STRUCTURED_AGENT_ID}")
    completion = llm.new_completion()
    response = completion.with_message(json.dumps(agent_request), role="user").execute()
    if not getattr(response, "success", True):
        raise RuntimeError(f"Structured agent call failed for {policy_id}.")
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError(f"Structured agent returned an empty response for {policy_id}.")
    payload = _parse_json_object_from_text(text)
    if isinstance(payload, dict) and "payload" in payload:
        return payload
    raise RuntimeError(f"Unexpected structured agent response shape for {policy_id}.")


def load_screen2_response(
    policy_id: str,
    subject_id: Optional[str] = None,
    selected_scope_context: Optional[dict] = None,
    criterion_answers: Optional[dict] = None,
    data_source: Optional[str] = None,
):
    if get_data_source(data_source) == "dss":
        return _load_screen2_response_dss(
            policy_id,
            subject_id,
            selected_scope_context=selected_scope_context,
            criterion_answers=criterion_answers,
        )
    return _load_screen2_response_local(policy_id, subject_id)


def _load_patient_rows_local():
    with PATIENT_FIXTURE_PATH.open() as stream:
        return list(DictReader(stream))


def _load_patient_rows_dss(columns: Optional[list[str]] = None):
    return _load_dataset_rows(PATIENT_DATASET_NAME, columns=columns)


def load_patient_summary(subject_id: str, data_source: Optional[str] = None):
    if get_data_source(data_source) == "dss":
        rows = _load_patient_rows_dss(columns=["subject_id", "gender", "birth_date"])
    else:
        rows = _load_patient_rows_local()

    for row in rows:
        if row.get("subject_id") == subject_id:
            return {
                "subject_id": subject_id,
                "gender": row.get("gender"),
                "birth_date": row.get("birth_date"),
            }
    return {
        "subject_id": subject_id,
        "gender": None,
        "birth_date": None,
    }


def load_patient_id_options(data_source: Optional[str] = None):
    if get_data_source(data_source) == "dss":
        rows = _load_patient_rows_dss(columns=["subject_id"])
    else:
        rows = _load_patient_rows_local()

    subject_ids = []
    for row in rows:
        subject_id = row.get("subject_id")
        if subject_id:
            subject_ids.append(subject_id)
    return sorted(set(subject_ids))


def default_billing_code(policy_id: str, data_source: Optional[str] = None):
    route_index = load_route_index(policy_id, data_source=data_source)
    for route in route_index.get("routes", []):
        if not isinstance(route, dict):
            continue
        for code in route.get("billing_codes", []):
            if isinstance(code, str) and code:
                return code
    return None
