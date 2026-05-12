"""Deterministic logic-tree evaluator for prior-auth selected cluster execution."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


CriterionResultMap = Dict[str, Dict[str, Any]]


def _empty_eval() -> Dict[str, Any]:
    return {
        "satisfied": False,
        "status": "unresolved",
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

    result["unresolved_criterion_ids"] = sorted(unresolved_ids)
    result["criterion_counts"] = {
        "satisfied": len(satisfied_ids),
        "not_satisfied": len(not_satisfied_ids),
        "unresolved": len(unresolved_ids),
    }
    return result


def _normalize_criterion_result(criterion_id: str, criterion_result_map: CriterionResultMap) -> Dict[str, Any]:
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
    elif status == "Missing":
        normalized["status"] = "unresolved"
        normalized["_unresolved_ids"].add(criterion_id)
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


def _evaluate_node(node: Optional[Dict[str, Any]], criterion_result_map: CriterionResultMap) -> Dict[str, Any]:
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
    logic_root: Optional[Dict[str, Any]],
    criterion_result_map: CriterionResultMap,
    supporting_logic_roots: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluate a selected cluster logic tree against a criterion-result map.

    If supporting logic roots are provided, the effective logic is treated as an
    implicit `all` across the primary root and every supporting root.
    """

    roots = [logic_root] + list(supporting_logic_roots or [])
    valid_roots = [root for root in roots if isinstance(root, dict)]

    if not valid_roots:
        return {
            "selected_cluster_satisfied": False,
            "selected_cluster_status": "unresolved",
            "unresolved_criterion_ids": [],
            "criterion_counts": {
                "satisfied": 0,
                "not_satisfied": 0,
                "unresolved": 0,
            },
        }

    effective_root = (
        valid_roots[0]
        if len(valid_roots) == 1
        else {
            "node_type": "group",
            "operator": "all",
            "children": valid_roots,
        }
    )

    result = _evaluate_node(effective_root, criterion_result_map)
    finalized = _finalize_eval(result)
    return {
        "selected_cluster_satisfied": finalized["satisfied"],
        "selected_cluster_status": finalized["status"],
        "unresolved_criterion_ids": finalized["unresolved_criterion_ids"],
        "criterion_counts": finalized["criterion_counts"],
    }
