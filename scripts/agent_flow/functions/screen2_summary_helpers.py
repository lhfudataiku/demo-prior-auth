"""Clinician-readable terminal summary helpers for Screen 2 Agent Review."""

from __future__ import annotations

import json
from typing import Any, Dict, List


def _as_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _source_text(source: Any) -> str:
    if isinstance(source, dict):
        return str(
            source.get("excerpt")
            or source.get("quote")
            or source.get("evidence")
            or source
        )
    return str(source)


def build_agent_review_summary(raw_review_result: Any) -> str:
    """Render the final reviewed Screen 2 payload as clinician-readable Markdown."""

    result = _as_object(raw_review_result)
    payload = _as_object(result.get("reviewed_screen_2_payload"))
    inner = _as_object(payload.get("payload"))
    display = _as_object(inner.get("selected_scope_display"))
    logic = _as_object(inner.get("logic_evaluation"))
    counts = _as_object(logic.get("criterion_counts"))
    raw_criteria = inner.get("criteria", [])
    criteria = raw_criteria if isinstance(raw_criteria, list) else []

    lines: List[str] = [
        "# Prior Authorization Eligibility Review",
        "",
        "## Case Summary",
        "",
        f"- Policy: {display.get('route_label', 'Unknown')}",
        f"- Phase: {display.get('phase_label', 'Unknown')}",
        f"- Clinical cluster: {display.get('cluster_label', 'Unknown')}",
        f"- Review status: {payload.get('status', 'Unknown')}",
        f"- Eligibility status: {logic.get('selected_cluster_status', 'Unknown')}",
        "",
        "## Eligibility Counts",
        "",
        f"- Satisfied: {counts.get('satisfied', 0)}",
        f"- Not satisfied: {counts.get('not_satisfied', 0)}",
        f"- Unresolved: {counts.get('unresolved', 0)}",
        "",
        "## Criterion Review",
        "",
    ]

    for index, raw_criterion in enumerate(criteria, start=1):
        criterion = _as_object(raw_criterion)
        chart_result = _as_object(criterion.get("chart_result"))
        ui_resolution = _as_object(criterion.get("ui_resolution"))
        planner_context = _as_object(criterion.get("planner_context"))

        lines.extend(
            [
                f"### Criterion {index}: {criterion.get('criterion_id', 'Unknown')}",
                "",
                f"**Question:** {criterion.get('prompt', 'Unknown')}",
                "",
                f"- Criterion type: {criterion.get('criterion_kind', 'Unknown')}",
                "- Retrieval approach: "
                f"{planner_context.get('criterion_archetype', 'Unknown')} / "
                f"{planner_context.get('retrieval_strategy', 'Unknown')}",
                f"- Chart evidence status: {chart_result.get('status', 'Unknown')}",
                f"- Meets criterion: {chart_result.get('meets_criterion', 'Unknown')}",
                f"- Display state: {ui_resolution.get('display_state', 'Unknown')}",
                f"- Final source: {ui_resolution.get('final_source', 'Unknown')}",
                "",
                "**Agent justification**",
                "",
                str(chart_result.get("justification") or "No justification provided."),
                "",
                "**Evidence cited**",
                "",
            ]
        )

        sources = _as_object(chart_result.get("sources"))
        structured_sources = sources.get("structured", [])
        note_sources = sources.get("notes", [])
        structured_sources = structured_sources if isinstance(structured_sources, list) else []
        note_sources = note_sources if isinstance(note_sources, list) else []

        if structured_sources:
            lines.append("Structured evidence:")
            lines.extend(f"- {_source_text(source)}" for source in structured_sources)
            lines.append("")

        if note_sources:
            lines.append("Clinical note evidence:")
            lines.extend(f"- {_source_text(source)}" for source in note_sources)
            lines.append("")

        if not structured_sources and not note_sources:
            lines.extend(["No supporting evidence was cited.", ""])

    return "\n".join(lines)
