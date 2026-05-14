"""Deterministic Selection Resolver for prior-auth Screen 1 scope reduction."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, Iterable, List, Optional, Set, Union


def _index_by_id(items: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        item_id = item.get(key)
        if isinstance(item_id, str) and item_id:
            out[item_id] = item
    return out


def _collect_criterion_ids_from_logic_root(logic_root: Optional[Dict[str, Any]]) -> Set[str]:
    criterion_ids: Set[str] = set()
    if not isinstance(logic_root, dict):
        return criterion_ids

    node_type = logic_root.get("node_type")
    if node_type == "criterion_ref":
        criterion_id = logic_root.get("criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            criterion_ids.add(criterion_id)
        return criterion_ids

    for child in logic_root.get("children", []):
        if isinstance(child, dict):
            criterion_ids.update(_collect_criterion_ids_from_logic_root(child))
    return criterion_ids


def _effective_diagnosis_code_candidates(
    selected_cluster: Dict[str, Any],
    selected_cluster_summary: Optional[Dict[str, Any]],
    inherited_clusters: List[Dict[str, Any]],
) -> List[str]:
    ordered_codes: List[str] = []
    seen: Set[str] = set()

    for source in [selected_cluster_summary, selected_cluster, *inherited_clusters]:
        if not isinstance(source, dict):
            continue
        for code in source.get("diagnosis_code_candidates", []):
            if isinstance(code, str) and code and code not in seen:
                seen.add(code)
                ordered_codes.append(code)
    return ordered_codes


def _find_billing_code_for_route(route_index_v4: Dict[str, Any], selected_route_id: str) -> Optional[str]:
    """Return a stable billing code that resolves to the selected route."""

    for route in route_index_v4.get("routes", []):
        if not isinstance(route, dict) or route.get("route_id") != selected_route_id:
            continue
        billing_codes = route.get("billing_codes", [])
        for billing_code in billing_codes:
            if isinstance(billing_code, str) and billing_code:
                return billing_code
    return None


def resolve_selection_scope(
    route_index_v4: Dict[str, Any],
    policy_master_v4: Dict[str, Any],
    billing_code: str,
    selected_phase: Optional[str] = None,
    selected_cluster_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve Screen 1 selection into a minimal scoped policy context.

    The returned payload is intentionally reduced for downstream use by the
    retrieval planner and cluster executor.
    """

    routes = route_index_v4.get("routes", [])
    matching_routes = [
        route for route in routes if isinstance(route, dict) and billing_code in route.get("billing_codes", [])
    ]

    if not matching_routes:
        return {
            "status": "blocked",
            "reason": "no_matching_route",
            "messages": [f"No route found for billing code {billing_code}."],
        }

    if len(matching_routes) > 1:
        return {
            "status": "blocked",
            "reason": "ambiguous_route",
            "matching_route_ids": [route.get("route_id") for route in matching_routes],
            "messages": [f"Multiple routes matched billing code {billing_code}."],
        }

    route = matching_routes[0]
    selected_route_id = route.get("route_id")
    if not isinstance(selected_route_id, str) or not selected_route_id:
        return {
            "status": "blocked",
            "reason": "invalid_route_index",
            "messages": ["Matched route is missing route_id."],
        }

    if route.get("terminal_disposition") != "continue":
        return {
            "status": "blocked",
            "reason": str(route.get("terminal_disposition", "stop")),
            "selected_route_id": selected_route_id,
            "route_summary": route,
            "messages": [f"Route {selected_route_id} is terminal."],
        }

    phases = route.get("phases", [])
    if route.get("phase_prompt_required") and not selected_phase:
        return {
            "status": "ok",
            "next_action": "collect_phase",
            "selected_route_id": selected_route_id,
            "route_summary": route,
            "allowed_phases": [phase.get("phase") for phase in phases if isinstance(phase, dict)],
        }

    phase_branch: Optional[Dict[str, Any]] = None
    if selected_phase:
        for phase in phases:
            if isinstance(phase, dict) and phase.get("phase") == selected_phase:
                phase_branch = phase
                break

    if phase_branch is None:
        for phase in phases:
            if isinstance(phase, dict) and phase.get("is_default"):
                phase_branch = phase
                break

    if phase_branch is None:
        return {
            "status": "blocked",
            "reason": "missing_phase_branch",
            "selected_route_id": selected_route_id,
            "messages": [f"No phase branch available for route {selected_route_id}."],
        }

    selected_phase_value = phase_branch.get("phase")
    if not isinstance(selected_phase_value, str) or not selected_phase_value:
        return {
            "status": "blocked",
            "reason": "invalid_phase_branch",
            "selected_route_id": selected_route_id,
            "messages": [f"Matched phase branch for route {selected_route_id} is invalid."],
        }

    cluster_shortlist = [
        cluster for cluster in phase_branch.get("cluster_summaries", []) if isinstance(cluster, dict)
    ]
    route_guard_ids = [
        guard_id for guard_id in phase_branch.get("route_guard_ids", []) if isinstance(guard_id, str) and guard_id
    ]

    if not selected_cluster_id:
        return {
            "status": "ok",
            "next_action": "collect_cluster",
            "selected_route_id": selected_route_id,
            "selected_phase": selected_phase_value,
            "route_summary": route,
            "phase_summary": phase_branch,
            "cluster_shortlist": cluster_shortlist,
            "route_guard_ids": route_guard_ids,
        }

    selected_cluster_summary = next(
        (cluster for cluster in cluster_shortlist if cluster.get("cluster_id") == selected_cluster_id),
        None,
    )
    if not isinstance(selected_cluster_summary, dict):
        return {
            "status": "blocked",
            "reason": "cluster_not_in_phase",
            "selected_route_id": selected_route_id,
            "selected_phase": selected_phase_value,
            "selected_cluster_id": selected_cluster_id,
            "messages": [f"Cluster {selected_cluster_id} is not available in phase {selected_phase_value}."],
        }

    route_map = _index_by_id(policy_master_v4.get("request_routes", []), "route_id")
    route_guard_map = _index_by_id(policy_master_v4.get("route_guards", []), "guard_id")
    cluster_guard_map = _index_by_id(policy_master_v4.get("cluster_entry_guards", []), "guard_id")
    cluster_map = _index_by_id(policy_master_v4.get("condition_clusters", []), "cluster_id")
    logic_profile_map = _index_by_id(policy_master_v4.get("logic_profiles", []), "logic_profile_id")
    criteria_map = _index_by_id(policy_master_v4.get("criteria_catalog", []), "criterion_id")

    selected_route = route_map.get(selected_route_id)
    selected_cluster = cluster_map.get(selected_cluster_id)
    if not isinstance(selected_route, dict) or not isinstance(selected_cluster, dict):
        return {
            "status": "blocked",
            "reason": "policy_master_mismatch",
            "selected_route_id": selected_route_id,
            "selected_phase": selected_phase_value,
            "selected_cluster_id": selected_cluster_id,
            "messages": ["Selected route or cluster could not be hydrated from policy_master_v4."],
        }

    cluster_entry_guard_ids = [
        guard_id
        for guard_id in selected_cluster_summary.get("cluster_entry_guard_ids", [])
        if isinstance(guard_id, str) and guard_id
    ]

    selected_route_guards = [
        route_guard_map[guard_id] for guard_id in route_guard_ids if guard_id in route_guard_map
    ]
    selected_cluster_entry_guards = [
        cluster_guard_map[guard_id] for guard_id in cluster_entry_guard_ids if guard_id in cluster_guard_map
    ]

    selected_logic_profiles: List[Dict[str, Any]] = []
    logic_profile_id = selected_cluster.get("logic_profile_id")
    if isinstance(logic_profile_id, str) and logic_profile_id and logic_profile_id != "UNKNOWN":
        profile = logic_profile_map.get(logic_profile_id)
        if isinstance(profile, dict):
            selected_logic_profiles.append(profile)

    inherited_cluster_ids = [
        cluster_id
        for cluster_id in selected_cluster.get("inherits_diagnosis_from_cluster_ids", [])
        if isinstance(cluster_id, str) and cluster_id
    ]
    selected_inherited_diagnosis_clusters = [
        cluster_map[cluster_id] for cluster_id in inherited_cluster_ids if cluster_id in cluster_map
    ]

    selected_cluster_criterion_ids = _collect_criterion_ids_from_logic_root(selected_cluster.get("logic_root"))
    for profile in selected_logic_profiles:
        selected_cluster_criterion_ids.update(_collect_criterion_ids_from_logic_root(profile.get("logic_root")))

    selected_inherited_diagnosis_criterion_ids: Set[str] = set()
    for inherited_cluster in selected_inherited_diagnosis_clusters:
        selected_inherited_diagnosis_criterion_ids.update(
            _collect_criterion_ids_from_logic_root(inherited_cluster.get("logic_root"))
        )

    # Inherited diagnosis logic should participate in downstream retrieval and
    # adjudication for the selected cluster, so fold those criterion IDs into
    # the selected cluster criterion set while also preserving a dedicated
    # traceability field.
    selected_cluster_criterion_ids.update(selected_inherited_diagnosis_criterion_ids)

    selected_route_guard_criterion_ids: Set[str] = set()
    for guard in selected_route_guards:
        selected_route_guard_criterion_ids.update(_collect_criterion_ids_from_logic_root(guard.get("logic_root")))

    selected_cluster_entry_guard_criterion_ids: Set[str] = set()
    for guard in selected_cluster_entry_guards:
        selected_cluster_entry_guard_criterion_ids.update(
            _collect_criterion_ids_from_logic_root(guard.get("logic_root"))
        )

    selected_criterion_ids = (
        selected_route_guard_criterion_ids
        | selected_cluster_entry_guard_criterion_ids
        | selected_cluster_criterion_ids
    )
    selected_criteria_catalog = [
        criteria_map[criterion_id] for criterion_id in selected_criterion_ids if criterion_id in criteria_map
    ]

    effective_diagnosis_code_candidates = _effective_diagnosis_code_candidates(
        selected_cluster=selected_cluster,
        selected_cluster_summary=selected_cluster_summary,
        inherited_clusters=selected_inherited_diagnosis_clusters,
    )

    scoped_policy_context = {
        "policy_id": policy_master_v4.get("policy_id", "UNKNOWN"),
        "selected_route_id": selected_route_id,
        "selected_phase": selected_phase_value,
        "selected_cluster_id": selected_cluster_id,
        "selected_route": selected_route,
        "selected_phase_branch": phase_branch,
        "selected_route_guards": selected_route_guards,
        "selected_cluster_summary": selected_cluster_summary,
        "selected_cluster": selected_cluster,
        "selected_cluster_entry_guards": selected_cluster_entry_guards,
        "selected_logic_profiles": selected_logic_profiles,
        "selected_inherited_diagnosis_clusters": selected_inherited_diagnosis_clusters,
        "effective_diagnosis_code_candidates": effective_diagnosis_code_candidates,
        "selected_route_guard_criterion_ids": sorted(selected_route_guard_criterion_ids),
        "selected_cluster_entry_guard_criterion_ids": sorted(selected_cluster_entry_guard_criterion_ids),
        "selected_inherited_diagnosis_criterion_ids": sorted(selected_inherited_diagnosis_criterion_ids),
        "selected_cluster_criterion_ids": sorted(selected_cluster_criterion_ids),
        "selected_criteria_catalog": selected_criteria_catalog,
    }

    return {
        "status": "ok",
        "next_action": "collect_cluster_guards" if cluster_entry_guard_ids else "proceed_screen_2",
        "route_summary": route,
        "cluster_shortlist": cluster_shortlist,
        "route_guard_ids": route_guard_ids,
        "cluster_entry_guard_ids": cluster_entry_guard_ids,
        "scoped_policy_context": scoped_policy_context,
    }


