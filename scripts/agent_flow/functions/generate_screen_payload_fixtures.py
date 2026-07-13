"""Generate Screen 2 / Screen 3 fixture payloads from current policy artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_flow.functions.screen_payload_helpers import (  # noqa: E402
    build_criterion_ui_map_data,
    build_screen2_payload_data,
    build_screen3_payload_data,
    build_screen3_payload_from_review_result_data,
    normalize_review_result_data,
)

ARTIFACTS_DIR = ROOT / "scripts" / "artifacts" / "policy_artifacts"
FIXTURES_DIR = ROOT / "scripts" / "artifacts" / "fixtures" / "screen_payloads"
POLICY_IDS = ["0059", "0314", "0655", "0685"]


def _iter_nested_values(payload: Any) -> Iterable[Any]:
    if isinstance(payload, dict):
        for value in payload.values():
            yield value
            yield from _iter_nested_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield item
            yield from _iter_nested_values(item)


def _extract_state(artifact_payload: Dict[str, Any]) -> Dict[str, Any]:
    for value in _iter_nested_values(artifact_payload):
        if isinstance(value, dict) and "selected_scope_context" in value:
            return value
    raise ValueError("Could not find block-graph state in artifact payload")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_review_result_fixture(
    screen_2_payload: Dict[str, Any],
    criterion_answers: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "approval_status": "approved",
        "approved_criterion_answers": criterion_answers,
        "reviewed_screen_2_payload": screen_2_payload,
        "review_metadata": {
            "reviewer": None,
            "reviewed_at": None,
            "comment": None,
        },
        "human_validated": True,
    }


def _parse_review_result_from_artifact(artifact_payload: Dict[str, Any]) -> Dict[str, Any]:
    final_output = artifact_payload.get("final_output")
    if not isinstance(final_output, str) or not final_output.strip():
        return {}

    first_line = final_output.splitlines()[0].strip()
    if not first_line:
        return {}

    try:
        parsed = json.loads(first_line)
    except json.JSONDecodeError:
        return {}
    return normalize_review_result_data(parsed)


def _parse_review_result_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    raw_review_result = state.get("screen_2_review_result")
    if isinstance(raw_review_result, dict):
        return normalize_review_result_data(raw_review_result)
    if not isinstance(raw_review_result, str) or not raw_review_result.strip():
        return {}

    try:
        parsed = json.loads(raw_review_result)
    except json.JSONDecodeError:
        return {}
    return normalize_review_result_data(parsed)


def _resolve_artifact_path(policy_id: str, explicit_source: Optional[str]) -> Path:
    if explicit_source:
        source_path = Path(explicit_source)
        if not source_path.is_absolute():
            source_path = ROOT / source_path
        return source_path

    for candidate_name in ("structured_agent_context.json", "test.json"):
        candidate_path = ARTIFACTS_DIR / policy_id / candidate_name
        if candidate_path.exists():
            return candidate_path

    raise FileNotFoundError(f"No artifact source found for policy {policy_id}")


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy-id",
        action="append",
        dest="policy_ids",
        help="Policy ID to regenerate. May be supplied multiple times.",
    )
    parser.add_argument(
        "--source",
        help="Optional source artifact path. Requires exactly one --policy-id.",
    )
    return parser


def main() -> None:
    args = _build_argument_parser().parse_args()
    policy_ids = args.policy_ids or POLICY_IDS

    if args.source and len(policy_ids) != 1:
        raise ValueError("--source requires exactly one --policy-id")

    for policy_id in policy_ids:
        artifact_path = _resolve_artifact_path(policy_id, args.source)
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        state = _extract_state(artifact_payload)

        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=state.get("selected_scope_context"),
            criterion_result_map=state.get("criterion_result_map", {}),
            criterion_answers=state.get("criterion_answers", {}),
            retrieval_plan=state.get("retrieval_plan_v1"),
        )
        state_with_ui = dict(state)
        state_with_ui["criterion_ui_map"] = criterion_ui_map

        fixture_dir = FIXTURES_DIR / policy_id
        _write_json(fixture_dir / "structured_agent_context.json", artifact_payload)
        _write_json(
            fixture_dir / "selected_scope_context.json",
            state.get("selected_scope_context", {}) or {},
        )
        _write_json(
            fixture_dir / "criterion_result_map.json",
            state.get("criterion_result_map", {}) or {},
        )
        _write_json(fixture_dir / "criterion_ui_map.json", criterion_ui_map)

        screen_2_payload = build_screen2_payload_data(state_with_ui)
        _write_json(fixture_dir / "screen_2_response.json", screen_2_payload)

        review_result = _parse_review_result_from_state(state)
        if not review_result:
            review_result = _parse_review_result_from_artifact(artifact_payload)
        if not review_result:
            review_result = _build_review_result_fixture(
                screen_2_payload=screen_2_payload,
                criterion_answers=state.get("criterion_answers", {}) or {},
            )
        _write_json(fixture_dir / "screen_2_review_result.json", review_result)

        screen_3_payload = (
            build_screen3_payload_from_review_result_data(review_result)
            if review_result
            else build_screen3_payload_data(state_with_ui)
        )
        _write_json(fixture_dir / "screen_3_response.json", screen_3_payload)


if __name__ == "__main__":
    main()
