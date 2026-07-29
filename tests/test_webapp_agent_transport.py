"""Regression coverage for the DSS Structured Agent completion boundary."""

from __future__ import annotations

import json
import unittest

from webapps.prior_auth_review.backend.agent_transport import (
    extract_graph_state,
    extract_review_result_from_graph,
)


def _review_result() -> dict:
    return {
        "approval_status": "approved",
        "approved_criterion_answers": {},
        "reviewed_screen_2_payload": {
            "status": "warning",
            "payload": {"criteria": [], "logic_evaluation": {}},
        },
        "human_validated": True,
    }


class WebappAgentTransportTests(unittest.TestCase):
    def test_extracts_review_artifact_from_context_upsert(self) -> None:
        expected = _review_result()
        context_upsert = {
            "_blocksGraphState_DEMO_PRIOR_AUTH_AGENT-NkBiV9OM-v2": {
                "_currentBlockId": "generate_text_output",
                "screen_2_review_result": json.dumps(expected),
                "agent_review_summary": "# Prior Authorization Eligibility Review",
            }
        }

        graph_state = extract_graph_state(context_upsert)
        result = extract_review_result_from_graph(graph_state)

        self.assertIsNotNone(graph_state)
        self.assertIsNotNone(result)
        self.assertEqual("approved", result["approval_status"])
        self.assertTrue(result["human_validated"])
        self.assertIn("reviewed_screen_2_payload", result)

    def test_extracts_review_artifact_from_nested_context_upsert(self) -> None:
        expected = _review_result()
        context_upsert = {
            "context": {
                "_blocksGraphState_DEMO_PRIOR_AUTH_AGENT-NkBiV9OM-v2": {
                    "_currentBlockId": "generate_text_output",
                    "screen_2_review_result": expected,
                }
            }
        }

        graph_state = extract_graph_state(context_upsert)
        result = extract_review_result_from_graph(graph_state)

        self.assertIsNotNone(graph_state)
        self.assertIsNotNone(result)
        self.assertEqual("approved", result["approval_status"])
        self.assertTrue(result["human_validated"])
        self.assertIn("reviewed_screen_2_payload", result)

    def test_markdown_terminal_text_is_not_a_transport_payload(self) -> None:
        graph_state = {
            "_currentBlockId": "generate_text_output",
            "agent_review_summary": "# Prior Authorization Eligibility Review",
        }

        self.assertIsNone(extract_review_result_from_graph(graph_state))


if __name__ == "__main__":
    unittest.main()
