# Prior Auth Assistant Framework

## Goal

Build a clinician-facing prior-authorization assistant that:
- resolves the correct request route from billing code
- narrows to the relevant condition cluster
- pre-fills high-confidence chart-backed answers
- highlights unresolved or conflicting criteria for clinician review
- never drops required clinical eligibility logic

This document is the production reference for the POC.

POC guardrail:
- Don't overcode. This is a POC.

Document role:
- use this file as the high-level product and architecture reference
- use `scripts/schema_v4/screen2_structured_agent_spec.md` as the technical
  Structured Agent build spec
- use the parser prompt as the executable schema contract for
  `policy_master_v4`

## Core Principles

- `policy_master_v4` is the only canonical policy artifact.
- `route_index_v4` is a deterministic routing view derived from `policy_master_v4`.
- Screen 1 is deterministic app/backend logic.
- The Dataiku Structured Visual Agent is the critical orchestration layer for Screen 2.
- Runtime execution uses flattened criterion execution:
  - generate `retrieval_plan_v1`
  - evaluate each criterion once
  - build `criterion_result_map`
  - apply results back to the selected logic tree
- Condition clusters should remain clinician-selectable and disease-specific, including continuation clusters.
- Shared continuation logic should be reused through `logic_profiles`, not by collapsing multiple diseases into one continuation bucket.
- Diagnosis-defined clusters must retain diagnosis-grounded effective logic, whether through a standalone diagnosis criterion or a composite disease-state criterion.

## Webapp Design

### Screen 1: Route and Cluster Selection
The webapp should help the clinician:
- enter patient ID
- select the target policy
- enter or confirm billing code
- choose phase only when the policy explicitly distinguishes it
- answer route guards
- select the relevant disease cluster
- answer cluster-entry guards
- optionally skip a guard answer and continue to review

### Screen 2: Eligibility Review
The webapp should show:
- the exact selected route/phase/cluster scope
- prefilled answers where confidence is high
- unresolved items that need clinician input
- explicit chart conflicts

POC human-review behavior:
- the Structured Agent should present the Screen 2 payload through a managed
  custom Python tool configured with human approval before execution
- the reviewer may approve the payload as-is or edit criterion answers when the
  tool configuration allows editable inputs
- approved or edited answers are returned as the reviewed Screen 2 artifact for
  deterministic downstream Screen 3 generation

Runtime modes:
- `native DSS approval mode`
  - the Structured Agent reaches the human-review tool boundary
  - DSS pauses for managed human approval before the tool executes
  - the tool returns `approved_criterion_answers`
  - backend/helper code deterministically builds Screen 3 from the reviewed
    Screen 2 artifact
- `standard webapp review mode`
  - the webapp renders Screen 2 directly from `screen_2_payload`
  - clinician edits are collected in the same answer-map shape
  - backend submit logic deterministically builds Screen 3
- use the same answer schema in both modes; do not fork the clinician-input model

Recommended UI behavior:
- `status = Found` and `meets_criterion = true`
  - show as chart-supported and satisfied
- `status = Found` and `meets_criterion = false`
  - show as chart-supported and not satisfied
- `status = Missing`
  - show as unresolved and prompt clinician review or manual confirmation
- `status = Ambiguous`
  - show as unresolved and prompt clinician resolution of conflicting or
    incomplete evidence

Current UI-design-mode note:
- the current webapp may still load Screen 2 from a static
  `structured_agent_context.json` while the Structured Agent integration is
  being finalized
- that is acceptable for UI iteration, but it should be treated strictly as a
  development adapter

### Screen 3: Final Review
The webapp should summarize:
- answered criteria
- chart-backed evidence
- unanswered required items
- warnings where clinician answers deviate from chart evidence

### Optional Safety Guardrails
The app may also:
- show other chart-matched clusters under the same route as “also detected in chart”
- include shared/global logic attached through route guards or logic profiles
- allow manual override to add another cluster

## Runtime Architecture

### Component ownership

- `condition_clusters` own route/phase-specific disease scope and grouping.
- `criteria_catalog` owns criterion decomposition, including whether a clinical requirement should be represented as a standalone criterion or a composite criterion.
- `logic_root` owns boolean composition of already-defined criteria and guards.
- Retrieval and adjudication layers should trust parser-defined criterion decomposition rather than re-splitting or re-merging criteria downstream.

