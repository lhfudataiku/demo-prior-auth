"""Managed custom Python tool for Screen 2 human review.

This tool is intentionally small. DSS owns the human approval checkpoint; the
tool only receives the approved or edited payload and returns it in a stable
shape for the Structured Agent to merge deterministically.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Dict

import dataiku  # noqa: F401  # Imported so DSS packages the tool with Dataiku runtime.
from dataiku.llm.agent_tools import BaseAgentTool

logger = logging.getLogger(__name__)


ANSWER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "value": {
            "oneOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "null"},
            ]
        },
        "comment": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "override_prefill": {"type": "boolean"},
    },
    "required": ["answer"],
    "additionalProperties": True,
}


class Screen2HumanReviewTool(BaseAgentTool):
    """Submit the Screen 2 payload for human approval and optional edits."""

    def set_config(self, config: Dict[str, Any], plugin_config: Dict[str, Any]) -> None:
        self.config = config
        self.plugin_config = plugin_config

    def get_descriptor(self, tool: Any) -> Dict[str, Any]:
        review_request_schema = {
            "type": "object",
            "properties": {
                "session_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "subject_id": {"type": "string"},
                "policy_id": {"type": "string"},
                "selected_scope": {
                    "type": "object",
                    "properties": {
                        "selected_route_id": {"type": "string"},
                        "selected_phase": {
                            "type": "string",
                            "enum": ["initial", "continuation", "other"],
                        },
                        "selected_cluster_id": {"type": "string"},
                    },
                    "required": [
                        "selected_route_id",
                        "selected_phase",
                        "selected_cluster_id",
                    ],
                    "additionalProperties": True,
                },
                "screen_2_payload": {
                    "type": "object",
                    "description": "Review payload built by build_screen2_payload(...).",
                    "additionalProperties": True,
                },
                "criterion_answers": {
                    "type": "object",
                    "additionalProperties": ANSWER_SCHEMA,
                },
                "review_metadata": {
                    "type": "object",
                    "properties": {
                            "reviewer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                            "reviewed_at": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                            "comment": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        },
                    "additionalProperties": True,
                },
            },
            "required": [
                "subject_id",
                "policy_id",
                "selected_scope",
                "screen_2_payload",
                "criterion_answers",
            ],
            "additionalProperties": True,
        }
        return {
            "description": (
                "Submit the prior-authorization Screen 2 eligibility review "
                "payload for human approval. The reviewer can edit criterion "
                "answers before approving when editable tool inputs are enabled."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "review_request": review_request_schema,
                },
                "required": ["review_request"],
                "additionalProperties": True,
            },
        }

    def invoke(self, input: Dict[str, Any], trace: Any) -> Dict[str, Any]:
        raw_input = input.get("input", {})
        if not isinstance(raw_input, dict):
            raw_input = {}

        user_input = _extract_review_request(raw_input)
        _validate_review_request(user_input)

        screen_2_payload = deepcopy(user_input.get("screen_2_payload", {}))
        criterion_answers = deepcopy(user_input.get("criterion_answers", {}))
        if not isinstance(criterion_answers, dict):
            criterion_answers = {}

        original_answers = _extract_payload_answers(screen_2_payload)
        approval_status = user_input.get("approval_status")
        if approval_status not in {"approved", "edited", "rejected"}:
            approval_status = "edited" if _answers_changed(original_answers, criterion_answers) else "approved"

        review_metadata = user_input.get("review_metadata", {})
        if not isinstance(review_metadata, dict):
            review_metadata = {}

        output = {
            "approval_status": approval_status,
            "approved_criterion_answers": criterion_answers,
            "reviewed_screen_2_payload": screen_2_payload,
            "review_metadata": {
                "reviewer": review_metadata.get("reviewer"),
                "reviewed_at": review_metadata.get("reviewed_at"),
                "comment": review_metadata.get("comment"),
            },
            "human_validated": approval_status in {"approved", "edited"},
        }

        if trace:
            trace.attributes["tool_version"] = "1.0"
            trace.attributes["session_id"] = user_input.get("session_id")
            trace.attributes["policy_id"] = user_input.get("policy_id")
            trace.attributes["approval_status"] = approval_status
            trace.attributes["approved_answer_count"] = len(criterion_answers)
        logger.info(
            "Screen 2 human review approved for session=%s policy=%s status=%s answers=%s",
            user_input.get("session_id"),
            user_input.get("policy_id"),
            approval_status,
            len(criterion_answers),
        )

        return {
            "output": output,
            "sources": [],
        }


def _extract_review_request(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    wrapped = raw_input.get("review_request")
    if isinstance(wrapped, dict):
        return wrapped
    if isinstance(raw_input, dict):
        return raw_input
    return {}


def _validate_review_request(user_input: Dict[str, Any]) -> None:
    if not isinstance(user_input, dict):
        raise ValueError("review_request must be an object")

    required_top_level = [
        "subject_id",
        "policy_id",
        "selected_scope",
        "screen_2_payload",
        "criterion_answers",
    ]
    missing_top_level = [
        key for key in required_top_level if key not in user_input
    ]
    if missing_top_level:
        raise ValueError(
            "review_request is missing required fields: "
            + ", ".join(sorted(missing_top_level))
        )

    selected_scope = user_input.get("selected_scope")
    if not isinstance(selected_scope, dict):
        raise ValueError("review_request.selected_scope must be an object")

    required_scope_fields = [
        "selected_route_id",
        "selected_phase",
        "selected_cluster_id",
    ]
    missing_scope_fields = [
        key for key in required_scope_fields if key not in selected_scope
    ]
    if missing_scope_fields:
        raise ValueError(
            "review_request.selected_scope is missing required fields: "
            + ", ".join(sorted(missing_scope_fields))
        )


def _extract_payload_answers(screen_2_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = screen_2_payload.get("payload", {}) if isinstance(screen_2_payload, dict) else {}
    criteria = payload.get("criteria", []) if isinstance(payload, dict) else []
    answers: Dict[str, Any] = {}

    if not isinstance(criteria, list):
        return answers

    for row in criteria:
        if not isinstance(row, dict):
            continue
        criterion_id = row.get("criterion_id")
        clinician_input = row.get("clinician_input", {})
        if not criterion_id or not isinstance(clinician_input, dict):
            continue
        if clinician_input.get("answered"):
            answers[str(criterion_id)] = {
                "answer": clinician_input.get("answer"),
                "value": clinician_input.get("value"),
                "comment": clinician_input.get("comment"),
                "override_prefill": bool(clinician_input.get("override_prefill", False)),
            }

    return answers


def _answers_changed(original_answers: Dict[str, Any], approved_answers: Dict[str, Any]) -> bool:
    return _normalize_answers(original_answers) != _normalize_answers(approved_answers)


def _normalize_answers(raw_answers: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for criterion_id, answer in raw_answers.items():
        if not isinstance(answer, dict):
            continue
        normalized[str(criterion_id)] = {
            "answer": answer.get("answer"),
            "value": answer.get("value"),
            "comment": answer.get("comment"),
            "override_prefill": bool(answer.get("override_prefill", False)),
        }
    return normalized
