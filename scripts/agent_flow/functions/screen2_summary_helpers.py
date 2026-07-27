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


def _display(value: Any, fallback: str = "Not established") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or fallback
    return str(value)


def _display_json(value: Any, fallback: str = "Not established") -> str:
    if value is None or value == "":
        return fallback
    return json.dumps(value, ensure_ascii=False, default=str)


def _yes_no(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Not established"


def _plan_items_by_criterion_id(retrieval_plan: Any) -> Dict[str, Dict[str, Any]]:
    plan = _as_object(retrieval_plan)
    items = plan.get("plan_items")
    if not isinstance(items, list):
        return {}
    return {
        item["criterion_id"]: item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("criterion_id"), str)
    }


def _requirement_assessment_lines(
    criterion_id: str,
    criterion_result_map: Dict[str, Any],
    plan_items_by_criterion_id: Dict[str, Dict[str, Any]],
) -> List[str]:
    result = _as_object(criterion_result_map.get(criterion_id))
    plan_item = _as_object(plan_items_by_criterion_id.get(criterion_id))
    hints = _as_object(plan_item.get("execution_hints"))
    planned_qualifiers = hints.get("qualifiers")
    planned_qualifiers = planned_qualifiers if isinstance(planned_qualifiers, list) else []
    assessments = result.get("qualifier_assessments")
    assessments = assessments if isinstance(assessments, list) else []
    assessments_by_qualifier = {
        assessment.get("qualifier"): assessment
        for assessment in assessments
        if isinstance(assessment, dict) and assessment.get("qualifier")
    }

    lines = ["**Requirement assessment**", "", "Required modifiers:"]
    if planned_qualifiers:
        for qualifier in planned_qualifiers:
            assessment = _as_object(assessments_by_qualifier.get(qualifier))
            lines.extend(
                [
                    f"- Modifier: {_display(qualifier)}",
                    f"  - Required fact: {_display(assessment.get('required_fact'))}",
                    f"  - Evidence status: {_display(assessment.get('status'))}",
                    f"  - Chart finding: {_display_json(assessment.get('normalized_value'))}",
                ]
            )
    else:
        lines.append("- No additional modifiers required.")

    lines.extend(["", "Disqualifying clause:"])
    if not hints.get("disqualifying_clause"):
        lines.append("- Not required.")
    else:
        clause = _as_object(result.get("disqualifying_clause_assessment"))
        lines.extend(
            [
                f"- Disqualifying fact: {_display(clause.get('disqualifying_fact'))}",
                f"- Evidence status: {_display(clause.get('status'))}",
                f"- Documented as present: {_yes_no(clause.get('is_present'))}",
                f"- Chart finding: {_display_json(clause.get('normalized_value'))}",
            ]
        )
    return lines


def build_agent_review_summary(
    raw_review_result: Any,
    criterion_result_map: Any = None,
    retrieval_plan: Any = None,
) -> str:
    """Render the final reviewed Screen 2 payload as clinician-readable Markdown."""

    result = _as_object(raw_review_result)
    payload = _as_object(result.get("reviewed_screen_2_payload"))
    inner = _as_object(payload.get("payload"))
    display = _as_object(inner.get("selected_scope_display"))
    logic = _as_object(inner.get("logic_evaluation"))
    counts = _as_object(logic.get("criterion_counts"))
    raw_criteria = inner.get("criteria", [])
    criteria = raw_criteria if isinstance(raw_criteria, list) else []
    result_map = criterion_result_map if isinstance(criterion_result_map, dict) else {}
    plan_items = _plan_items_by_criterion_id(retrieval_plan)

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
                *_requirement_assessment_lines(
                    str(criterion.get("criterion_id", "")), result_map, plan_items
                ),
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


def get_agent_review_summary_metadata(raw_review_result: Any) -> Dict[str, Any]:
    """Return trace metadata associated with a rendered review summary."""

    result = _as_object(raw_review_result)
    payload = _as_object(result.get("reviewed_screen_2_payload"))
    inner = _as_object(payload.get("payload"))
    criteria = inner.get("criteria", [])
    return {
        "summary_version": "agent_review_summary_v2",
        "criterion_count": len(criteria) if isinstance(criteria, list) else 0,
        "human_validated": bool(result.get("human_validated")),
    }
