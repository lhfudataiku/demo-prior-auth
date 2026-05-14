"""Regression runner for the prior-auth logic tree evaluator.

This script replays saved `criterion_result_map` artifacts against the selected
cluster logic reconstructed from policy artifacts. It provides a lightweight
sanity check whenever the reasoning-result contract or evaluator semantics
change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.production.functions.logic_tree_evaluator import evaluate_logic_tree
from scripts.production.functions.selection_resolver import resolve_selection_scope


CaseConfig = Dict[str, Any]


CASES: Sequence[CaseConfig] = (
    {
        "name": "0059",
        "policy_master": "scripts/production/policy_artifacts/0059/policy_master_v4.json",
        "route_index": "scripts/production/policy_artifacts/0059/route_index_v4.json",
        "scoped": "scripts/production/policy_artifacts/0059/scoped_policy_context.json",
        "result_map": "scripts/production/policy_artifacts/0059/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": ["CR_CLUSTER_OBSTRUCTIVE_DIAG"],
            "not_satisfied_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 1,
                "not_satisfied": 0,
                "unresolved": 1,
            },
            "unresolved_criterion_ids": ["CR_ROUTE_NOT_DIAGNOSE_COPD"],
        },
    },
    {
        "name": "0314_CONT_HYCELA",
        "policy_master": "scripts/production/policy_artifacts/0314/policy_master_v4.json",
        "route_index": "scripts/production/policy_artifacts/0314/route_index_v4.json",
        "scoped": "scripts/production/policy_artifacts/0314/scoped_policy_context_SC_CLL.json",
        "result_map": "scripts/production/policy_artifacts/0314/criterion_result_map_ONC_HYCELA_CONT.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": ["CR_DIAG_ONCOLOGY"],
            "not_satisfied_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 1,
                "not_satisfied": 0,
                "unresolved": 2,
            },
            "unresolved_criterion_ids": [
                "CR_CD20_TEST_POSITIVE",
                "CR_ONC_CONT_NO_UNACCEPTABLE_TOX",
            ],
        },
    },
    {
        "name": "0655",
        "policy_master": "scripts/production/policy_artifacts/0655/policy_master_v4.json",
        "route_index": "scripts/production/policy_artifacts/0655/route_index_v4.json",
        "scoped": "scripts/production/policy_artifacts/0655/scoped_policy_context.json",
        "result_map": "scripts/production/policy_artifacts/0655/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": ["CR_UC_DIAGNOSIS"],
            "not_satisfied_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 1,
                "not_satisfied": 0,
                "unresolved": 5,
            },
            "unresolved_criterion_ids": [
                "CR_NO_CONCOMITANT",
                "CR_TB_NEGATIVE",
                "CR_UC_CLINICAL_RESPONSE",
                "CR_UC_MOD_SEV",
                "CR_UC_REMISSION",
            ],
        },
    },
    {
        "name": "0685_INIT_NSCLC",
        "policy_master": "scripts/production/policy_artifacts/0685/policy_master_v4.json",
        "route_index": "scripts/production/policy_artifacts/0685/route_index_v4.json",
        "scoped": "scripts/production/policy_artifacts/0685/scoped_policy_context_INIT_NSCLC.json",
        "result_map": "scripts/production/policy_artifacts/0685/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": ["CR_0685_DIAG_NSCLC"],
            "not_satisfied_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 1,
                "not_satisfied": 0,
                "unresolved": 2,
            },
            "unresolved_criterion_ids": [
                "CR_0685_GUARD_NSCLC_NO_PEM_MAINT",
                "CR_0685_RG_NO_CETUX",
            ],
        },
    },
)


def _load_json(relative_path: str) -> Dict[str, Any]:
    return json.loads((REPO_ROOT / relative_path).read_text())


def _rehydrate_scoped_policy_context(case: CaseConfig, scoped_payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(scoped_payload.get("selected_cluster"), dict):
        return scoped_payload

    route_index = _load_json(case["route_index"])
    policy_master = _load_json(case["policy_master"])
    selected_route_id = scoped_payload["selected_route_id"]

    billing_code = None
    for route in route_index.get("routes", []):
        if route.get("route_id") == selected_route_id:
            billing_codes = route.get("billing_codes", [])
            if billing_codes:
                billing_code = billing_codes[0]
            break

    if not billing_code:
        raise ValueError(f"Could not rehydrate scoped policy context for {case['name']}: missing billing code")

    resolved = resolve_selection_scope(
        route_index_v4=route_index,
        policy_master_v4=policy_master,
        billing_code=billing_code,
        selected_phase=scoped_payload["selected_phase"],
        selected_cluster_id=scoped_payload["selected_cluster_id"],
    )
    if resolved.get("status") != "ok" or "scoped_policy_context" not in resolved:
        raise ValueError(f"Could not rehydrate scoped policy context for {case['name']}: {resolved}")

    return resolved["scoped_policy_context"]


def _evaluate_case(case: CaseConfig) -> Dict[str, Any]:
    scoped_payload = _rehydrate_scoped_policy_context(
        case,
        _load_json(case["scoped"])["scoped_policy_context"],
    )
    result_map = _load_json(case["result_map"])

    evaluation = evaluate_logic_tree(scoped_payload, result_map)

    return {
        "name": case["name"],
        "evaluation": evaluation,
        "expected": case["expected"],
        "passed": evaluation == case["expected"],
    }


def main() -> int:
    results = [_evaluate_case(case) for case in CASES]

    failures = [result for result in results if not result["passed"]]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['name']}")
        print(json.dumps(result["evaluation"], indent=2, sort_keys=True))
        if not result["passed"]:
            print("Expected:")
            print(json.dumps(result["expected"], indent=2, sort_keys=True))
        print()

    if failures:
        print(f"{len(failures)} regression case(s) failed.")
        return 1

    print(f"All {len(results)} regression case(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
