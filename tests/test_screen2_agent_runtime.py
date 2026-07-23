"""Regression coverage for explicit-runtime Screen 2 block functions."""

from __future__ import annotations

import unittest

from scripts.agent_flow.functions.screen2_agent_runtime import (
    accumulate_current_reasoning_result,
    build_screen2_payload_from_state,
    prepare_screen2_review_payload,
)
from scripts.agent_flow.functions.screen2_summary_helpers import (
    build_agent_review_summary,
    get_agent_review_summary_metadata,
)


class _Span:
    def __init__(self) -> None:
        self.attributes = {}
        self.outputs = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Trace:
    def subspan(self, _name):
        return _Span()


def _scope() -> dict:
    return {
        "selected_route_id": "ROUTE_TEST",
        "selected_phase": "other",
        "selected_cluster_id": "CL_TEST",
        "selected_route": {"label": "Test route"},
        "selected_cluster": {
            "label": "Test cluster",
            "logic_root": {
                "node_type": "criterion_ref",
                "criterion_id": "CR_TEST",
            },
        },
        "selected_criteria_catalog": [
            {
                "criterion_id": "CR_TEST",
                "criterion_kind": "cluster_criterion",
                "prompt": "Is the test criterion documented?",
                "answer_type": "boolean",
                "required": True,
            }
        ],
        "selected_cluster_criterion_ids": ["CR_TEST"],
    }


class Screen2AgentRuntimeTests(unittest.TestCase):
    def test_accumulation_preserves_an_immutable_plan_trace(self) -> None:
        plan_item = {
            "criterion_id": "CR_TEST",
            "execution_hints": {"qualifiers": []},
        }
        state = {"selected_scope_context": _scope()}
        scratchpad = {
            "current_plan_item": plan_item,
            "current_reasoning_result": (
                '{"criterion_id":"CR_TEST","status":"Missing",'
                '"meets_criterion":false,"sources":{"structured":[],"notes":[]}}'
            ),
        }

        accumulate_current_reasoning_result(state, scratchpad, _Trace())

        plan_item["execution_hints"]["qualifiers"].append("disease_stage")
        trace = state["criterion_trace_map"]["CR_TEST"]
        self.assertEqual([], trace["plan_item"]["execution_hints"]["qualifiers"])
        self.assertEqual("Missing", state["criterion_result_map"]["CR_TEST"]["status"])
        self.assertEqual({}, scratchpad["current_reasoning_result"])

    def test_prepare_payload_builds_a_missing_ui_map_with_retrieval_plan(self) -> None:
        state = {
            "session_id": "session-test",
            "subject_id": "subject-test",
            "policy_id": "policy-test",
            "selected_scope_context": _scope(),
            "criterion_answers": {},
            "criterion_result_map": {
                "CR_TEST": {
                    "criterion_id": "CR_TEST",
                    "status": "Found",
                    "meets_criterion": True,
                    "sources": {"structured": [], "notes": []},
                }
            },
            "retrieval_plan_v1": {
                "plan_items": [
                    {
                        "criterion_id": "CR_TEST",
                        "execution_hints": {
                            "criterion_archetype": "ARC_note_only",
                            "retrieval_strategy": "note_first",
                        },
                    }
                ]
            },
        }

        payload = build_screen2_payload_from_state(state, _Trace())
        prepare_screen2_review_payload(state, _Trace())

        self.assertEqual("satisfied", payload["payload"]["logic_evaluation"]["selected_cluster_status"])
        self.assertEqual(
            "ARC_note_only",
            state["criterion_ui_map"]["CR_TEST"]["planner_context"]["criterion_archetype"],
        )
        self.assertIn("screen_2_payload", state["screen_2_review_tool_input"])

    def test_summary_handles_sources_and_invalid_result_data(self) -> None:
        summary = build_agent_review_summary(
            {
                "reviewed_screen_2_payload": {
                    "status": "warning",
                    "payload": {
                        "selected_scope_display": {"route_label": "Test route"},
                        "logic_evaluation": {"selected_cluster_status": "unresolved"},
                        "criteria": [
                            {
                                "criterion_id": "CR_TEST",
                                "chart_result": {
                                    "status": "Missing",
                                    "meets_criterion": False,
                                    "sources": {"notes": [{"excerpt": "No direct evidence."}]},
                                },
                            }
                        ],
                    },
                }
            }
        )

        self.assertIn("# Prior Authorization Eligibility Review", summary)
        self.assertIn("No direct evidence.", summary)
        self.assertIn("Policy: Unknown", build_agent_review_summary("not-json"))
        self.assertEqual(
            {"summary_version": "agent_review_summary_v1", "criterion_count": 0, "human_validated": False},
            get_agent_review_summary_metadata("not-json"),
        )


if __name__ == "__main__":
    unittest.main()