### Canonical and Derived Artifacts

#### Canonical
- `policy_master_v4`

#### Derived
- `route_index_v4`
  - built deterministically from `policy_master_v4`
  - used only for Screen 1 routing UX

### Deterministic Backend Layer
Responsibilities:
- load `policy_master_v4`
- derive or load `route_index_v4`
- run the Selection Resolver
- validate route guard answers
- validate cluster-entry guard answers
- build the Screen 1 payload field `scoped_policy_context`
- carry any answered route-guard and cluster-entry-guard clinician responses
  forward as initial `criterion_answers`
- read/write retrieval-plan cache
- provide one adapter for loading patient summary
- provide one adapter for loading Screen 2 from a Structured Agent result

Implementation helpers:
- `scripts/agent_flow/functions/route_index_builder.py`
- `scripts/agent_flow/functions/selection_resolver.py`
- `scripts/agent_flow/functions/python_code_blocks.py`

### Agent Layer

#### 1. Policy Parser Agent
Prompt:
- `scripts/agent_flow/agents/policy_parser_agent_prompt_v4_1.md`

Responsibility:
- parse raw policy text
- emit canonical `policy_master_v4`

Notes:
- run during ingestion or policy refresh
- do not run in the live clinician session unless the artifact is missing
- request routes should follow policy narrative families, not one-code-per-route
- grouped covered billing codes that share the same narrative criteria must stay together in one route

#### 2. Structured Visual Agent
Platform:
- Dataiku DSS 14.5 Structured Visual Agents

Responsibility:
- begin after Screen 1 scope selection
- look up or create `retrieval_plan_v1`
- orchestrate criterion traversal over flattened `plan_items`
- call the Criterion Reasoning Agent once per criterion
- build `criterion_result_map`
- evaluate the selected logic tree
- return the reviewed Screen 2 artifact for deterministic downstream
  transformation

Implementation spec:
- `scripts/schema_v4/screen2_structured_agent_spec.md`

#### 3. Retrieval Planner Agent
Prompt:
- `scripts/agent_flow/agents/retrieval_planner_agent_prompt_v1_1.md`

Responsibility:
- consume `subject_id + scoped_policy_context`
- generate `retrieval_plan_v1` only for the selected scope
- preserve parser-defined criterion decomposition in the plan
- for diagnosis-grounded hybrid disease-state criteria, preserve a diagnosis-code
  structured leg plus a qualifier-resolution leg
- define retrieval planning only, not adjudication

#### 4. Criterion Reasoning Agent
Prompt:
- `scripts/agent_flow/agents/criterion_reasoning_agent_prompt_v1_1.md`

Responsibility:
- evaluate one atomic criterion using chart evidence
- execute hybrid disease-state criteria with diagnosis-grounded structured
  retrieval first when diagnosis codes are available
- return a consistent `status` / `meets_criterion` pair
- provide evidence and justification

## Selection Resolver

Purpose:
- reduce Screen 1 choices to the minimal scope needed before retrieval planning

Inputs:
- `route_index_v4`
- `policy_master_v4`
- `billing_code`
- optional `selected_phase`
- optional `selected_cluster_id`

Behavior:
- resolve billing code -> route
- stop immediately for terminal routes
- prompt for phase only when required
- build the disease-specific cluster shortlist for the selected phase
- hydrate relevant route guards and cluster-entry guards from `policy_master_v4`
- return a planner-facing `scoped_policy_context` payload whose inner runtime object becomes `selected_scope_context` inside the Structured Agent
- preserve any answered route-guard and cluster-entry-guard clinician responses
  so they can seed Screen 2 `criterion_answers`

Implementation boundary:
- `resolve_selection_scope(...)` is the canonical deterministic resolver and the
  source of the Screen 2 agent handoff object
- `build_screen1_payload(...)` is the Screen 1 webapp adapter and should not be
  treated as the canonical source for Structured Agent input preparation

Implementation:
- `scripts/agent_flow/functions/selection_resolver.py`

### `scoped_policy_context` contract

`scoped_policy_context` is the Screen 1 / API payload field name. Its inner object is
persisted in Structured Agent state as `selected_scope_context`.

