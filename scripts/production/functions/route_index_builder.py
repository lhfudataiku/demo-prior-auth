"""Deterministically derive route_index_v4 from policy_master_v4.

This keeps policy_master_v4 as the only canonical parser artifact while still
providing a compact Screen 1 routing view for the webapp.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _index_by_id(items: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        item_id = item.get(key)
        if isinstance(item_id, str) and item_id:
            out[item_id] = item
    return out


def _derive_ui_label(route: Dict[str, Any]) -> str:
    label = route.get("label")
    if isinstance(label, str) and label:
        return label
    route_id = route.get("route_id")
    if isinstance(route_id, str) and route_id:
        return route_id
    return "UNKNOWN"


def _build_cluster_summary(
    cluster_id: str,
    cluster_map: Dict[str, Dict[str, Any]],
    cluster_guard_map: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    cluster = cluster_map.get(cluster_id)
    if not isinstance(cluster, dict):
        return None

    cluster_entry_guard_ids = [
        guard_id
        for guard_id in cluster.get("cluster_entry_guard_ids", [])
        if isinstance(guard_id, str) and guard_id and guard_id in cluster_guard_map
    ]

    return {
        "cluster_id": cluster.get("cluster_id", "UNKNOWN"),
        "condition_key": cluster.get("condition_key", "UNKNOWN"),
        "condition_label": cluster.get("condition_label", "UNKNOWN"),
        "condition_synonyms": [
            synonym
            for synonym in cluster.get("condition_synonyms", [])
            if isinstance(synonym, str) and synonym
        ],
        "diagnosis_basis": cluster.get("diagnosis_basis", "UNKNOWN"),
        "diagnosis_code_candidates": [
            code
            for code in cluster.get("diagnosis_code_candidates", [])
            if isinstance(code, str) and code
        ],
        "cluster_entry_guard_ids": cluster_entry_guard_ids,
    }


def build_route_index_v4(policy_master_v4: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact routing view from canonical policy memory."""

    cluster_map = _index_by_id(policy_master_v4.get("condition_clusters", []), "cluster_id")
    cluster_guard_map = _index_by_id(policy_master_v4.get("cluster_entry_guards", []), "guard_id")

    routes: List[Dict[str, Any]] = []
    for route in policy_master_v4.get("request_routes", []):
        if not isinstance(route, dict):
            continue

        phases: List[Dict[str, Any]] = []
        for phase_branch in route.get("phase_branches", []):
            if not isinstance(phase_branch, dict):
                continue

            cluster_summaries: List[Dict[str, Any]] = []
            for cluster_id in phase_branch.get("cluster_ids", []):
                if not isinstance(cluster_id, str) or not cluster_id:
                    continue
                summary = _build_cluster_summary(cluster_id, cluster_map, cluster_guard_map)
                if summary is not None:
                    cluster_summaries.append(summary)

            phases.append(
                {
                    "phase": phase_branch.get("phase", "UNKNOWN"),
                    "is_default": bool(phase_branch.get("is_default", False)),
                    "route_guard_ids": [
                        guard_id
                        for guard_id in phase_branch.get("route_guard_ids", [])
                        if isinstance(guard_id, str) and guard_id
                    ],
                    "cluster_summaries": cluster_summaries,
                }
            )

        routes.append(
            {
                "route_id": route.get("route_id", "UNKNOWN"),
                "label": route.get("label", "UNKNOWN"),
                "coverage_status": route.get("coverage_status", "UNKNOWN"),
                "terminal_disposition": route.get("terminal_disposition", "continue"),
                "billing_codes": [
                    code for code in route.get("billing_codes", []) if isinstance(code, str) and code
                ],
                "phase_prompt_required": bool(route.get("phase_prompt_required", False)),
                "phases": phases,
                "ui_label": _derive_ui_label(route),
            }
        )

    return {
        "policy_id": policy_master_v4.get("policy_id", "UNKNOWN"),
        "routes": routes,
    }
