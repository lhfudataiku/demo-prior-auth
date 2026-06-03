"""Generate Screen 2 / Screen 3 fixture payloads from current policy artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_flow.functions.screen_payload_helpers import (  # noqa: E402
    build_criterion_ui_map_data,
    build_screen2_payload_data,
    build_screen3_payload_data,
)

ARTIFACTS_DIR = ROOT / "scripts" / "artifacts" / "policy_artifacts"
FIXTURES_DIR = ROOT / "scripts" / "artifacts" / "fixtures" / "screen_payloads"
POLICY_IDS = ["0059", "0314", "0655", "0685"]


def _extract_state(artifact_payload: Dict[str, Any]) -> Dict[str, Any]:
    context = artifact_payload.get("context", {})
    if not isinstance(context, dict):
        raise ValueError("structured_agent_context missing top-level context object")

    for value in context.values():
        if isinstance(value, dict) and "selected_scope_context" in value:
            return value

    raise ValueError("Could not find block-graph state in structured_agent_context")


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


def main() -> None:
    for policy_id in POLICY_IDS:
        artifact_path = ARTIFACTS_DIR / policy_id / "structured_agent_context.json"
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        state = _extract_state(artifact_payload)

        criterion_ui_map = build_criterion_ui_map_data(
            selected_scope_context=state.get("selected_scope_context"),
            criterion_result_map=state.get("criterion_result_map", {}),
            criterion_answers=state.get("criterion_answers", {}),
        )
        state_with_ui = dict(state)
        state_with_ui["criterion_ui_map"] = criterion_ui_map

        fixture_dir = FIXTURES_DIR / policy_id
        _write_json(fixture_dir / "criterion_ui_map.json", criterion_ui_map)
        screen_2_payload = build_screen2_payload_data(state_with_ui)
        _write_json(fixture_dir / "screen_2_response.json", screen_2_payload)
        _write_json(
            fixture_dir / "screen_2_review_result.json",
            _build_review_result_fixture(
                screen_2_payload=screen_2_payload,
                criterion_answers=state.get("criterion_answers", {}) or {},
            ),
        )
        _write_json(
            fixture_dir / "screen_3_response.json",
            build_screen3_payload_data(state_with_ui),
        )


if __name__ == "__main__":
    main()
