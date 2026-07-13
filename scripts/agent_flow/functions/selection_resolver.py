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


def _criterion_ids_from_guards(guards: Iterable[Dict[str, Any]]) -> List[str]:
    ordered_ids: List[str] = []
    for guard in guards:
        if not isinstance(guard, dict):
            continue
        for criterion_id in sorted(_collect_criterion_ids_from_logic_root(guard.get("logic_root"))):
            if criterion_id not in ordered_ids:
                ordered_ids.append(criterion_id)
    return ordered_ids


def _criteria_rows_from_ids(
    criteria_catalog: Iterable[Dict[str, Any]],
    criterion_ids: Iterable[str],
) -> List[Dict[str, Any]]:
    criteria_map = _index_by_id(criteria_catalog, "criterion_id")
    rows: List[Dict[str, Any]] = []
    for criterion_id in criterion_ids:
        criterion = criteria_map.get(criterion_id)
        if not isinstance(criterion, dict):
            continue
        rows.append(
            {
                "criterion_id": criterion_id,
                "criterion_kind": criterion.get("criterion_kind", "cluster_criterion"),
                "prompt": criterion.get("prompt", criterion_id),
                "answer_type": criterion.get("answer_type", "boolean"),
                "required": bool(criterion.get("required", True)),
            }
        )
    return rows


def _billing_code_options(route_index_v4: Dict[str, Any]) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for route in route_index_v4.get("routes", []):
        if not isinstance(route, dict):
            continue
        route_id = route.get("route_id")
        route_label = route.get("label") or route.get("ui_label") or route_id
        for code in route.get("billing_codes", []):
            if not isinstance(code, str) or not code or code in seen:
                continue
            seen.add(code)
            options.append(
                {
                    "billing_code": code,
                    "route_id": route_id,
                    "route_label": route_label,
                    "coverage_status": route.get("coverage_status"),
                }
            )
    return sorted(options, key=lambda item: item["billing_code"])


