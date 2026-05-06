"""Dataiku Code Agent that traverses questionnaires via a visual criterion agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

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


class QuestionnaireEvaluator:
    """Traverses policy/questionnaire nodes with short-circuit logic."""

    def __init__(self, agent: ChartQueryAgent) -> None:
        self.agent = agent

    def evaluate_policy(self, subject_id: str, parsed_policy: Dict[str, Any]) -> Dict[str, Any]:
        questionnaire = parsed_policy.get("questionnaire", [])

        group_results: List[EvalResult] = [self._eval_node(subject_id, group) for group in questionnaire]

        return {
            "document_type": parsed_policy.get("document_type", "UNKNOWN"),
            "policy_id": parsed_policy.get("subject_matter", {}).get("policy_id", "UNKNOWN"),
            "subject_id": subject_id,
            "group_results": [self._to_dict(r) for r in group_results],
            "eligible_groups": [r.node_id for r in group_results if r.satisfied],
        }

    def evaluate_policy_stream(self, subject_id: str, parsed_policy: Dict[str, Any]) -> Iterator[str]:
        questionnaire = parsed_policy.get("questionnaire", [])
        yield f"Starting policy evaluation for {len(questionnaire)} top-level group(s).\n"

        group_results: List[EvalResult] = []
        for index, group in enumerate(questionnaire, start=1):
            yield f"Evaluating group {index}/{len(questionnaire)}: {group.get('id', 'UNKNOWN')}\n"
            group_result = yield from self._eval_node_stream(subject_id, group)
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
            return self._eval_group(subject_id, node, evidence_group_text=evidence_group_text)
        raise ValueError(f"Unknown node_type: {node_type}")

    def _eval_node_stream(
        self,
        subject_id: str,
        node: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
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
            return (yield from self._eval_group_stream(subject_id, node, evidence_group_text=evidence_group_text))
        raise ValueError(f"Unknown node_type: {node_type}")

    def _eval_group(
        self,
        subject_id: str,
        group: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
    ) -> EvalResult:
        operator = group["operator"]
        children = group.get("children", [])
        group_evidence_group_text = group.get("evidence_group_text", evidence_group_text)

        child_results: List[EvalResult] = []

        if operator == "all":
            all_passed = True
            for child in children:
                r = self._eval_node(subject_id, child, evidence_group_text=group_evidence_group_text)
                child_results.append(r)
                if not r.satisfied:
                    all_passed = False
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=all_passed,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        if operator == "any":
            for child in children:
                r = self._eval_node(subject_id, child, evidence_group_text=group_evidence_group_text)
                child_results.append(r)
                if r.satisfied:
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
            none_passed = True
            for child in children:
                r = self._eval_node(subject_id, child, evidence_group_text=group_evidence_group_text)
                child_results.append(r)
                if r.satisfied:
                    none_passed = False
            return EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=none_passed,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )

        if operator.startswith("at_least:"):
            needed = int(operator.split(":", 1)[1])
            passed = 0
            remaining = len(children)

            for child in children:
                r = self._eval_node(subject_id, child, evidence_group_text=group_evidence_group_text)
                child_results.append(r)
                remaining -= 1
                if r.satisfied:
                    passed += 1
                if passed >= needed:
                    return EvalResult(
                        node_id=group["id"],
                        node_type="group",
                        satisfied=True,
                        evidence_group_text=group_evidence_group_text,
                        children=child_results,
                    )
                if passed + remaining < needed:
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
    ) -> Iterator[Any]:
        operator = group["operator"]
        children = group.get("children", [])
        group_evidence_group_text = group.get("evidence_group_text", evidence_group_text)

        yield f"Entering group {group['id']} ({operator})\n"
        child_results: List[EvalResult] = []

        if operator == "all":
            all_passed = True
            for child in children:
                r = yield from self._eval_node_stream(
                    subject_id,
                    child,
                    evidence_group_text=group_evidence_group_text,
                )
                child_results.append(r)
                if not r.satisfied:
                    all_passed = False
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=all_passed,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied={result.satisfied}\n"
            return result

        if operator == "any":
            for child in children:
                r = yield from self._eval_node_stream(
                    subject_id,
                    child,
                    evidence_group_text=group_evidence_group_text,
                )
                child_results.append(r)
                if r.satisfied:
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
            none_passed = True
            for child in children:
                r = yield from self._eval_node_stream(
                    subject_id,
                    child,
                    evidence_group_text=group_evidence_group_text,
                )
                child_results.append(r)
                if r.satisfied:
                    none_passed = False
            result = EvalResult(
                node_id=group["id"],
                node_type="group",
                satisfied=none_passed,
                evidence_group_text=group_evidence_group_text,
                children=child_results,
            )
            yield f"Leaving group {group['id']}: satisfied={result.satisfied}\n"
            return result

        if operator.startswith("at_least:"):
            needed = int(operator.split(":", 1)[1])
            passed = 0
            remaining = len(children)

            for child in children:
                r = yield from self._eval_node_stream(
                    subject_id,
                    child,
                    evidence_group_text=group_evidence_group_text,
                )
                child_results.append(r)
                remaining -= 1
                if r.satisfied:
                    passed += 1
                if passed >= needed:
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

    def _to_dict(self, result: EvalResult) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "node_id": result.node_id,
            "node_type": result.node_type,
            "satisfied": result.satisfied,
        }
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

    # SYSTEM_PROMPT = (
    #     "You are evaluating one policy criterion for a patient. "
    #     "Return a JSON object with keys 'satisfied', 'confidence', 'evidence', and 'rationale'. "
    #     "Treat any missing data as unknown and avoid fabricating details."
    # )

    def __init__(self, visual_agent_id: str) -> None:
        project = dataiku.api_client().get_default_project()
        self._visual_agent = project.get_agent(visual_agent_id).as_llm()

    def evaluate_criterion(
        self,
        subject_id: str,
        criterion: Dict[str, Any],
        evidence_group_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt_payload = {
            "subject_id": subject_id,
            "criterion": criterion,
        }
        if evidence_group_text is not None:
            prompt_payload["evidence_group_text"] = evidence_group_text
        completion = (
            self._visual_agent.new_completion()
            # .with_message(self.SYSTEM_PROMPT, "system")
            .with_message(json.dumps(prompt_payload, indent=2))
        )
        response = completion.execute()
        parsed_response = self._parse_visual_agent_response(response.text)

        return {
            "extracted_value": parsed_response.get("extracted_value"),
            "meets_criterion": bool(parsed_response.get("meets_criterion", False)),
            "status": parsed_response.get("status", "Ambiguous"),
            "justification": parsed_response.get("justification", ""),
            "sources": parsed_response.get("sources", {}),
        }

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


# ---------------------------------------------------------------------------
# Dataiku Code Agent entrypoint
# ---------------------------------------------------------------------------


class QuestionnaireTraverseAgent(BaseLLM):
    """Code Agent that evaluates coverage policies via questionnaire traversal."""

    VISUAL_AGENT_ID = "7V59eXPp"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chart_agent = VisualChartQueryAgent(self.VISUAL_AGENT_ID)

    def process(self, query: Dict[str, Any], settings: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payload = self._extract_payload(query)
            subject_id = payload["subject_id"]
            parsed_policy = payload["parsed_policy"]
            evaluator = QuestionnaireEvaluator(self._chart_agent)
            evaluation = evaluator.evaluate_policy(subject_id=subject_id, parsed_policy=parsed_policy)
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
            emit_progress_chunks = bool(payload.get("emit_progress_chunks", False))
            evaluator = QuestionnaireEvaluator(self._chart_agent)
            stream = evaluator.evaluate_policy_stream(subject_id=subject_id, parsed_policy=parsed_policy)

            try:
                while True:
                    text = next(stream)
                    if emit_progress_chunks:
                        yield {"chunk": {"text": text}}
            except StopIteration as stop:
                evaluation = stop.value

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
            subject_id = payload.get("subject_id", payload.get("patient_id"))
            if isinstance(parsed_policy, dict) and isinstance(subject_id, str) and subject_id:
                emit_progress_chunks = bool(payload.get("emit_progress_chunks", False))
                return {
                    "subject_id": subject_id,
                    "parsed_policy": parsed_policy,
                    "emit_progress_chunks": emit_progress_chunks,
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
            executed.append(node)
            return
        for child in node.get("children", []):
            walk(child)

    for group_result in eval_output.get("group_results", []):
        walk(group_result)

    return executed