```json
{
  "policy_id": "string",
  "selected_route_id": "string",
  "selected_route_label": "string",
  "selected_phase": "initial | continuation | other",
  "selected_phase_label": "string",
  "selected_cluster_id": "string",
  "selected_cluster_label": "string",
  "selected_route": {},
  "selected_phase_branch": {},
  "selected_route_guards": [],
  "selected_cluster_summary": {},
  "selected_cluster": {},
  "selected_cluster_entry_guards": [],
  "selected_logic_profiles": [],
  "selected_inherited_diagnosis_clusters": [],
  "effective_diagnosis_code_candidates": ["string"],
  "selected_route_guard_criterion_ids": ["string"],
  "selected_cluster_entry_guard_criterion_ids": ["string"],
  "selected_inherited_diagnosis_criterion_ids": ["string"],
  "selected_cluster_criterion_ids": ["string"],
  "selected_criteria_catalog": []
}
```

Display-label requirements:
- `selected_route_label` should be resolved during Screen 1 from the route label
  defined in the policy artifacts
- `selected_cluster_label` should be resolved during Screen 1 from the selected
  condition cluster label in `policy_master_v4`
- `selected_phase_label` may be produced deterministically from
  `selected_phase` (`Initial`, `Continuation`, `Other`)
- these display fields should be carried into `selected_scope_context` so Screen
  2 does not need to re-join `policy_master_v4` or `route_index_v4` just to
  render clinician-friendly context text

Screen 1 handoff contract:
- Screen 1 should also return an optional top-level `criterion_answers` object
  alongside `scoped_policy_context`
- those answers seed Screen 2 for selected route guards and selected
  cluster-entry guards
- skipped Screen 1 questions remain unanswered; they should not be coerced to
  `false`
- by the time Screen 2 builds `criterion_ui_map`, Screen 1 answers and Screen 2
  answers are treated uniformly as clinician input
- `criterion_answers` is the working clinician-input state keyed by
  `criterion_id`
- after human approval or webapp submit, the approved snapshot should be carried
  as `approved_criterion_answers`

Patient summary note:
- patient demographics should not be added to the Structured Agent payload just
  for Screen 2 rendering
- the webapp/backend should load a small `patient_summary` object directly from
  the DSS `Patient` dataset using:
  - `subject_id`
  - `gender`
  - `birth_date`

Deployment adapter note:
- keep one backend adapter responsible for patient-summary loading so the UI
  contract remains stable across fixture mode and deployment mode
- keep one backend adapter responsible for obtaining Screen 2 from Structured
  Agent output so the UI contract remains stable across static-artifact mode and
  live agent mode
- in the current DSS deployment, the backend resolves the Structured Agent from
  the active/default DSS project context rather than hard-coding a project key
- the current deployed project key is `DEMO_PRIOR_AUTH_AGENT`; the standard
  webapp and Structured Agent are expected to live in that same project context
- in deployment mode, Screen 1 should hand `selected_scope_context` to the
  Dataiku Structured Agent, which should generate `structured_agent_context`
  and expose `screen_2_payload` for Screen 2 rendering
  - `birth_date`

Critical assumptions:
- continuation shortlist entries should remain disease-specific
- diagnosis metadata alone is not sufficient for downstream planning
- if a cluster depends on diagnosis confirmation, the selected scope must still include diagnosis-grounded effective logic, which may be represented by either a standalone diagnosis criterion or a composite disease-state criterion

## Screen Ownership

### Screen 1: Deterministic backend
Backend should:
1. load `policy_master_v4`
2. derive or load `route_index_v4`
3. resolve route from billing code
4. handle terminal routes immediately
5. prompt for phase only when required
6. return route guards
7. return disease-specific cluster shortlist
8. return cluster-entry guards for the chosen cluster
9. build `scoped_policy_context` only after the selected scope is valid
10. persist the inner scoped object in Structured Agent state as `selected_scope_context`
11. return any answered route-guard and cluster-entry-guard responses as
    initial `criterion_answers`

### Screen 2: Structured Agent
Structured Agent should:
1. receive `subject_id + scoped_policy_context`
2. load or generate `retrieval_plan_v1`
3. iterate over flattened `plan_items`
4. call Criterion Reasoning Agent once per unique criterion
5. build `criterion_result_map`
6. build a deterministic webapp-facing `criterion_ui_map`
7. apply results to the selected logic tree
8. build the Screen 2 review payload
9. request human approval through the managed Screen 2 review tool
10. emit the reviewed Screen 2 artifact as the stable downstream handoff object