def _find_route_summary(route_index_v4: Dict[str, Any], selected_route_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(selected_route_id, str) or not selected_route_id:
        return None
    for route in route_index_v4.get("routes", []):
        if isinstance(route, dict) and route.get("route_id") == selected_route_id:
            return route
    return None


def _find_phase_branch_from_route(
    route_summary: Optional[Dict[str, Any]],
    selected_phase: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(route_summary, dict):
        return None
    phases = route_summary.get("phases", []) or []
    if isinstance(selected_phase, str) and selected_phase:
        for phase in phases:
            if isinstance(phase, dict) and phase.get("phase") == selected_phase:
                return phase
    for phase in phases:
        if isinstance(phase, dict) and phase.get("is_default"):
            return phase
    return None


def _route_display(route_summary: Optional[Dict[str, Any]], selected_route_id: Optional[str]) -> Dict[str, Any]:
    route_id = selected_route_id if isinstance(selected_route_id, str) else None
    return {
        "route_id": route_id,
        "route_label": _route_label(route_summary, route_id) if route_id else None,
    }


def _phase_label(phase: Optional[str]) -> Optional[str]:
    if not isinstance(phase, str) or not phase:
        return None
    return {
        "initial": "Initial",
        "continuation": "Continuation",
        "other": "Other",
    }.get(phase, phase.replace("_", " ").title())


def _route_label(
    route_summary: Optional[Dict[str, Any]],
    selected_route_id: str,
) -> str:
    if isinstance(route_summary, dict):
        label = route_summary.get("label") or route_summary.get("ui_label")
        if isinstance(label, str) and label:
            return label
    return selected_route_id


def _cluster_label(
    selected_cluster_summary: Optional[Dict[str, Any]],
    selected_cluster: Optional[Dict[str, Any]],
    selected_cluster_id: str,
) -> str:
    for source in [selected_cluster_summary, selected_cluster]:
        if not isinstance(source, dict):
            continue
        label = source.get("label") or source.get("condition_label")
        if isinstance(label, str) and label:
            return label
    return selected_cluster_id


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
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": None,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
        }

    if len(matching_routes) > 1:
        return {
            "status": "blocked",
            "reason": "ambiguous_route",
            "matching_route_ids": [route.get("route_id") for route in matching_routes],
            "messages": [f"Multiple routes matched billing code {billing_code}."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": None,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
        }

    route = matching_routes[0]
    selected_route_id = route.get("route_id")
    if not isinstance(selected_route_id, str) or not selected_route_id:
        return {
            "status": "blocked",
            "reason": "invalid_route_index",
            "messages": ["Matched route is missing route_id."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": None,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
        }

    if route.get("terminal_disposition") != "continue":
        return {
            "status": "blocked",
            "reason": str(route.get("terminal_disposition", "stop")),
            "messages": [f"Route {selected_route_id} is terminal."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
        }

    phases = route.get("phases", [])
    if route.get("phase_prompt_required") and not selected_phase:
        return {
            "status": "ok",
            "next_action": "collect_phase",
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": None,
                "selected_cluster_id": None,
            },
            "phase_values": [phase.get("phase") for phase in phases if isinstance(phase, dict)],
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
            "messages": [f"No phase branch available for route {selected_route_id}."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
        }

    selected_phase_value = phase_branch.get("phase")
    if not isinstance(selected_phase_value, str) or not selected_phase_value:
        return {
            "status": "blocked",
            "reason": "invalid_phase_branch",
            "messages": [f"Matched phase branch for route {selected_route_id} is invalid."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase,
                "selected_cluster_id": selected_cluster_id,
            },
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
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase_value,
                "selected_cluster_id": None,
            },
            "cluster_ids": [cluster.get("cluster_id") for cluster in cluster_shortlist if isinstance(cluster, dict)],
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
            "messages": [f"Cluster {selected_cluster_id} is not available in phase {selected_phase_value}."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase_value,
                "selected_cluster_id": selected_cluster_id,
            },
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
            "messages": ["Selected route or cluster could not be hydrated from policy_master_v4."],
            "selection": {
                "billing_code": billing_code,
                "selected_route_id": selected_route_id,
                "selected_phase": selected_phase_value,
                "selected_cluster_id": selected_cluster_id,
            },
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
        "selected_route_label": _route_label(route, selected_route_id),
        "selected_phase": selected_phase_value,
        "selected_phase_label": _phase_label(selected_phase_value),
        "selected_cluster_id": selected_cluster_id,
        "selected_cluster_label": _cluster_label(
            selected_cluster_summary,
            selected_cluster,
            selected_cluster_id,
        ),
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
        "selection": {
            "billing_code": billing_code,
            "selected_route_id": selected_route_id,
            "selected_phase": selected_phase_value,
            "selected_cluster_id": selected_cluster_id,
        },
        "phase_values": [selected_phase_value],
        "cluster_ids": [selected_cluster_id],
        "route_guard_ids": route_guard_ids,
        "cluster_entry_guard_ids": cluster_entry_guard_ids,
        "scoped_policy_context": scoped_policy_context,
    }


def build_screen1_payload(
    route_index_v4: Dict[str, Any],
    policy_master_v4: Dict[str, Any],
    billing_code: Optional[str] = None,
    selected_phase: Optional[str] = None,
    selected_cluster_id: Optional[str] = None,
    criterion_answers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a frontend-friendly Screen 1 payload around `resolve_selection_scope`.

    This is the deterministic wrapper the webapp/backend should use for the
    Screen 1 route/phase/cluster flow.
    """

    billing_code_options = _billing_code_options(route_index_v4)
    safe_answers = criterion_answers if isinstance(criterion_answers, dict) else {}

    if not billing_code:
        return {
            "status": "ok",
            "payload": {
                "step": "collect_billing_code",
                "selection": {
                    "billing_code": None,
                    "selected_route_id": None,
                    "selected_phase": None,
                    "selected_cluster_id": None,
                },
                "billing_code_options": billing_code_options,
                "route_display": {"route_id": None, "route_label": None},
                "phase_options": [],
                "cluster_options": [],
                "route_guard_questions": [],
                "cluster_entry_guard_questions": [],
                "selected_scope_context": None,
                "criterion_answers": safe_answers,
                "next_action": "collect_billing_code",
            },
            "messages": ["Select or enter a billing code to begin Screen 1 routing."],
        }

    resolved = resolve_selection_scope(
        route_index_v4=route_index_v4,
        policy_master_v4=policy_master_v4,
        billing_code=billing_code,
        selected_phase=selected_phase,
        selected_cluster_id=selected_cluster_id,
    )

    status = resolved.get("status", "blocked")
    if status != "ok":
        return {
            "status": status,
            "payload": {
                "step": "blocked",
                "billing_code": billing_code,
                "billing_code_options": billing_code_options,
                "selected_route": resolved.get("route_summary"),
                "phase_options": [],
                "cluster_options": [],
                "route_guard_questions": [],
                "cluster_entry_guard_questions": [],
                "scoped_policy_context": None,
                "criterion_answers": safe_answers,
                "next_action": resolved.get("reason", "blocked"),
            },
            "messages": list(resolved.get("messages", []) or []),
        }

    next_action = resolved.get("next_action")
    selection = resolved.get("selection", {}) if isinstance(resolved.get("selection"), dict) else {}
    selected_route_id = selection.get("selected_route_id")
    selected_phase_value = selection.get("selected_phase")
    route_summary = _find_route_summary(route_index_v4, selected_route_id)
    phase_branch = _find_phase_branch_from_route(route_summary, selected_phase_value)

    if next_action == "collect_phase":
        phases = []
        for phase in resolved.get("phase_values", []) or []:
            if not isinstance(phase, str) or not phase:
                continue
            phases.append({"value": phase, "label": _phase_label(phase)})
        return {
            "status": "ok",
            "payload": {
                "step": "collect_phase",
                "selection": selection,
                "billing_code_options": billing_code_options,
                "route_display": _route_display(route_summary, selected_route_id),
                "phase_options": phases,
                "cluster_options": [],
                "route_guard_questions": [],
                "cluster_entry_guard_questions": [],
                "selected_scope_context": None,
                "criterion_answers": safe_answers,
                "next_action": "collect_phase",
            },
            "messages": [],
        }

    if next_action == "collect_cluster":
        cluster_options: List[Dict[str, Any]] = []
        cluster_summaries = (phase_branch or {}).get("cluster_summaries", []) or []
        target_cluster_ids = [
            cluster_id for cluster_id in resolved.get("cluster_ids", []) or [] if isinstance(cluster_id, str)
        ]
        if target_cluster_ids:
            cluster_summaries = [
                cluster for cluster in cluster_summaries
                if isinstance(cluster, dict) and cluster.get("cluster_id") in target_cluster_ids
            ]
        for cluster in cluster_summaries:
            if not isinstance(cluster, dict):
                continue
            cluster_options.append(
                {
                    "cluster_id": cluster.get("cluster_id"),
                    "cluster_label": cluster.get("condition_label") or cluster.get("label") or cluster.get("cluster_id"),
                    "condition_key": cluster.get("condition_key"),
                    "diagnosis_code_candidates": cluster.get("diagnosis_code_candidates", []),
                }
            )
        return {
            "status": "ok",
            "payload": {
                "step": "collect_cluster",
                "selection": selection,
                "billing_code_options": billing_code_options,
                "route_display": _route_display(route_summary, selected_route_id),
                "phase_options": [{"value": selected_phase_value, "label": _phase_label(selected_phase_value)}] if isinstance(selected_phase_value, str) else [],
                "cluster_options": cluster_options,
                "route_guard_questions": [],
                "cluster_entry_guard_questions": [],
                "selected_scope_context": None,
                "criterion_answers": safe_answers,
                "next_action": "collect_cluster",
            },
            "messages": [],
        }

    scoped_policy_context = resolved.get("scoped_policy_context")
    if not isinstance(scoped_policy_context, dict):
        return {
            "status": "blocked",
            "payload": {
                "step": "blocked",
                "selection": selection,
                "billing_code_options": billing_code_options,
                "route_display": _route_display(route_summary, selected_route_id),
                "phase_options": [],
                "cluster_options": [],
                "route_guard_questions": [],
                "cluster_entry_guard_questions": [],
                "selected_scope_context": None,
                "criterion_answers": safe_answers,
                "next_action": "blocked",
            },
            "messages": ["Selection resolution did not produce a scoped policy context."],
        }

    criteria_catalog = scoped_policy_context.get("selected_criteria_catalog", []) or []
    route_guard_questions = _criteria_rows_from_ids(
        criteria_catalog,
        _criterion_ids_from_guards(scoped_policy_context.get("selected_route_guards", []) or []),
    )
    cluster_entry_guard_questions = _criteria_rows_from_ids(
        criteria_catalog,
        _criterion_ids_from_guards(scoped_policy_context.get("selected_cluster_entry_guards", []) or []),
    )

    return {
        "status": "ok",
        "payload": {
            "step": "review_scope",
            "selection": selection,
            "billing_code_options": billing_code_options,
            "route_display": _route_display(route_summary, selected_route_id),
            "phase_options": [
                {
                    "value": scoped_policy_context.get("selected_phase"),
                    "label": scoped_policy_context.get("selected_phase_label"),
                }
            ],
            "cluster_options": [
                {
                    "cluster_id": scoped_policy_context.get("selected_cluster_id"),
                    "cluster_label": scoped_policy_context.get("selected_cluster_label"),
                    "condition_key": (scoped_policy_context.get("selected_cluster_summary") or {}).get("condition_key"),
                    "diagnosis_code_candidates": scoped_policy_context.get("effective_diagnosis_code_candidates", []),
                }
            ],
            "route_guard_questions": route_guard_questions,
            "cluster_entry_guard_questions": cluster_entry_guard_questions,
            "selected_scope_context": scoped_policy_context,
            "criterion_answers": safe_answers,
            "next_action": "proceed_screen_2",
        },
        "messages": list(resolved.get("messages", []) or []),
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
    return regenerated_scoped


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
