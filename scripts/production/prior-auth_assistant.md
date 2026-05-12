# Prior Auth Assistant Framework

## Goal

Build a clinician-facing prior-authorization assistant that:
- resolves the correct request route from billing code
- narrows to the relevant condition cluster
- pre-fills high-confidence chart-backed answers
- highlights unresolved or conflicting criteria for clinician review
- never drops required clinical eligibility logic

This document is the production reference for the POC.

## Core Principles

- `policy_master_v4` is the only canonical policy artifact.
- `route_index_v4` is a deterministic routing view derived from `policy_master_v4`.
- Screen 1 is deterministic app/backend logic.
- The Dataiku Structured Visual Agent is the critical orchestration layer for Screen 2 and Screen 3.
- Runtime execution uses flattened criterion execution:
  - generate `retrieval_plan_v1`
  - evaluate each criterion once
  - build `criterion_result_map`
  - apply results back to the selected logic tree
- Condition clusters should remain clinician-selectable and disease-specific, including continuation clusters.
- Shared continuation logic should be reused through `logic_profiles`, not by collapsing multiple diseases into one continuation bucket.
- Diagnosis-defined clusters must expose explicit executable diagnosis criteria.

## Webapp Design

### Screen 1: Route and Cluster Selection
The webapp should help the clinician:
- enter or confirm billing code
- choose phase only when the policy explicitly distinguishes it
- answer route guards
- select the relevant disease cluster
- answer cluster-entry guards

### Screen 2: Eligibility Review
The webapp should show:
- the exact selected route/phase/cluster scope
- prefilled answers where confidence is high
- unresolved items that need clinician input
- explicit chart conflicts

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
- build `scoped_policy_context`
- read/write retrieval-plan cache

Implementation helpers:
- `scripts/production/functions/route_index_builder.py`
- `scripts/production/functions/selection_resolver.py`
- `scripts/production/functions/logic_tree_evaluator.py`

### Agent Layer

#### 1. Policy Parser Agent
Prompt:
- `scripts/production/agents/policy_parser_agent_prompt_v4.md`

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
- return Screen 2 and Screen 3 payloads

Implementation spec:
- `scripts/production/agents/screen2_structured_agent_spec.md`

#### 3. Retrieval Planner Agent
Prompt:
- `scripts/production/agents/retrieval_planner_agent_prompt_v1.md`

Responsibility:
- consume `subject_id + scoped_policy_context`
- generate `retrieval_plan_v1` only for the selected scope
- define retrieval planning only, not adjudication

#### 4. Criterion Reasoning Agent
Prompt:
- `scripts/production/agents/criterion_reasoning_agent_prompt.md`

Responsibility:
- evaluate one atomic criterion using chart evidence
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
- return a planner-facing `scoped_policy_context`

Implementation:
- `scripts/production/functions/selection_resolver.py`

### `scoped_policy_context` contract

```json
{
  "policy_id": "string",
  "selected_route_id": "string",
  "selected_route_label": "string",
  "selected_phase": "initial | continuation | other",
  "selected_cluster_id": "string",
  "selected_cluster_label": "string",
  "effective_diagnosis_code_candidates": ["string"],
  "selected_logic_profile_ids": ["string"],
  "selected_route_guard_criterion_ids": ["string"],
  "selected_cluster_entry_guard_criterion_ids": ["string"],
  "selected_cluster_criterion_ids": ["string"],
  "selected_criteria_catalog": []
}
```

Critical assumptions:
- continuation shortlist entries should remain disease-specific
- diagnosis metadata alone is not sufficient for downstream planning
- if a cluster depends on diagnosis confirmation, the required diagnosis criterion must appear in `selected_criteria_catalog`

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

### Screen 2: Structured Agent
Structured Agent should:
1. receive `subject_id + scoped_policy_context`
2. load or generate `retrieval_plan_v1`
3. iterate over flattened `plan_items`
4. call Criterion Reasoning Agent once per unique criterion
5. build `criterion_result_map`
6. apply results to the selected logic tree
7. return prefills, unresolved items, conflicts, and logic evaluation

### Screen 3: Structured Agent
Structured Agent should:
1. merge clinician answers with chart-backed results
2. recompute completeness and conflicts
3. return final review payload

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

- `scripts/production/agents/policy_parser_agent_prompt_v4.md`
- `scripts/production/agents/screen2_structured_agent_spec.md`
- `scripts/production/agents/retrieval_planner_agent_prompt_v1.md`
- `scripts/production/functions/route_index_builder.py`
- `scripts/production/functions/selection_resolver.py`
- `scripts/production/functions/logic_tree_evaluator.py`
- `scripts/production/functions/evaluator_regression.py`
- `scripts/production/agents/criterion_reasoning_agent_prompt.md`
- `scripts/production/prior-auth_assistant_flowchart.md`