Conflict handling rule:
- `criterion_ui_map` should compare chart-backed `criterion_result_map` against
  any clinician input already captured in Screen 1 or entered later in Screen 2
- disagreement on a chart-backed `Found` result should surface as a conflict,
  not trigger a second reasoning pass

Implementation note:
- persist the inner selected scope object in agent state as
  `selected_scope_context`
- reserve `scoped_policy_context` for the Screen 1 / API payload field name

### Screen 3: Deterministic backend/webapp layer
Backend/webapp should:
1. consume the approved Screen 2 review result
2. merge clinician answers with chart-backed results
3. recompute completeness and conflicts
4. return final review payload

Approval boundary:
- the Screen 2 review tool is the POC human-in-the-loop boundary
- it should be configured with `Enforce human approval before making tool call`
- the post-approval path should stay deterministic and should not call the
  Retrieval Planner Agent, Criterion Reasoning Agent, or chart tools again

## Two-Tier Persistence Model

### Tier 1: `policy_artifacts`
Purpose:
- shared policy artifact store

Recommended columns:
- `policy_id`
- `schema_version`
- `policy_effective_date`
- `last_review_date`
- `next_review_date`
- `artifact_created_datetime`
- `policy_source_hash`
- `document_type`
- `title`
- `policy_master_v4`
- `route_index_v4`

Notes:
- `policy_master_v4` is canonical
- `route_index_v4` is derived from `policy_master_v4`
- one active row per `policy_id + schema_version + policy_source_hash`

### Tier 2: `retrieval_plan_cache_v1`
Purpose:
- deterministic runtime planning cache

Recommended columns:
- `policy_id`
- `schema_version`
- `planner_version`
- optional `semantic_model_version`
- `selected_route_id`
- `selected_phase`
- `selected_cluster_id`
- `plan_created_datetime`
- `cache_key`
- `retrieval_plan_v1`

Notes:
- cache key should uniquely represent selected route/phase/cluster scope
- one active row per `policy_id + planner_version + semantic_model_version + selected_route_id + selected_phase + selected_cluster_id`

### Optional: `prior_auth_session_state`
Use only if the webapp must support resume/reload.

## Logic Evaluation Rules

The evaluator runs after `criterion_result_map` is complete.

`criterion_result_map` design rule:
- `extracted_value` should contain only compact normalized result content useful
  for prefill or downstream logic
- raw structured rows and note excerpts belong in `sources`
- `sources.structured` should include all relevant returned EHR records rather
  than a single aggregated source item
- `sources.notes` should use clinician-reviewable excerpts plus a brief
  explanation of why each excerpt matters
- each note excerpt should be a focused local passage, not the full retrieved
  chunk
- reasoning belongs in `justification`

### Criterion normalization
- `Found` + `meets_criterion=true` -> satisfied
- `Found` + `meets_criterion=false` -> not satisfied
- `Missing` + `meets_criterion=false` -> unresolved and should prompt clinician follow-up
- `Ambiguous` + `meets_criterion=false` -> unresolved
- `Unreviewed` -> unresolved

Contract:
- `status` is the chart-evidence resolution field used to decide whether the
  webapp should prompt the clinician
- `meets_criterion` is the pass/fail adjudication field and may be `true` only
  when `status = Found`
- for exclusionary criteria, chart silence is not enough to satisfy the
  criterion; documented absence of the disqualifying fact is required
- if that documented absence is not found, return `Missing` +
  `meets_criterion=false`, and let the webapp prompt for clinician review

### Operators
- `all`
  - satisfied if all children are satisfied
  - not satisfied if any child is not satisfied
  - unresolved otherwise
- `any`
  - satisfied if any child is satisfied
  - not satisfied if all children are not satisfied
  - unresolved otherwise
- `none`
  - satisfied if all children are not satisfied
  - not satisfied if any child is satisfied
  - unresolved otherwise
- `at_least:n`
  - satisfied if satisfied-child count reaches `n`
  - not satisfied if even all unresolved children could not reach `n`
  - unresolved otherwise

