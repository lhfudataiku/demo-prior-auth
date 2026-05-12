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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.production.functions.logic_tree_evaluator import evaluate_logic_tree
from scripts.production.functions.selection_resolver import (
    _collect_criterion_ids_from_logic_root,
)


CaseConfig = Dict[str, Any]


CASES: Sequence[CaseConfig] = (
    {
        "name": "0059",
        "policy_master": "scripts/production/policy_artifacts/0059/policy_master_v4.json",
        "scoped": "scripts/production/policy_artifacts/0059/scoped_policy_context.json",
        "result_map": "scripts/production/policy_artifacts/0059/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
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
        "scoped": "scripts/production/policy_artifacts/0314/scoped_policy_context_SC_CLL.json",
        "result_map": "scripts/production/policy_artifacts/0314/criterion_result_map_ONC_HYCELA_CONT.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
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
        "scoped": "scripts/production/policy_artifacts/0655/scoped_policy_context.json",
        "result_map": "scripts/production/policy_artifacts/0655/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "criterion_counts": {
                "satisfied": 1,
                "not_satisfied": 0,
                "unresolved": 4,
            },
            "unresolved_criterion_ids": [
                "CR_NO_CONCOMITANT",
                "CR_TB_NEGATIVE",
                "CR_UC_CLINICAL_RESPONSE",
                "CR_UC_REMISSION",
            ],
        },
    },
    {
        "name": "0685_INIT_NSCLC",
        "policy_master": "scripts/production/policy_artifacts/0685/policy_master_v4.json",
        "scoped": "scripts/production/policy_artifacts/0685/scoped_policy_context_INIT_NSCLC.json",
        "result_map": "scripts/production/policy_artifacts/0685/criterion_result_map.json",
        "expected": {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
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


def _find_selected_cluster(
    policy_master: Dict[str, Any],
    cluster_id: str,
    route_id: str,
    phase: str,
) -> Optional[Dict[str, Any]]:
    for cluster in policy_master.get("condition_clusters", []):
        if (
            cluster.get("cluster_id") == cluster_id
            and cluster.get("route_id") == route_id
            and cluster.get("phase") == phase
        ):
            return cluster
    for cluster in policy_master.get("condition_clusters", []):
        if cluster.get("cluster_id") == cluster_id:
            return cluster
    return None


def _select_guard_roots(
    guards: Iterable[Dict[str, Any]],
    criterion_ids: Iterable[str],
    route_id: str,
    phase: str,
    cluster_id: Optional[str] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    wanted = set(criterion_ids or [])
    selected: List[Tuple[str, Dict[str, Any]]] = []

    for guard in guards:
        if route_id not in (guard.get("applies_to_route_ids") or []):
            continue

        phases = guard.get("applies_to_phases") or []
        if phase not in phases and "all" not in phases:
            continue

        if cluster_id is not None:
            clusters = guard.get("applies_to_cluster_ids") or []
            if clusters and cluster_id not in clusters:
                continue

        root = guard.get("logic_root")
        root_ids = _collect_criterion_ids_from_logic_root(root)
        if wanted and not (root_ids & wanted):
            continue

        if isinstance(root, dict):
            selected.append((str(guard.get("guard_id", "UNKNOWN")), root))

    return selected


def _select_logic_profiles(
    profiles: Iterable[Dict[str, Any]],
    profile_ids: Iterable[str],
) -> List[Tuple[str, Dict[str, Any]]]:
    wanted = set(profile_ids or [])
    selected: List[Tuple[str, Dict[str, Any]]] = []

    for profile in profiles:
        if profile.get("logic_profile_id") not in wanted:
            continue
        root = profile.get("logic_root")
        if isinstance(root, dict):
            selected.append((str(profile.get("logic_profile_id", "UNKNOWN")), root))

    return selected


def _evaluate_case(case: CaseConfig) -> Dict[str, Any]:
    policy_master = _load_json(case["policy_master"])
    scoped_payload = _load_json(case["scoped"])["scoped_policy_context"]
    result_map = _load_json(case["result_map"])

    route_id = scoped_payload["selected_route_id"]
    phase = scoped_payload["selected_phase"]
    cluster_id = scoped_payload["selected_cluster_id"]

    cluster = _find_selected_cluster(policy_master, cluster_id, route_id, phase)
    cluster_root = cluster.get("logic_root") if isinstance(cluster, dict) else None

    route_guards = _select_guard_roots(
        policy_master.get("route_guards", []),
        scoped_payload.get("selected_route_guard_criterion_ids", []),
        route_id,
        phase,
    )
    cluster_entry_guards = _select_guard_roots(
        policy_master.get("cluster_entry_guards", []),
        scoped_payload.get("selected_cluster_entry_guard_criterion_ids", []),
        route_id,
        phase,
        cluster_id,
    )
    logic_profiles = _select_logic_profiles(
        policy_master.get("logic_profiles", []),
        scoped_payload.get("selected_logic_profile_ids", []),
    )

    supporting_roots = [
        root for _, root in route_guards + cluster_entry_guards + logic_profiles
    ]
    evaluation = evaluate_logic_tree(cluster_root, result_map, supporting_roots)

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
