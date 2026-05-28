"""Compatibility wrapper around Screen 2 Python block helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from scripts.agent_flow.functions.logic_tree_helpers import evaluate_logic_tree

CriterionResultMap = Dict[str, Dict[str, Any]]

__all__ = ["CriterionResultMap", "evaluate_logic_tree"]


def evaluate_logic_tree_wrapper(
    selected_scope_context: Optional[Dict[str, Any]],
    criterion_result_map: CriterionResultMap,
) -> Dict[str, Any]:
    """Backward-compatible alias for older imports."""

    return evaluate_logic_tree(selected_scope_context, criterion_result_map)
