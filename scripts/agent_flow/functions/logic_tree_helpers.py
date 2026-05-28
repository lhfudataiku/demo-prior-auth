"""Pure logic-tree evaluation helpers for Screen 2 Structured Agent state."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from scripts.agent_flow.functions.common import CriterionResultMap


def _empty_eval() -> Dict[str, Any]:
    return {
        "satisfied": False,
        "status": "unresolved",
        "satisfied_criterion_ids": [],
        "not_satisfied_criterion_ids": [],
        "unresolved_criterion_ids": [],
        "criterion_counts": {
            "satisfied": 0,
            "not_satisfied": 0,
            "unresolved": 0,
        },
        "_satisfied_ids": set(),
        "_not_satisfied_ids": set(),
        "_unresolved_ids": set(),
    }


def _finalize_eval(result: Dict[str, Any]) -> Dict[str, Any]:
    satisfied_ids = result.pop("_satisfied_ids")
    not_satisfied_ids = result.pop("_not_satisfied_ids")
    unresolved_ids = result.pop("_unresolved_ids")

    result["satisfied_criterion_ids"] = sorted(satisfied_ids)
    result["not_satisfied_criterion_ids"] = sorted(not_satisfied_ids)
    result["unresolved_criterion_ids"] = sorted(unresolved_ids)
    result["criterion_counts"] = {
        "satisfied": len(satisfied_ids),
        "not_satisfied": len(not_satisfied_ids),
        "unresolved": len(unresolved_ids),
    }
    return result


def _normalize_criterion_result(
    criterion_id: str,
    criterion_result_map: CriterionResultMap,
) -> Dict[str, Any]:
    raw = criterion_result_map.get(criterion_id, {})
    if not isinstance(raw, dict):
        raw = {}

    status = str(raw.get("status", "Unreviewed"))
    meets_criterion = bool(raw.get("meets_criterion", False))

    normalized = _empty_eval()
    if status == "Found" and meets_criterion:
        normalized["satisfied"] = True
        normalized["status"] = "satisfied"
        normalized["_satisfied_ids"].add(criterion_id)
    elif status == "Found" and not meets_criterion:
        normalized["status"] = "not_satisfied"
        normalized["_not_satisfied_ids"].add(criterion_id)
    else:
        normalized["status"] = "unresolved"
        normalized["_unresolved_ids"].add(criterion_id)

    return normalized


def _merge_sets(child_results: Iterable[Dict[str, Any]]) -> Dict[str, Set[str]]:
    satisfied_ids: Set[str] = set()
    not_satisfied_ids: Set[str] = set()
    unresolved_ids: Set[str] = set()
    for child in child_results:
        satisfied_ids.update(child.get("_satisfied_ids", set()))
        not_satisfied_ids.update(child.get("_not_satisfied_ids", set()))
        unresolved_ids.update(child.get("_unresolved_ids", set()))
    return {
        "_satisfied_ids": satisfied_ids,
        "_not_satisfied_ids": not_satisfied_ids,
        "_unresolved_ids": unresolved_ids,
    }


def _extract_logic_roots_from_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        root = item.get("logic_root")
        if isinstance(root, dict):
            roots.append(root)
    return roots


def _derive_logic_inputs_from_scope_context(
    selected_scope_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(selected_scope_context, dict):
        return {"logic_root": None, "supporting_logic_roots": []}

    selected_cluster = selected_scope_context.get("selected_cluster")
    logic_root = selected_cluster.get("logic_root") if isinstance(selected_cluster, dict) else None
    if not isinstance(logic_root, dict):
        logic_root = None

    supporting_logic_roots: List[Dict[str, Any]] = []
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_route_guards", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_cluster_entry_guards", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(selected_scope_context.get("selected_logic_profiles", []))
    )
    supporting_logic_roots.extend(
        _extract_logic_roots_from_items(
            selected_scope_context.get("selected_inherited_diagnosis_clusters", [])
        )
    )

    return {"logic_root": logic_root, "supporting_logic_roots": supporting_logic_roots}


def _evaluate_node(
    node: Optional[Dict[str, Any]],
    criterion_result_map: CriterionResultMap,
) -> Dict[str, Any]:
    if not isinstance(node, dict):
        return _empty_eval()

    node_type = node.get("node_type")
    if node_type == "criterion_ref":
        criterion_id = node.get("criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            return _empty_eval()
        return _normalize_criterion_result(criterion_id, criterion_result_map)

    if node_type != "group":
        return _empty_eval()

    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    child_results = [_evaluate_node(child, criterion_result_map) for child in children]
    merged = _merge_sets(child_results)

    satisfied_children = sum(1 for result in child_results if result["status"] == "satisfied")
    not_satisfied_children = sum(1 for result in child_results if result["status"] == "not_satisfied")
    unresolved_children = sum(1 for result in child_results if result["status"] == "unresolved")

    operator = str(node.get("operator", "all"))
    result = _empty_eval()
    result.update(merged)

    if operator == "all":
        if not_satisfied_children > 0:
            result["status"] = "not_satisfied"
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "satisfied"
            result["satisfied"] = True
        return result

    if operator == "any":
        if satisfied_children > 0:
            result["status"] = "satisfied"
            result["satisfied"] = True
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "not_satisfied"
        return result

    if operator == "none":
        if satisfied_children > 0:
            result["status"] = "not_satisfied"
        elif unresolved_children > 0:
            result["status"] = "unresolved"
        else:
            result["status"] = "satisfied"
            result["satisfied"] = True
        return result

    if operator.startswith("at_least:"):
        try:
            threshold = int(operator.split(":", 1)[1])
        except (IndexError, ValueError):
            threshold = 0

        possible_max = satisfied_children + unresolved_children
        if satisfied_children >= threshold:
            result["status"] = "satisfied"
            result["satisfied"] = True
        elif possible_max < threshold:
            result["status"] = "not_satisfied"
        else:
            result["status"] = "unresolved"
        return result

    return result


def evaluate_logic_tree(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_result_map: CriterionResultMap,
) -> Dict[str, Any]:
    """Evaluate selected-scope logic against a criterion-result map."""

    derived = _derive_logic_inputs_from_scope_context(selected_scope_context)
    logic_root = derived["logic_root"]
    supporting_logic_roots = derived["supporting_logic_roots"]

    roots = [logic_root] + list(supporting_logic_roots)
    valid_roots = [root for root in roots if isinstance(root, dict)]

    if not valid_roots:
        return {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "satisfied_criterion_ids": [],
            "not_satisfied_criterion_ids": [],
            "unresolved_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 0,
                "not_satisfied": 0,
                "unresolved": 0,
            },
        }

    effective_root = valid_roots[0] if len(valid_roots) == 1 else {
        "node_type": "group",
        "operator": "all",
        "children": valid_roots,
    }

    result = _evaluate_node(effective_root, criterion_result_map)
    finalized = _finalize_eval(result)
    return {
        "selected_cluster_satisfied": finalized["satisfied"],
        "selected_cluster_status": finalized["status"],
        "satisfied_criterion_ids": finalized["satisfied_criterion_ids"],
        "not_satisfied_criterion_ids": finalized["not_satisfied_criterion_ids"],
        "unresolved_criterion_ids": finalized["unresolved_criterion_ids"],
        "criterion_counts": finalized["criterion_counts"],
    }