def regenerate_scoped_policy_context(
    route_index_v4: Dict[str, Any],
    policy_master_v4: Dict[str, Any],
    existing_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Regenerate a saved `scoped_policy_context*.json` artifact only.

    The input may be either the full saved wrapper payload or the inner
    `scoped_policy_context` object. The function re-resolves the selected
    route/phase/cluster against the current route index and policy master while
    preserving the saved artifact shape returned by `resolve_selection_scope`.
    """

    scoped_policy_context = existing_payload.get("scoped_policy_context", existing_payload)
    if not isinstance(scoped_policy_context, dict):
        raise ValueError("existing_payload must contain a scoped_policy_context object")

    selected_route_id = scoped_policy_context.get("selected_route_id")
    selected_phase = scoped_policy_context.get("selected_phase")
    selected_cluster_id = scoped_policy_context.get("selected_cluster_id")
    if not all(isinstance(value, str) and value for value in [selected_route_id, selected_phase, selected_cluster_id]):
        raise ValueError("existing scoped policy context is missing selected route, phase, or cluster identifiers")

    billing_code = _find_billing_code_for_route(route_index_v4, selected_route_id)
    if not billing_code:
        raise ValueError(f"Could not find a billing code for route {selected_route_id}")

    regenerated = resolve_selection_scope(
        route_index_v4=route_index_v4,
        policy_master_v4=policy_master_v4,
        billing_code=billing_code,
        selected_phase=selected_phase,
        selected_cluster_id=selected_cluster_id,
    )
    if regenerated.get("status") != "ok" or "scoped_policy_context" not in regenerated:
        raise ValueError(f"Could not regenerate scoped policy context: {regenerated}")

    regenerated_scoped = regenerated["scoped_policy_context"]
    if regenerated_scoped.get("selected_route_id") != selected_route_id:
        raise ValueError(
            "Regenerated scoped policy context does not match the original selected route "
            f"({regenerated_scoped.get('selected_route_id')} != {selected_route_id})"
        )
    return regenerated


def regenerate_scoped_policy_context_file(
    scoped_policy_context_path: Union[str, Path],
    route_index_v4: Dict[str, Any],
    policy_master_v4: Dict[str, Any],
) -> Dict[str, Any]:
    """Rewrite one saved `scoped_policy_context*.json` artifact in place."""

    path = Path(scoped_policy_context_path)
    existing_payload = json.loads(path.read_text())
    regenerated = regenerate_scoped_policy_context(
        route_index_v4=route_index_v4,
        policy_master_v4=policy_master_v4,
        existing_payload=existing_payload,
    )
    path.write_text(json.dumps(regenerated, indent=2) + "\n")
    return regenerated