POC rule:
- repeated `criterion_ref` nodes should be evaluated once and reused everywhere in the logic tree
- `evaluate_logic_tree(selected_scope_context, criterion_result_map)` derives its
  primary and supporting logic roots directly from `selected_scope_context`,
  including:
  - `selected_cluster.logic_root`
  - `selected_route_guards[].logic_root`
  - `selected_cluster_entry_guards[].logic_root`
  - `selected_logic_profiles[].logic_root`
  - `selected_inherited_diagnosis_clusters[].logic_root`

## Screen 2 Merge Model

Use three per-criterion layers:
- clinician input
- chart-backed result
- UI resolution

Canonical backend artifact:
- `criterion_result_map`

Derived webapp-facing artifact:
- `criterion_ui_map`

Recommended shape:

```json
{
  "CRITERION_ID": {
    "criterion_id": "string",
    "criterion_kind": "route_guard | cluster_entry_guard | cluster_criterion",
    "prompt": "string",
    "required": true,
    "clinician_input": {
      "answer": null,
      "value": null,
      "comment": null,
      "override_prefill": false,
      "answered": false
    },
    "chart_result": {
      "status": "Found | Missing | Ambiguous | Unreviewed",
      "meets_criterion": false,
      "extracted_value": null,
      "justification": null,
      "sources": {
        "structured": [],
        "notes": []
      }
    },
    "ui_resolution": {
      "display_state": "satisfied | not_satisfied | needs_clinician | conflict | unanswered",
      "prefill_value": null,
      "use_chart_as_prefill": false,
      "conflict_flag": false,
      "conflict_reason": null,
      "final_answer": null,
      "final_source": "chart | clinician | unresolved | system"
    }
  }
}
```

Rules:
- `chart_result` mirrors the backend-produced `criterion_result_map`
- `clinician_input` mirrors the latest user answer, whether it was first
  captured in Screen 1 or entered in Screen 2
- `ui_resolution` is deterministic frontend/backend merge logic, not LLM output

Recommended merge behavior:
- `Found + meets_criterion=true`
  - can prefill as satisfied
- `Found + meets_criterion=false`
  - can prefill as not satisfied
- `Missing`
  - do not auto-fail in the UI
  - show as `needs_clinician`
- `Ambiguous`
  - show as `needs_clinician`
- `Unreviewed`
  - show as `unanswered` until processed
- clinician/chart disagreement on a chart-backed `Found` result
  - show as `conflict`

Recommended presentation order:
- route guards first
- cluster-entry guards second
- cluster criteria third

This preserves a staged clinician workflow while keeping the backend execution
flattened and uniform.

## Work Plan

1. Maintain parser ingestion around canonical `policy_master_v4`
2. Derive `route_index_v4` deterministically from the master file
3. Keep Screen 1 deterministic in backend code
4. Use Structured Agent orchestration only after scope selection
5. Cache `retrieval_plan_v1` by selected route/phase/cluster
6. Validate representative policies:
   - `0059`
   - `0314`
   - `0655`
   - `0685`

## POC Success Criteria

The POC is successful if:
- Screen 1 shows the right route, phase, and disease-specific cluster choices
- required guards appear at the right step
- retrieval planning only runs on the selected scope
- each criterion is evaluated once
- the final logic evaluation is consistent with the policy logic
- no required clinical diagnosis criterion is lost in grouped or inherited continuation scenarios

## Reference Files

- `scripts/agent_flow/agents/policy_parser_agent_prompt_v4_1.md`
- `scripts/schema_v4/screen2_structured_agent_spec.md`
- `scripts/schema_v4/screen2_human_review_tool_spec.md`
- `scripts/agent_flow/agents/retrieval_planner_agent_prompt_v1_1.md`
- `scripts/agent_flow/functions/route_index_builder.py`
- `scripts/agent_flow/functions/selection_resolver.py`
- `scripts/agent_flow/functions/python_code_blocks.py`
- `scripts/agent_flow/functions/logic_tree_evaluator.py`
- `scripts/agent_flow/functions/evaluator_regression.py`
- `scripts/agent_flow/agents/criterion_reasoning_agent_prompt_v1_1.md`
- `scripts/schema_v4/prior-auth_assistant_flowchart.md`
