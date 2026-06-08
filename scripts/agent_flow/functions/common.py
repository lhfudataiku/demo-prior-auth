"""Shared types and scope helpers for Screen 2 Structured Agent blocks."""

from __future__ import annotations

from typing import Any, Dict

CriterionResult = Dict[str, Any]
CriterionResultMap = Dict[str, CriterionResult]
StateDict = Dict[str, Any]
ScratchpadDict = Dict[str, Any]

DEFAULT_SCOPE_STATE_KEY = "selected_scope_context"


def get_selected_scope_context(state: StateDict) -> Dict[str, Any]:
    """Return the selected-scope object from agent state.

    Screen 2 should persist the inner scoped selection object under
    `selected_scope_context`, but this helper tolerates the older wrapper shape
    while flows are being migrated.
    """

    scope_context = state.get(DEFAULT_SCOPE_STATE_KEY, {}) or {}
    if isinstance(scope_context, dict):
        inner = scope_context.get("scoped_policy_context")
        if isinstance(inner, dict):
            return inner
        return scope_context
    return {}
