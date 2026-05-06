"""Dataiku Code Agent that traverses questionnaires with a thin routing layer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Set

import dataiku
from dataiku.llm.python import BaseLLM


# ---------------------------------------------------------------------------
# Agent contract (evaluator delegates to this implementation)
# ---------------------------------------------------------------------------


class ChartQueryAgent:
    """Minimal interface for evaluating a single criterion."""

    def evaluate_criterion(
        self,
        subject_id: str,
        criterion: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def prefilter_policy_codes(
        self,
        subject_id: str,
        parsed_policy: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return None


@dataclass
class EvalResult:
    node_id: str
    satisfied: bool
    node_type: str
    prompt: Optional[str] = None
    evidence_group_text: Optional[str] = None
    skipped: bool = False
    children: Optional[List["EvalResult"]] = None
    agent_result: Optional[Dict[str, Any]] = None


class CriterionRouter:
    """Normalizes execution hints and provides lightweight routing directives."""

    _ALLOWED_ARCHETYPES = {
        "ARC_observation_threshold_numeric",
        "ARC_dx_code_range_with_lookback",
        "ARC_imaging_or_observation",
        "ARC_demographic_age_or_gender",
        "ARC_medication_exposure_presence",
        "ARC_medication_trial_duration",
        "ARC_latest_observation_snapshot",
        "ARC_procedure_code_presence",
        "ARC_encounter_timing_or_setting",
        "ARC_note_only",
        "ARC_hybrid_structured_note",
        "UNKNOWN",
    }
    _ALLOWED_STRATEGIES = {"sql_first", "note_first", "hybrid"}
    _ALLOWED_ENTITIES = {
        "patient",
        "condition",
        "encounter",
        "medication_request",
        "medication",
        "observation",
        "imaging",
        "procedure",
        "document",
        "UNKNOWN",
    }
    _ALLOWED_TIME_ANCHORS = {
        "encounter_start_datetime",
        "effective_datetime",
        "order_datetime",
        "procedure_datestart",
        "NONE",
        "UNKNOWN",
    }
    _SQL_ONLY_ARCHETYPES = {
        "ARC_dx_code_range_with_lookback",
        "ARC_demographic_age_or_gender",
        "ARC_latest_observation_snapshot",
        "ARC_procedure_code_presence",
        "ARC_encounter_timing_or_setting",
    }

    def route(self, criterion: Dict[str, Any]) -> Dict[str, Any]:
        raw_hints = criterion.get("execution_hints", {})
        hints = raw_hints if isinstance(raw_hints, dict) else {}

        archetype = self._normalize_enum(
            value=hints.get("criterion_archetype"),
            allowed=self._ALLOWED_ARCHETYPES,
            fallback="UNKNOWN",
        )
        strategy = self._normalize_strategy(hints.get("retrieval_strategy"), archetype)
        entity = self._normalize_enum(
            value=hints.get("semantic_model_entity"),
            allowed=self._ALLOWED_ENTITIES,
            fallback="UNKNOWN",
        )
        time_anchor = self._normalize_enum(
            value=hints.get("time_anchor_field"),
            allowed=self._ALLOWED_TIME_ANCHORS,
            fallback="UNKNOWN",
        )

        normalized_hints: Dict[str, Any] = {
            "criterion_archetype": archetype,
            "retrieval_strategy": strategy,
            "semantic_model_entity": entity,
            "time_anchor_field": time_anchor,
        }

        route_plan = self._build_route_plan(archetype=archetype, strategy=strategy)
        return {
            "normalized_execution_hints": normalized_hints,
            "route_plan": route_plan,
        }

    @staticmethod
    def _normalize_enum(value: Any, allowed: set, fallback: str) -> str:
        if isinstance(value, str) and value in allowed:
            return value
        return fallback

    def _normalize_strategy(self, raw_strategy: Any, archetype: str) -> str:
        if isinstance(raw_strategy, str) and raw_strategy in self._ALLOWED_STRATEGIES:
            return raw_strategy
        if archetype == "ARC_note_only":
            return "note_first"
        if archetype == "ARC_hybrid_structured_note":
            return "hybrid"
        return "sql_first"

    def _build_route_plan(self, archetype: str, strategy: str) -> Dict[str, Any]:
        primary_tool = "ehr_sql_query_tool"
        fallback_tool = "none"
        max_tool_hops = 1

        if strategy == "note_first":
            primary_tool = "clinical_note_semantic_search_tool"
            fallback_tool = "ehr_sql_query_tool"
            max_tool_hops = 2
        elif strategy == "hybrid":
            primary_tool = "ehr_sql_query_tool"
            fallback_tool = "clinical_note_semantic_search_tool"
            max_tool_hops = 2
        elif archetype not in self._SQL_ONLY_ARCHETYPES:
            fallback_tool = "clinical_note_semantic_search_tool"
            max_tool_hops = 2

        return {
            "primary_tool": primary_tool,
            "fallback_tool": fallback_tool,
            "max_tool_hops": max_tool_hops,
            "stop_when_primary_resolves": True,
            "sql_only_for_missing": archetype in self._SQL_ONLY_ARCHETYPES,
        }


class QuestionnaireEvaluator:
    """Traverses policy/questionnaire nodes with short-circuit logic."""

    _PREFILTERABLE_ARCHETYPES = {
        "ARC_dx_code_range_with_lookback",
        "ARC_imaging_or_observation",
        "ARC_procedure_code_presence",
    }
    _ALLOWED_PREFILTER_MODES = {"off", "reorder", "prune"}
    _ALLOWED_PREFILTER_FOCUS_MODES = {"off", "hit_only"}

    def __init__(
        self,
        agent: ChartQueryAgent,
        parallel_groups: bool = False,
        max_parallel_groups: int = 4,
        enable_code_prefilter: bool = True,
        criterion_prefilter_mode: str = "prune",
        prefilter_focus_mode: str = "hit_only",
    ) -> None:
        self.agent = agent
        self.parallel_groups = parallel_groups
        self.max_parallel_groups = max(1, max_parallel_groups)
        self.enable_code_prefilter = enable_code_prefilter
        self.criterion_prefilter_mode = self._normalize_prefilter_mode(criterion_prefilter_mode)
        self.prefilter_focus_mode = self._normalize_prefilter_focus_mode(prefilter_focus_mode)

    def evaluate_policy(self, subject_id: str, parsed_policy: Dict[str, Any]) -> Dict[str, Any]:
        questionnaire = parsed_policy.get("questionnaire", [])
        prefilter_hits = self._resolve_prefilter_hits(subject_id, parsed_policy)
        group_results = self._evaluate_top_level_groups(subject_id, questionnaire, prefilter_hits)

        return {
            "document_type": parsed_policy.get("document_type", "UNKNOWN"),
            "policy_id": parsed_policy.get("subject_matter", {}).get("policy_id", "UNKNOWN"),
            "subject_id": subject_id,
            "group_results": [self._to_dict(r) for r in group_results],
            "eligible_groups": [r.node_id for r in group_results if r.satisfied],
        }

    def _evaluate_top_level_groups(
        self,
        subject_id: str,
        groups: List[Dict[str, Any]],
        prefilter_hits: Optional[Set[str]],
    ) -> List[EvalResult]:
        ordered_results: List[Optional[EvalResult]] = [None] * len(groups)
        to_evaluate: List[tuple[int, Dict[str, Any]]] = []

        for index, group in enumerate(groups):
            if prefilter_hits is not None and self._should_skip_group_by_prefilter(group, prefilter_hits):
                ordered_results[index] = self._skip_group_by_prefilter(group, prefilter_hits)
            else:
                to_evaluate.append((index, group))

        if not to_evaluate:
            return [result for result in ordered_results if result is not None]

        if self.parallel_groups and len(to_evaluate) > 1:
            max_workers = min(self.max_parallel_groups, len(to_evaluate))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(self._eval_node, subject_id, group, None, prefilter_hits): index
                    for index, group in to_evaluate
                }
                for future in as_completed(futures):
                    ordered_results[futures[future]] = future.result()
        else:
            for index, group in to_evaluate:
                ordered_results[index] = self._eval_node(subject_id, group, prefilter_hits=prefilter_hits)

        return [result for result in ordered_results if result is not None]

    def _resolve_prefilter_hits(self, subject_id: str, parsed_policy: Dict[str, Any]) -> Optional[Set[str]]:
        if not self.enable_code_prefilter:
            return None
        prefilter_result = self.agent.prefilter_policy_codes(subject_id, parsed_policy)
        if not isinstance(prefilter_result, dict):
            return None
        raw_codes = prefilter_result.get("matched_inclusion_codes")
        if not isinstance(raw_codes, list):
            return set()
        return {self._normalize_code_token(str(code)) for code in raw_codes if str(code).strip()}

    def _should_skip_group_by_prefilter(self, group: Dict[str, Any], prefilter_hits: Set[str]) -> bool:
        criteria = list(self._iter_criteria(group))
        if not criteria:
            return False

        operator = str(group.get("operator", "")).lower()
        strict_criteria = [c for c in criteria if self._is_strict_prefilter_criterion(c)]
        if not strict_criteria:
            return False

        if operator == "all":
            return any(not self._criterion_has_prefilter_hit(c, prefilter_hits) for c in strict_criteria)

        if operator == "any" or operator.startswith("at_least:"):
            if len(strict_criteria) != len(criteria):
                return False
            possible_true = sum(1 for c in strict_criteria if self._criterion_has_prefilter_hit(c, prefilter_hits))
            if operator == "any":
                return possible_true == 0
            try:
                needed = int(operator.split(":", 1)[1])
            except (IndexError, ValueError):
                return False
            return possible_true < needed

        return False

    def _skip_group_by_prefilter(self, group: Dict[str, Any], prefilter_hits: Set[str]) -> EvalResult:
        matched_codes = sorted(prefilter_hits)
        evidence_group_text = group.get("evidence_group_text")
        result = self._skip_node(group, evidence_group_text)
        result.agent_result = {
            "status": "SkippedByPrefilter",
            "justification": (
                "Skipped before criterion evaluation because one-shot inclusion-code prefilter "
                "found no relevant match for this group."
            ),
            "matched_inclusion_codes": matched_codes,
        }
        return result

    @staticmethod
    def _normalize_code_token(code: str) -> str:
        normalized = code.upper().replace("–", "-")
        normalized = re.sub(r"\s*-\s*", " - ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _iter_criteria(self, node: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        node_type = node.get("node_type")
        if node_type == "criterion":
            yield node
            return
        for child in node.get("children", []):
            yield from self._iter_criteria(child)

    def _criterion_codes(self, criterion: Dict[str, Any]) -> Set[str]:
        code_binding = criterion.get("code_binding", {})
        raw_codes: Any = []
        if isinstance(code_binding, dict):
            raw_codes = code_binding.get("source_codes", [])
        if not isinstance(raw_codes, list):
            query_fragment = criterion.get("ehr_query_fragment", {})
            raw_codes = query_fragment.get("codes", []) if isinstance(query_fragment, dict) else []
        if not isinstance(raw_codes, list):
            return set()
        return {
            self._normalize_code_token(str(code))
            for code in raw_codes
            if isinstance(code, str) and code.strip()
        }

    def _is_strict_prefilter_criterion(self, criterion: Dict[str, Any]) -> bool:
        codes = self._criterion_codes(criterion)
        if not codes:
            return False
        if not bool(criterion.get("prefilter_eligible", False)):
            return False
        code_binding = criterion.get("code_binding", {})
        if isinstance(code_binding, dict):
            status = str(code_binding.get("status", "")).strip().lower()
            if status not in {"mapped", "passthrough"}:
                return False
        execution_hints = criterion.get("execution_hints", {})
        if not isinstance(execution_hints, dict):
            return False
        archetype = execution_hints.get("criterion_archetype")
        return archetype in self._PREFILTERABLE_ARCHETYPES

    @classmethod
    def _normalize_prefilter_mode(cls, mode: Any) -> str:
        if isinstance(mode, str):
            normalized = mode.strip().lower()
            if normalized in cls._ALLOWED_PREFILTER_MODES:
                return normalized
        return "reorder"

    def _is_deterministic_prefilter_criterion(self, criterion: Dict[str, Any]) -> bool:
        if not self._is_strict_prefilter_criterion(criterion):
            return False
        code_binding = criterion.get("code_binding", {})
        if not isinstance(code_binding, dict):
            return False
        status = str(code_binding.get("status", "")).strip().lower()
        return status == "mapped"

    @classmethod
    def _normalize_prefilter_focus_mode(cls, mode: Any) -> str:
        if isinstance(mode, str):
            normalized = mode.strip().lower()
            if normalized in cls._ALLOWED_PREFILTER_FOCUS_MODES:
                return normalized
        return "off"

    def _group_allows_prefilter_focus(self, group: Dict[str, Any]) -> bool:
        if str(group.get("operator", "")).lower() != "any":
            return False
        raw_codes = group.get("prefilter_inclusion_codes")
        return isinstance(raw_codes, list) and len(raw_codes) > 0

    def _should_focus_on_prefilter_hits(
        self,
        group: Dict[str, Any],
        ordered_children: List[tuple[int, Dict[str, Any]]],
        prefilter_hits: Optional[Set[str]],
    ) -> bool:
        if self.prefilter_focus_mode != "hit_only" or not prefilter_hits:
            return False
        if not self._group_allows_prefilter_focus(group):
            return False
        for _, child in ordered_children:
            if child.get("node_type") != "criterion":
                continue
            if not self._is_deterministic_prefilter_criterion(child):
                continue
            if self._criterion_has_prefilter_hit(child, prefilter_hits):
                return True
        return False

    def _should_skip_criterion_by_focus(
        self,
        criterion: Dict[str, Any],
        focus_on_hits: bool,
        prefilter_hits: Optional[Set[str]],
    ) -> bool:
        if not focus_on_hits:
            return False
        if self._is_deterministic_prefilter_criterion(criterion):
            return not self._criterion_has_prefilter_hit(criterion, prefilter_hits or set())
        return True

    def _skip_criterion_by_focus(
        self,
        criterion: Dict[str, Any],
        evidence_group_text: Optional[str],
        prefilter_hits: Optional[Set[str]],
    ) -> EvalResult:
        matched_codes = sorted(prefilter_hits or [])
        return EvalResult(
            node_id=criterion.get("id", "UNKNOWN"),
            node_type="criterion",
            satisfied=False,
            prompt=criterion.get("prompt"),
            evidence_group_text=evidence_group_text,
            skipped=True,
            agent_result={
                "status": "SkippedByPrefilterFocus",
                "meets_criterion": False,
                "extracted_value": "",
                "justification": (
                    "Skipped criterion evaluation because group-level prefilter focus was enabled and "
                    "this criterion was not aligned with matched diagnosis codes."
                ),
                "matched_inclusion_codes": matched_codes,
            },
        )

    def _should_prune_criterion_by_prefilter(
        self,
        criterion: Dict[str, Any],
        prefilter_hits: Optional[Set[str]],
    ) -> bool:
        if self.criterion_prefilter_mode != "prune" or not prefilter_hits:
            return False
        if not self._is_deterministic_prefilter_criterion(criterion):
            return False
        return not self._criterion_has_prefilter_hit(criterion, prefilter_hits)

    def _prune_criterion_by_prefilter(
        self,
        criterion: Dict[str, Any],
        evidence_group_text: Optional[str],
        prefilter_hits: Optional[Set[str]],
    ) -> EvalResult:
        matched_codes = sorted(prefilter_hits or [])
        return EvalResult(
            node_id=criterion.get("id", "UNKNOWN"),
            node_type="criterion",
            satisfied=False,
            prompt=criterion.get("prompt"),
            evidence_group_text=evidence_group_text,
            skipped=True,
            agent_result={
                "status": "SkippedByPrefilterCriterion",
                "meets_criterion": False,
                "extracted_value": "",
                "justification": (
                    "Skipped criterion evaluation because deterministic mapped codes did not match "
                    "the patient's one-shot prefilter hits."
                ),
                "matched_inclusion_codes": matched_codes,
            },
        )

    def _criterion_has_prefilter_hit(self, criterion: Dict[str, Any], prefilter_hits: Set[str]) -> bool:
        return bool(self._criterion_codes(criterion) & prefilter_hits)

    def _child_prefilter_score(self, node: Dict[str, Any], prefilter_hits: Set[str]) -> int:
        node_type = node.get("node_type")
        if node_type == "criterion":
            if not self._is_strict_prefilter_criterion(node):
                return 0
            return 2 if self._criterion_has_prefilter_hit(node, prefilter_hits) else -2

        strict_criteria = [criterion for criterion in self._iter_criteria(node) if self._is_strict_prefilter_criterion(criterion)]
        if not strict_criteria:
            return 0
        matched = sum(1 for criterion in strict_criteria if self._criterion_has_prefilter_hit(criterion, prefilter_hits))
        if matched == len(strict_criteria):
            return 1
        if matched > 0:
            return 0
        return -1

    def _ordered_children(
        self,
        children: List[Dict[str, Any]],
        operator: str,
        prefilter_hits: Optional[Set[str]],
    ) -> List[tuple[int, Dict[str, Any]]]:
        ordered = list(enumerate(children))
        if not prefilter_hits or self.criterion_prefilter_mode == "off":
            return ordered

        reverse = operator in {"any", "none"} or operator.startswith("at_least:")
        ordered.sort(
            key=lambda item: self._child_prefilter_score(item[1], prefilter_hits),
            reverse=reverse,
        )
        return ordered

    def evaluate_policy_stream(self, subject_id: str, parsed_policy: Dict[str, Any]) -> Iterator[str]:
        questionnaire = parsed_policy.get("questionnaire", [])
        prefilter_hits = self._resolve_prefilter_hits(subject_id, parsed_policy)
        yield f"Starting policy evaluation for {len(questionnaire)} top-level group(s).\n"
        if prefilter_hits is not None:
            if prefilter_hits:
                preview_codes = ", ".join(sorted(prefilter_hits)[:8])
                yield f"One-shot prefilter matched {len(prefilter_hits)} inclusion code(s): {preview_codes}\n"
            else:
                yield "One-shot prefilter matched 0 inclusion codes.\n"

        group_results: List[EvalResult] = []
        for index, group in enumerate(questionnaire, start=1):
            if prefilter_hits is not None and self._should_skip_group_by_prefilter(group, prefilter_hits):
                group_results.append(self._skip_group_by_prefilter(group, prefilter_hits))
                yield (
                    f"Skipping group {index}/{len(questionnaire)}: {group.get('id', 'UNKNOWN')} "
                    "due to one-shot prefilter.\n"
                )
                continue
            yield f"Evaluating group {index}/{len(questionnaire)}: {group.get('id', 'UNKNOWN')}\n"
            group_result = yield from self._eval_node_stream(subject_id, group, prefilter_hits=prefilter_hits)
            group_results.append(group_result)

        evaluation = {
            "document_type": parsed_policy.get("document_type", "UNKNOWN"),
            "policy_id": parsed_policy.get("subject_matter", {}).get("policy_id", "UNKNOWN"),
            "subject_id": subject_id,
            "group_results": [self._to_dict(r) for r in group_results],
            "eligible_groups": [r.node_id for r in group_results if r.satisfied],
        }
        yield f"Finished policy evaluation. Eligible groups: {len(evaluation['eligible_groups'])}\n"
        return evaluation

    def _eval_node(
        self,
        subject_id: str,
        node: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
        prefilter_hits: Optional[Set[str]] = None,
    ) -> EvalResult:
        node_type = node["node_type"]
        if node_type == "criterion":
            agent_result = self.agent.evaluate_criterion(
                subject_id,
                node,
                evidence_group_text=evidence_group_text,
            )
            return EvalResult(
                node_id=node["id"],
                node_type="criterion",
                satisfied=bool(agent_result.get("meets_criterion", False)),
                prompt=node.get("prompt"),
                evidence_group_text=evidence_group_text,
                agent_result=agent_result,
            )
        if node_type == "group":
            return self._eval_group(
                subject_id,
                node,
                evidence_group_text=evidence_group_text,
                prefilter_hits=prefilter_hits,
            )
        raise ValueError(f"Unknown node_type: {node_type}")

    def _eval_node_stream(
        self,
        subject_id: str,
        node: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
        prefilter_hits: Optional[Set[str]] = None,
    ) -> Iterator[Any]:
        node_type = node["node_type"]
        if node_type == "criterion":
            yield f"  Checking criterion {node['id']}: {node.get('prompt', 'UNKNOWN')}\n"
            agent_result = self.agent.evaluate_criterion(
                subject_id,
                node,
                evidence_group_text=evidence_group_text,
            )
            result = EvalResult(
                node_id=node["id"],
                node_type="criterion",
                satisfied=bool(agent_result.get("meets_criterion", False)),
                prompt=node.get("prompt"),
                evidence_group_text=evidence_group_text,
                agent_result=agent_result,
            )
            yield (
                f"  Result for {node['id']}: status={agent_result.get('status', 'Ambiguous')}, "
                f"meets_criterion={result.satisfied}\n"
            )
            extracted_value = agent_result.get("extracted_value")
            if extracted_value is not None:
                yield f"  Extracted value: {json.dumps(extracted_value, ensure_ascii=False)}\n"
            justification = agent_result.get("justification")
            if justification:
                yield f"  Justification: {justification}\n"
            return result
        if node_type == "group":
            return (
                yield from self._eval_group_stream(
                    subject_id,
                    node,
                    evidence_group_text=evidence_group_text,
                    prefilter_hits=prefilter_hits,
                )
            )
        raise ValueError(f"Unknown node_type: {node_type}")

    def _eval_group(
        self,
        subject_id: str,
        group: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
        prefilter_hits: Optional[Set[str]] = None,
    ) -> EvalResult:
        operator = group["operator"]
        children = group.get("children", [])
        ordered_children = self._ordered_children(children, operator, prefilter_hits)
        group_evidence_group_text = group.get("evidence_group_text", evidence_group_text)
        focus_on_hits = self._should_focus_on_prefilter_hits(group, ordered_children, prefilter_hits)

        child_results: List[EvalResult] = []

        if operator == "all":
            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                else:
                    r = self._eval_node(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if not r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=True,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        if operator == "any":
            for pos, (_, child) in enumerate(ordered_children):
                if child.get("node_type") == "criterion":
                    if self._should_skip_criterion_by_focus(child, focus_on_hits, prefilter_hits):
                        r = self._skip_criterion_by_focus(
                            child,
                            group_evidence_group_text,
                            prefilter_hits,
                        )
                    elif self._should_prune_criterion_by_prefilter(child, prefilter_hits):
                        r = self._prune_criterion_by_prefilter(
                            child,
                            group_evidence_group_text,
                            prefilter_hits,
                        )
                    else:
                        r = self._eval_node(
                            subject_id,
                            child,
                            evidence_group_text=group_evidence_group_text,
                            prefilter_hits=prefilter_hits,
                        )
                else:
                    r = self._eval_node(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=True,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=False,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        if operator == "none":
            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                else:
                    r = self._eval_node(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=True,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        if operator.startswith("at_least:"):
            needed = int(operator.split(":", 1)[1])
            passed = 0
            remaining = len(ordered_children)

            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                else:
                    r = self._eval_node(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                remaining -= 1
                if r.satisfied:
                    passed += 1
                if passed >= needed:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=True,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                if passed + remaining < needed:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=(passed >= needed),
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        raise ValueError(f"Unsupported operator: {operator}")

    def _eval_group_stream(
        self,
        subject_id: str,
        group: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
        prefilter_hits: Optional[Set[str]] = None,
    ) -> Iterator[Any]:
        operator = group["operator"]
        children = group.get("children", [])
        ordered_children = self._ordered_children(children, operator, prefilter_hits)
        group_evidence_group_text = group.get("evidence_group_text", evidence_group_text)
        focus_on_hits = self._should_focus_on_prefilter_hits(group, ordered_children, prefilter_hits)

        yield f"Entering group {group['id']} ({operator})\n"
        child_results: List[EvalResult] = []

        if operator == "all":
            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                    yield f"  Prefilter-pruned criterion {child.get('id', 'UNKNOWN')}\n"
                else:
                    r = yield from self._eval_node_stream(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if not r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    yield f"Short-circuit group {group['id']} (all): one child failed.\n"
                    result = EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                    yield f"Leaving group {group['id']}: satisfied=False\n"
                    return result
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=True,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied=True\n"
            return result

        if operator == "any":
            for pos, (_, child) in enumerate(ordered_children):
                if child.get("node_type") == "criterion":
                    if self._should_skip_criterion_by_focus(child, focus_on_hits, prefilter_hits):
                        r = self._skip_criterion_by_focus(
                            child,
                            group_evidence_group_text,
                            prefilter_hits,
                        )
                        yield f"  Prefilter-focus skipped criterion {child.get('id', 'UNKNOWN')}\n"
                    elif self._should_prune_criterion_by_prefilter(child, prefilter_hits):
                        r = self._prune_criterion_by_prefilter(
                            child,
                            group_evidence_group_text,
                            prefilter_hits,
                        )
                        yield f"  Prefilter-pruned criterion {child.get('id', 'UNKNOWN')}\n"
                    else:
                        r = yield from self._eval_node_stream(
                            subject_id,
                            child,
                            evidence_group_text=group_evidence_group_text,
                            prefilter_hits=prefilter_hits,
                        )
                else:
                    r = yield from self._eval_node_stream(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    yield f"Short-circuit group {group['id']} (any): one child passed.\n"
                    result = EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=True,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                    yield f"Leaving group {group['id']}: satisfied=True\n"
                    return result
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=False,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied=False\n"
            return result

        if operator == "none":
            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                    yield f"  Prefilter-pruned criterion {child.get('id', 'UNKNOWN')}\n"
                else:
                    r = yield from self._eval_node_stream(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                if r.satisfied:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    yield f"Short-circuit group {group['id']} (none): one child passed.\n"
                    result = EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                    yield f"Leaving group {group['id']}: satisfied=False\n"
                    return result
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=True,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied=True\n"
            return result

        if operator.startswith("at_least:"):
            needed = int(operator.split(":", 1)[1])
            passed = 0
            remaining = len(ordered_children)

            for pos, (_, child) in enumerate(ordered_children):
                if (
                    child.get("node_type") == "criterion"
                    and self._should_prune_criterion_by_prefilter(child, prefilter_hits)
                ):
                    r = self._prune_criterion_by_prefilter(
                        child,
                        group_evidence_group_text,
                        prefilter_hits,
                    )
                    yield f"  Prefilter-pruned criterion {child.get('id', 'UNKNOWN')}\n"
                else:
                    r = yield from self._eval_node_stream(
                        subject_id,
                        child,
                        evidence_group_text=group_evidence_group_text,
                        prefilter_hits=prefilter_hits,
                    )
                child_results.append(r)
                remaining -= 1
                if r.satisfied:
                    passed += 1
                if passed >= needed:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    yield f"Short-circuit group {group['id']} (at_least): threshold reached.\n"
                    result = EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=True,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                    yield f"Leaving group {group['id']}: satisfied=True\n"
                    return result
                if passed + remaining < needed:
                    remaining_children = [remaining_child for _, remaining_child in ordered_children[pos + 1 :]]
                    child_results.extend(self._build_skipped_children(remaining_children, group_evidence_group_text))
                    yield f"Short-circuit group {group['id']} (at_least): threshold unreachable.\n"
                    result = EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=False,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                    yield f"Leaving group {group['id']}: satisfied=False\n"
                    return result
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=(passed >= needed),
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied={result.satisfied}\n"
            return result

        raise ValueError(f"Unsupported operator: {operator}")

    def _build_skipped_children(
        self,
        children: List[Dict[str, Any]],
        evidence_group_text: Optional[str],
    ) -> List[EvalResult]:
        return [self._skip_node(child, evidence_group_text) for child in children]

    def _skip_node(self, node: Dict[str, Any], evidence_group_text: Optional[str]) -> EvalResult:
        node_type = node.get("node_type", "criterion")
        if node_type == "criterion":
            return EvalResult(
                node_id=node.get("id", "UNKNOWN"),
                node_type="criterion",
                satisfied=False,
                prompt=node.get("prompt"),
                evidence_group_text=evidence_group_text,
                skipped=True,
            )
        if node_type == "group":
            group_evidence_group_text = node.get("evidence_group_text", evidence_group_text)
            skipped_children = [
                self._skip_node(child, group_evidence_group_text) for child in node.get("children", [])
            ]
            return EvalResult(
                node_id=node.get("id", "UNKNOWN"),
                node_type="group",
                satisfied=False,
                evidence_group_text=group_evidence_group_text,
                skipped=True,
                children=skipped_children,
            )
        raise ValueError(f"Unknown node_type: {node_type}")

    def _to_dict(self, result: EvalResult) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "node_id": result.node_id,
            "node_type": result.node_type,
            "satisfied": result.satisfied,
        }
        if result.skipped:
            out["skipped"] = True
        if result.prompt is not None:
            out["prompt"] = result.prompt
        if result.evidence_group_text is not None:
            out["evidence_group_text"] = result.evidence_group_text
        if result.agent_result is not None:
            out["agent_result"] = result.agent_result
        if result.children is not None:
            out["children"] = [self._to_dict(c) for c in result.children]
        return out


# ---------------------------------------------------------------------------
# Visual agent-backed evaluator
# ---------------------------------------------------------------------------


class VisualChartQueryAgent(ChartQueryAgent):
    """Delegates criterion evaluation to a controlled Dataiku Visual Agent."""

    def __init__(self, visual_agent_id: str) -> None:
        project = dataiku.api_client().get_default_project()
        self._visual_agent = project.get_agent(visual_agent_id).as_llm()
        self._router = CriterionRouter()

    @staticmethod
    def _normalize_code_token(code: str) -> str:
        normalized = code.upper().replace("–", "-")
        normalized = re.sub(r"\s*-\s*", " - ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _execute_visual_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        completion = self._visual_agent.new_completion().with_message(json.dumps(payload, indent=2))
        response = completion.execute()
        return self._parse_visual_agent_response(response.text)

    def evaluate_criterion(
        self,
        subject_id: str,
        criterion: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        route_info = self._router.route(criterion)
        normalized_criterion = dict(criterion)
        normalized_criterion["execution_hints"] = route_info["normalized_execution_hints"]

        prompt_payload = {
            "subject_id": subject_id,
            "criterion": normalized_criterion,
            "route_plan": route_info["route_plan"],
            "routing_instruction": (
                "Follow route_plan strictly. Use primary tool first, and only use fallback tool if "
                "the criterion remains unresolved after primary evidence. If relevant partial evidence is found "
                "but qualifier-level fields are missing, use status='Ambiguous' instead of 'Missing'."
            ),
        }
        if evidence_group_text is not None:
            prompt_payload["evidence_group_text"] = evidence_group_text
        parsed_response = self._execute_visual_payload(prompt_payload)
        result = {
            "extracted_value": parsed_response.get("extracted_value"),
            "meets_criterion": bool(parsed_response.get("meets_criterion", False)),
            "status": parsed_response.get("status", "Ambiguous"),
            "justification": parsed_response.get("justification", ""),
            "sources": parsed_response.get("sources", {}),
        }
        return self._normalize_partial_evidence_status(result)

    def prefilter_policy_codes(
        self,
        subject_id: str,
        parsed_policy: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        inclusion_codes = self._collect_inclusion_codes(parsed_policy)
        if not inclusion_codes:
            return None

        prefilter_payload = {
            "subject_id": subject_id,
            "criterion": {
                "id": "PREFILTER_INCLUSION_CODES",
                "node_type": "criterion",
                "prompt": (
                    "Identify which inclusion codes are present for this patient using structured EHR "
                    "evidence only. If a code range is provided, match when a patient diagnosis/procedure "
                    "falls within that policy range."
                ),
                "execution_hints": {
                    "criterion_archetype": "ARC_dx_code_range_with_lookback",
                    "retrieval_strategy": "sql_first",
                    "semantic_model_entity": "condition",
                    "time_anchor_field": "encounter_start_datetime",
                },
                "ehr_query_fragment": {
                    "field": "condition",
                    "operator": "exists",
                    "value": "One-shot inclusion code prefilter",
                    "codes": inclusion_codes,
                },
                "semantic_search_tokens": [],
            },
            "route_plan": {
                "primary_tool": "ehr_sql_query_tool",
                "fallback_tool": "none",
                "max_tool_hops": 1,
                "stop_when_primary_resolves": True,
                "sql_only_for_missing": True,
            },
            "routing_instruction": (
                "Perform one SQL-first prefilter pass. In extracted_value, list matched inclusion "
                "policy code strings exactly as provided by the policy parser, separated by ';'. "
                "Return empty extracted_value if none."
            ),
        }

        parsed_response = self._execute_visual_payload(prefilter_payload)
        matched_codes = self._extract_matched_inclusion_codes(parsed_response, inclusion_codes)
        return {
            "matched_inclusion_codes": sorted(matched_codes),
            "status": parsed_response.get("status", "Ambiguous"),
        }

    @staticmethod
    def _collect_inclusion_codes(parsed_policy: Dict[str, Any]) -> List[str]:
        codes: Set[str] = set()
        questionnaire = parsed_policy.get("questionnaire", [])
        if isinstance(questionnaire, list):
            stack: List[Dict[str, Any]] = [node for node in questionnaire if isinstance(node, dict)]
            while stack:
                node = stack.pop()
                if node.get("node_type") == "criterion":
                    if not bool(node.get("prefilter_eligible", False)):
                        continue
                    code_binding = node.get("code_binding", {})
                    if isinstance(code_binding, dict):
                        raw_codes = code_binding.get("source_codes", [])
                        if isinstance(raw_codes, list):
                            for code in raw_codes:
                                if isinstance(code, str) and code.strip():
                                    codes.add(code.strip())
                    continue
                for child in node.get("children", []):
                    if isinstance(child, dict):
                        stack.append(child)
        if codes:
            return sorted(codes)

        code_set = parsed_policy.get("code_set", {})
        if isinstance(code_set, dict):
            inclusion = code_set.get("inclusion", [])
            if isinstance(inclusion, list):
                for item in inclusion:
                    if isinstance(item, dict):
                        code = item.get("code")
                        if isinstance(code, str) and code.strip():
                            codes.add(code.strip())
        return sorted(codes)

    def _extract_matched_inclusion_codes(
        self,
        parsed_response: Dict[str, Any],
        inclusion_codes: List[str],
    ) -> Set[str]:
        normalized_lookup = {
            self._normalize_code_token(code): code for code in inclusion_codes
        }
        candidate_texts: List[str] = []
        extracted_value = parsed_response.get("extracted_value")
        if isinstance(extracted_value, str):
            candidate_texts.append(extracted_value)
        justification = parsed_response.get("justification")
        if isinstance(justification, str):
            candidate_texts.append(justification)

        matched: Set[str] = set()
        for text in candidate_texts:
            normalized_text = self._normalize_code_token(text)
            for normalized_code, original_code in normalized_lookup.items():
                escaped = re.escape(normalized_code)
                if re.search(rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])", normalized_text):
                    matched.add(original_code)
        return matched

    @staticmethod
    def _parse_visual_agent_response(response_text: str) -> Dict[str, Any]:
        default_response: Dict[str, Any] = {
            "extracted_value": None,
            "meets_criterion": False,
            "status": "Ambiguous",
            "justification": "",
            "sources": {},
        }
        if not response_text:
            return default_response
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                normalized = dict(default_response)
                normalized.update(parsed)
                return normalized
        except json.JSONDecodeError:
            pass
        return {
            **default_response,
            "justification": response_text,
        }

    @staticmethod
    def _normalize_partial_evidence_status(result: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(result)
        status = str(normalized.get("status", "Ambiguous"))
        if status not in {"Found", "Missing", "Ambiguous"}:
            normalized["status"] = "Ambiguous"
            return normalized

        if status != "Missing" or bool(normalized.get("meets_criterion", False)):
            return normalized

        extracted_value = normalized.get("extracted_value")
        sources = normalized.get("sources", {})
        has_extracted_value = extracted_value not in (None, "", [], {})
        has_sources = (
            isinstance(sources, dict)
            and any(isinstance(v, list) and len(v) > 0 for v in sources.values())
        )
        if has_extracted_value or has_sources:
            normalized["status"] = "Ambiguous"
            justification = str(normalized.get("justification", "")).strip()
            suffix = "Partial relevant evidence exists, but qualifier-level evidence is incomplete."
            normalized["justification"] = f"{justification} {suffix}".strip()
        return normalized


# ---------------------------------------------------------------------------
# Dataiku Code Agent entrypoint
# ---------------------------------------------------------------------------


class QuestionnaireTraverseWithRouterAgent(BaseLLM):
    """Code Agent that evaluates coverage policies via questionnaire traversal and thin routing."""

    VISUAL_AGENT_ID = "7V59eXPp"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chart_agent = VisualChartQueryAgent(self.VISUAL_AGENT_ID)

    def _build_evaluator(self, payload: Dict[str, Any], force_sequential: bool = False) -> QuestionnaireEvaluator:
        parallel_groups = bool(payload.get("parallel_groups", True))
        if force_sequential:
            parallel_groups = False
        return QuestionnaireEvaluator(
            self._chart_agent,
            parallel_groups=parallel_groups,
            max_parallel_groups=int(payload.get("max_parallel_groups", 4)),
            enable_code_prefilter=bool(payload.get("enable_code_prefilter", True)),
            criterion_prefilter_mode=str(payload.get("criterion_prefilter_mode", "prune")),
            prefilter_focus_mode=str(payload.get("prefilter_focus_mode", "hit_only")),
        )

    @staticmethod
    def _normalize_code(code: str) -> str:
        return re.sub(r"\s+", "", code.upper())

    @classmethod
    def _extract_intervention_codes(cls, intervention: Dict[str, Any]) -> Set[str]:
        raw_codes = intervention.get("billing_codes", [])
        if not isinstance(raw_codes, list):
            return set()
        codes: Set[str] = set()
        for item in raw_codes:
            if isinstance(item, str) and item.strip():
                codes.add(cls._normalize_code(item))
            elif isinstance(item, dict):
                code = item.get("code")
                if isinstance(code, str) and code.strip():
                    codes.add(cls._normalize_code(code))
        return codes

    @staticmethod
    def _extract_group_ids(intervention: Dict[str, Any]) -> Set[str]:
        raw_group_ids = intervention.get("group_ids", [])
        if not isinstance(raw_group_ids, list):
            return set()
        return {str(group_id).strip() for group_id in raw_group_ids if str(group_id).strip()}

    def _resolve_policy_scope(
        self,
        parsed_policy: Dict[str, Any],
        requested_billing_code: Optional[str],
        requested_intervention_type: Optional[str],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        questionnaire = parsed_policy.get("questionnaire", [])
        if not isinstance(questionnaire, list):
            questionnaire = []
        interventions = parsed_policy.get("interventions", [])
        if not isinstance(interventions, list):
            interventions = []

        scope_meta: Dict[str, Any] = {
            "requested_billing_code": requested_billing_code,
            "requested_intervention_type": requested_intervention_type,
            "scope_status": "all_groups",
            "selected_intervention": None,
            "candidate_intervention_ids": [],
            "total_top_level_groups": len(questionnaire),
            "scoped_top_level_groups": len(questionnaire),
        }
        if not interventions:
            return parsed_policy, scope_meta

        candidates: List[Dict[str, Any]] = [i for i in interventions if isinstance(i, dict)]
        if requested_billing_code:
            normalized_requested_code = self._normalize_code(requested_billing_code)
            candidates = [
                intervention
                for intervention in candidates
                if normalized_requested_code in self._extract_intervention_codes(intervention)
            ]
        if requested_intervention_type:
            normalized_type = requested_intervention_type.strip().lower()
            candidates = [
                intervention
                for intervention in candidates
                if str(intervention.get("intervention_type", "")).strip().lower() == normalized_type
            ]

        scope_meta["candidate_intervention_ids"] = [
            str(intervention.get("intervention_id", "UNKNOWN")) for intervention in candidates
        ]
        if len(candidates) != 1:
            if not candidates:
                scope_meta["scope_status"] = "no_matching_intervention"
            else:
                scope_meta["scope_status"] = "ambiguous_intervention"
            return parsed_policy, scope_meta

        selected_intervention = candidates[0]
        selected_intervention_id = str(selected_intervention.get("intervention_id", "")).strip()
        selected_group_ids = self._extract_group_ids(selected_intervention)

        scoped_groups: List[Dict[str, Any]] = []
        for group in questionnaire:
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id", "")).strip()
            group_intervention_id = str(group.get("intervention_id", "")).strip()
            if selected_group_ids and group_id in selected_group_ids:
                scoped_groups.append(group)
                continue
            if selected_intervention_id and group_intervention_id == selected_intervention_id:
                scoped_groups.append(group)

        if not scoped_groups:
            scoped_groups = questionnaire
            scope_meta["scope_status"] = "selected_intervention_no_group_map"
        else:
            scope_meta["scope_status"] = "selected_intervention"

        scoped_policy = dict(parsed_policy)
        scoped_policy["questionnaire"] = scoped_groups
        scope_meta["selected_intervention"] = {
            "intervention_id": selected_intervention.get("intervention_id", "UNKNOWN"),
            "intervention_type": selected_intervention.get("intervention_type", "UNKNOWN"),
            "label": selected_intervention.get("label", "UNKNOWN"),
            "billing_codes": selected_intervention.get("billing_codes", []),
            "group_ids": sorted(selected_group_ids),
        }
        scope_meta["scoped_top_level_groups"] = len(scoped_groups)
        return scoped_policy, scope_meta

    @staticmethod
    def _attach_scope_metadata(evaluation: Dict[str, Any], scope_meta: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(evaluation)
        enriched["scope"] = scope_meta
        selected = scope_meta.get("selected_intervention")
        if isinstance(selected, dict):
            enriched["selected_intervention_id"] = selected.get("intervention_id", "UNKNOWN")
            enriched["selected_intervention_type"] = selected.get("intervention_type", "UNKNOWN")
        return enriched

    def process(self, query: Dict[str, Any], settings: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payload = self._extract_payload(query)
            subject_id = payload["subject_id"]
            parsed_policy = payload["parsed_policy"]
            scoped_policy, scope_meta = self._resolve_policy_scope(
                parsed_policy=parsed_policy,
                requested_billing_code=payload.get("requested_billing_code"),
                requested_intervention_type=payload.get("requested_intervention_type"),
            )
            evaluator = self._build_evaluator(payload)
            evaluation = evaluator.evaluate_policy(subject_id=subject_id, parsed_policy=scoped_policy)
            evaluation = self._attach_scope_metadata(evaluation, scope_meta)
            return {"text": json.dumps(evaluation, indent=2)}
        except Exception as exc:
            error_payload = {
                "error": str(exc),
                "expected_input": "Payload containing 'subject_id' (or 'patient_id') and 'parsed_policy'.",
            }
            return {"text": json.dumps(error_payload, indent=2)}

    def process_stream(self, query: Dict[str, Any], settings: Dict[str, Any], trace: Dict[str, Any]):
        try:
            payload = self._extract_payload(query)
            subject_id = payload["subject_id"]
            parsed_policy = payload["parsed_policy"]
            scoped_policy, scope_meta = self._resolve_policy_scope(
                parsed_policy=parsed_policy,
                requested_billing_code=payload.get("requested_billing_code"),
                requested_intervention_type=payload.get("requested_intervention_type"),
            )
            emit_progress_chunks = bool(payload.get("emit_progress_chunks", False))
            if emit_progress_chunks:
                if scope_meta["scope_status"] == "selected_intervention":
                    selected = scope_meta.get("selected_intervention", {})
                    yield {
                        "chunk": {
                            "text": (
                                "Selected intervention "
                                f"{selected.get('intervention_id', 'UNKNOWN')} "
                                f"({selected.get('intervention_type', 'UNKNOWN')}).\n"
                            )
                        }
                    }
                evaluator = self._build_evaluator(payload, force_sequential=True)
                stream = evaluator.evaluate_policy_stream(subject_id=subject_id, parsed_policy=scoped_policy)

                try:
                    while True:
                        text = next(stream)
                        yield {"chunk": {"text": text}}
                except StopIteration as stop:
                    evaluation = stop.value
            else:
                evaluator = self._build_evaluator(payload)
                evaluation = evaluator.evaluate_policy(subject_id=subject_id, parsed_policy=scoped_policy)

            evaluation = self._attach_scope_metadata(evaluation, scope_meta)
            final_text = json.dumps(evaluation, indent=2)
            yield {"chunk": {"text": final_text}}
            yield {"footer": {"text": final_text, "evaluation": evaluation}}
        except Exception as exc:
            error_payload = {
                "error": str(exc),
                "expected_input": "Payload containing 'subject_id' (or 'patient_id') and 'parsed_policy'.",
            }
            error_text = json.dumps(error_payload, indent=2)
            yield {"chunk": {"text": error_text}}
            yield {"footer": {"text": error_text}}

    @staticmethod
    def _extract_payload(query: Dict[str, Any]) -> Dict[str, Any]:
        def _normalize_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if not isinstance(payload, dict):
                return None
            parsed_policy = payload.get("parsed_policy")
            subject_id = payload.get("subject_id") or payload.get("patient_id")
            if isinstance(parsed_policy, dict) and isinstance(subject_id, str) and subject_id:
                emit_progress_chunks = bool(payload.get("emit_progress_chunks", False))
                try:
                    max_parallel_groups = int(payload.get("max_parallel_groups", 4))
                except (TypeError, ValueError):
                    max_parallel_groups = 4
                parallel_groups = bool(payload.get("parallel_groups", not emit_progress_chunks))
                enable_code_prefilter = bool(payload.get("enable_code_prefilter", True))
                raw_prefilter_mode = payload.get("criterion_prefilter_mode", "prune")
                raw_prefilter_focus_mode = payload.get("prefilter_focus_mode", "hit_only")
                requested_billing_code = (
                    payload.get("requested_billing_code")
                    or payload.get("billing_code")
                    or payload.get("hcpcs_code")
                    or payload.get("cpt_code")
                )
                requested_intervention_type = payload.get("requested_intervention_type") or payload.get(
                    "intervention_type"
                )
                return {
                    "subject_id": subject_id,
                    "parsed_policy": parsed_policy,
                    "emit_progress_chunks": emit_progress_chunks,
                    "parallel_groups": parallel_groups,
                    "max_parallel_groups": max(1, max_parallel_groups),
                    "enable_code_prefilter": enable_code_prefilter,
                    "criterion_prefilter_mode": raw_prefilter_mode
                    if isinstance(raw_prefilter_mode, str) and raw_prefilter_mode.strip()
                    else "prune",
                    "prefilter_focus_mode": raw_prefilter_focus_mode
                    if isinstance(raw_prefilter_focus_mode, str) and raw_prefilter_focus_mode.strip()
                    else "hit_only",
                    "requested_billing_code": requested_billing_code
                    if isinstance(requested_billing_code, str) and requested_billing_code.strip()
                    else None,
                    "requested_intervention_type": requested_intervention_type.strip().lower()
                    if isinstance(requested_intervention_type, str) and requested_intervention_type.strip()
                    else None,
                }
            return None

        def _try_parse_json_text(text: str) -> Optional[Any]:
            text = text.strip()
            if not text or text[0] not in "{[":
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None

        def _search(obj: Any, depth: int = 0) -> Optional[Dict[str, Any]]:
            if depth > 6:
                return None
            if isinstance(obj, dict):
                normalized = _normalize_payload(obj)
                if normalized is not None:
                    return normalized
                for value in obj.values():
                    found = _search(value, depth + 1)
                    if found is not None:
                        return found
                return None
            if isinstance(obj, list):
                for item in obj:
                    found = _search(item, depth + 1)
                    if found is not None:
                        return found
                return None
            if isinstance(obj, str):
                parsed = _try_parse_json_text(obj)
                if parsed is None:
                    return None
                return _search(parsed, depth + 1)
            return None

        found_payload = _search(query)
        if found_payload is not None:
            return found_payload
        raise ValueError(
            "Could not locate payload with 'subject_id' (or 'patient_id') and 'parsed_policy' in query/state."
        )


def collect_executed_criteria(eval_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    executed: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any]) -> None:
        if node["node_type"] == "criterion":
            if not node.get("skipped", False):
                executed.append(node)
            return
        for child in node.get("children", []):
            walk(child)

    for group_result in eval_output.get("group_results", []):
        walk(group_result)

    return executed
