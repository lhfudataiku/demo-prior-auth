# Prior Auth Assistant Framework

## Goal

Build a clinician-facing prior authorization assistant that:
- resolves the correct request route from billing code
- narrows to the relevant clinical condition cluster
- pre-fills high-confidence answers from the EHR
- highlights unresolved or conflicting criteria for clinician review
- preserves safety by never dropping required clinical eligibility logic

This document is the reference framework for the POC.

## Webapp Design

### Screen 1: Route and Cluster Selection
The webapp should help the clinician:
- enter or confirm billing code
- choose phase only when the policy explicitly distinguishes it (`initial`, `continuation`, or `other`)
- complete route guard logic checks
- select the relevant disease cluster
- complete cluster-entry guard logic checks

### Screen 2: Eligibility Review
The webapp should show the exact eligibility cluster for the selected route and phase:
- prefilled answers from EHR where confidence is high
- unresolved items highlighted for clinician input
- chart conflicts shown explicitly

### Screen 3: Final Review
The webapp should summarize:
- answered criteria
- chart-backed evidence
- unanswered required items
- warnings where clinician answers deviate from chart evidence

## Optional Safety Guardrails

To reduce missed criteria and unsafe routing, the app may also:
- show any other chart-matched clusters under the same intervention as "also detected in chart"
- include shared/global criteria tied to the selected route or cluster logic profile
- allow manual override to add another cluster when the clinician believes the intended condition is broader or different than the chart suggestion

## Two-Tier Persistence Model

### Tier 1: Canonical Policy Store
Persist to Dataiku dataset:
- `policy_artifacts`

Purpose:
- shared source of truth for parsed policy artifacts
- versioned and reusable across users and sessions

Suggested keys:
- `policy_id`
- `schema_version`
- `policy_effective_date`
- `last_review_date`
- `next_review_date`
- `artifact_created_datetime`
- optional `policy_source_hash`
- `policy_master_v4`
- `route_index_v4`

### Tier 2: Runtime Planning Cache
Persist to Dataiku dataset:
- `retrieval_plan_cache_v1`
- optional shortlist cache later if needed

Purpose:
- deterministic cache for selected route/phase/cluster planning
- avoid regenerating retrieval plans unnecessarily

Suggested keys:
- `policy_id`
- `selected_route_id`
- `selected_phase`
- `selected_cluster_id`
- `planner_version`
- optional `semantic_model_version`
- `plan_created_datetime`
- `retrieval_plan_v1`

## Core Agents and Responsibilities

### 1. Policy Parser Agent
Prompt:
- `scripts/production/agents/policy_parser_agent_prompt_v4.md`

Responsibility:
- parse raw policy text
- generate `policy_master_v4`
- generate `route_index_v4`

Output destination:
- Tier 1 canonical policy store (`policy_artifacts`)

Notes:
- this should run during ingestion or policy refresh
- it should not be part of the live clinician session unless the policy artifact is missing

### 2. Structured Visual Agent (Session Orchestrator)
Platform:
- Dataiku DSS 14.5 Structured Visual Agents

Responsibility:
- act as the critical orchestration layer after Screen 1 scope selection
- look up and write retrieval-plan cache in Tier 2
- call the Retrieval Planner Agent with `scoped_policy_context`
- orchestrate criterion traversal and trigger the Criterion Reasoning Agent
- aggregate criterion results into Screen 2 and Screen 3 payloads

This is the main agent-powered orchestration layer for the application.

### 3. Selection Resolver
Responsibility:
- use `route_index_v4` as the Screen 1 routing view
- deterministically resolve:
  - billing code -> request route
  - route -> phase requirement
  - route + phase -> relevant cluster shortlist
  - selected cluster -> relevant cluster-entry guards
- return only the minimal selected scope needed before retrieval planning

Design principle:
- this layer should be hard-coded and deterministic
- it should reduce the payload before calling the retrieval planner

Implementation:
- `functions/selection_resolver.py`

Notes:
- prefer `route_index_v4` for route/phase/cluster selection UX
- use `policy_master_v4` only to hydrate the full guard objects after IDs are selected
- do not call the retrieval planner until:
  - route is resolved
  - phase is resolved
  - route guards are answered
  - cluster is selected
  - cluster-entry guards are answered

Resolver output contract:

```json
{
  "status": "ok | blocked",
  "next_action": "collect_phase | collect_cluster | collect_cluster_guards | proceed_screen_2 | stop",
  "route_summary": {},
  "cluster_shortlist": [],
  "route_guard_ids": ["string"],
  "cluster_entry_guard_ids": ["string"],
  "scoped_policy_context": {
    "policy_id": "string",
    "selected_route_id": "string",
    "selected_phase": "initial | continuation | other",
    "selected_cluster_id": "string",
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
    "selected_cluster_criterion_ids": ["string"],
    "selected_criteria_catalog": []
  }
}
```

### 4. Retrieval Planner Agent
Prompt:
- `scripts/production/agents/retrieval_planner_agent_prompt_v1.md`

Responsibility:
- consume `scoped_policy_context` from the Selection Resolver
- generate `retrieval_plan_v1` only for the minimal selected scope
- restore EHR planning structures such as:
  - `execution_hints`
  - `ehr_query_fragment`
  - `time_constraint`
  - `route_plan`

Output destination:
- Tier 2 runtime planning cache (`retrieval_plan_cache_v1`)

### 5. Criterion Reasoning Agent
Prompt:
- `scripts/criterion_reasoning_agent_prompt.md`

Responsibility:
- evaluate one atomic criterion using patient-scoped EHR evidence
- return:
  - `Found`
  - `Missing`
  - `Ambiguous`
- provide extracted evidence and justification

### 6. Cluster Executor
Responsibility:
- replace the old questionnaire-wide traversal runtime
- evaluate only the selected route/phase/cluster scope
- apply route and cluster-entry dependencies correctly
- aggregate:
  - prefills
  - unresolved items
  - chart conflicts
  - completion status

Important architectural direction:
- do not use full questionnaire traversal as the main runtime engine
- use V4-native selected-cluster execution instead

## Current Backend Mapping

### Aligned Components
- `scripts/production/agents/policy_parser_agent_prompt_v4.md`
- `functions/selection_resolver.py`
- `scripts/production/agents/retrieval_planner_agent_prompt_v1.md`
- `scripts/criterion_reasoning_agent_prompt.md`

### Component To Replace / Refactor
- `scripts/questionnaire_traverse_w_router_code_agent.py`

Reason:
- it is still based on the older `parsed_policy["questionnaire"]` traversal model
- the V4 runtime should be driven by:
  - request route
  - phase branch
  - route guards
  - cluster-entry guards
  - selected condition cluster
  - logic profiles
  - criteria catalog

## Structured Agent and Webapp Interaction

### Screen 1 Flow: Route Confirmation
Webapp sends:
- `policy_id`
- `subject_id`
- `billing_code`
- optional `phase`

Deterministic app/backend logic should:
1. load `policy_master_v4` and `route_index_v4` from Tier 1
2. use the Selection Resolver to resolve request route from billing code via `route_index_v4`
3. if the route is terminal, return an immediate stop response
4. if phase is required and missing, return a phase prompt
5. determine the correct phase branch
6. build the disease cluster shortlist from that phase branch
7. optionally rank clusters using chart diagnosis evidence
8. hydrate selected IDs against `policy_master_v4` to materialize applicable route guards, cluster-entry guards, logic profiles, and referenced criteria objects
9. return a Screen 1 payload containing:
   - route summary
   - phase requirement
   - route guard prompts
   - cluster shortlist
   - also-detected-in-chart suggestions
   - cluster-entry guards for the selected cluster when applicable

Webapp renders:
- code
- initial/continuation only if needed
- route guard logic check
- disease cluster selection
- cluster-entry guard logic check

Worked example (`0059`):
- billing code `A4614`
- Selection Resolver finds route `RR_0059_PFM_SPACER` from `route_index_v4`
- route is non-terminal and `phase_prompt_required = false`
- default phase is `other`
- route guard IDs = `RG_0059_DEVICE_TYPE`
- cluster shortlist =
  - `CL_0059_J20_J21`
  - `CL_0059_J40_J47`
  - `CL_0059_J67`
- after clinician selects one cluster, the app hydrates:
  - route guard definition from `policy_master_v4.route_guards`
  - cluster-entry guard definitions from `policy_master_v4.cluster_entry_guards`
  - selected cluster object from `policy_master_v4.condition_clusters`
  - referenced criteria objects from `policy_master_v4.criteria_catalog`
- only after these selections and guard answers does the runtime call the retrieval planner with `scoped_policy_context`

### Screen 1 Submit
Webapp sends:
- selected route
- selected phase
- route guard answers
- selected cluster
- cluster-entry guard answers

Deterministic app/backend logic should:
1. use the Selection Resolver to reduce the request to the final selected route/phase/cluster scope
2. validate route guards
3. validate cluster-entry guards
4. if blocked, return warning or stop payload
5. look up Tier 2 retrieval-plan cache
6. if cache miss, call the Structured Visual Agent with `subject_id + scoped_policy_context`
7. persist any returned `retrieval_plan_v1`
8. move the session to Screen 2

### Screen 2 Flow: Eligibility Review
Structured Visual Agent should:
1. receive `subject_id + scoped_policy_context`
2. generate or load the retrieval plan for that scoped policy context
3. run the selected-cluster executor
4. evaluate only relevant cluster criteria and applicable shared logic
5. delegate atomic adjudication to the Criterion Reasoning Agent
6. aggregate outputs into:
   - high-confidence prefills
   - unresolved items
   - explicit chart conflicts
   - optional additional cluster suggestions

Webapp renders:
- prefilled answers
- unresolved items highlighted
- chart conflicts explicitly shown

### Screen 2 Submit
Webapp sends:
- clinician-entered answers
- overrides to prefills
- optional manual add-another-cluster action

Structured Visual Agent should:
1. merge clinician answers with chart-backed evidence
2. recompute completeness and conflict flags
3. build final review state

### Screen 3 Flow: Final Review
Structured Visual Agent returns:
- answered criteria
- chart-backed evidence
- unanswered required items
- warnings where clinician answers deviate from chart evidence
- optional also-detected clusters not selected

Webapp renders the final review and submission-ready summary.

## Recommended Dataiku Structured Agent Pattern

Use one Structured Visual Agent as the main runtime controller for Screen 2 and Screen 3.

Recommended responsibilities:
- `State` for scoped policy context, retrieval plan, and criterion results
- `Routing` for post-selection execution branching and failure handling
- `Delegate` blocks for:
  - retrieval planner
  - criterion reasoning
- `For Each` or `Parallel` only where criterion-level work is independent

Design principle:
- keep Screen 1 deterministic in app/backend code
- use the Structured Agent where orchestration and repeated delegated reasoning add value

## Work Plan

### 1. Define Dataset Contracts
Create Tier 1 and Tier 2 dataset schemas.

Tier 1 should store:
- `policy_id`
- `schema_version`
- `policy_effective_date`
- `last_review_date`
- `next_review_date`
- `artifact_created_datetime`
- optional `policy_source_hash`
- `policy_master_v4`
- `route_index_v4`

Tier 2 should store:
- `policy_id`
- `selected_route_id`
- `selected_phase`
- `selected_cluster_id`
- `planner_version`
- optional `semantic_model_version`
- `retrieval_plan_v1`

### 2. Build Policy Ingestion
- parse policy text with the V4 parser agent
- validate artifact shape
- persist canonical artifacts to Tier 1

### 3. Build Deterministic Screen 1 Backend Logic
Implement the non-agent backend flow for:
- route resolution
- terminal route handling
- phase prompting
- guard prompting
- scoped policy context construction
- cache lookup before agent execution

### 4. Build the Structured Visual Agent Orchestrator
Implement the agent flow for:
- retrieval planning
- criterion traversal
- criterion reasoning delegation
- Screen 2 payload aggregation
- Screen 3 final review aggregation

### 5. Replace Questionnaire-Wide Traversal
Refactor away from the old runtime traversal model and build a V4-native cluster executor that evaluates only:
- selected route
- selected phase
- selected cluster

### 6. Wire Retrieval-Plan Caching
- lookup cache before planning
- regenerate on miss
- invalidate on planner version or policy refresh

### 7. Define Screen Payload Contracts
Create explicit JSON request/response contracts for:
- Screen 1
- Screen 2
- Screen 3

### 8. Run End-to-End Validation
Validate representative policies:
- `q0059` for simple route flow
- `q0685` for inheritance and shared continuation logic
- `q0314` for multi-phase guard-heavy flow

### 9. Defer Non-POC Optimizations
Do not optimize further unless it blocks user experience.
Examples to defer:
- aggressive cluster deduplication refinement
- advanced caching beyond retrieval plan reuse
- broader policy families outside the POC scope

## Concrete Dataset Schemas

These schemas are intentionally simple for the POC. Each dataset row stores one artifact keyed by deterministic identifiers.

### Dataset 1: `policy_artifacts`

Purpose:
- canonical shared store for parser outputs

Recommended columns:

| Column | Type | Notes |
| --- | --- | --- |
| `policy_id` | string | policy identifier such as `0059`, `0314`, `0685` |
| `schema_version` | string | expected `prior_auth_v4` |
| `policy_effective_date` | string | policy effective date when present |
| `last_review_date` | string | last review date when present |
| `next_review_date` | string | next scheduled review date when present |
| `artifact_created_datetime` | string | artifact creation datetime |
| `policy_source_hash` | string | hash of source markdown/text used for parsing |
| `document_type` | string | e.g. `COVERAGE_POLICY` |
| `title` | string | policy title if available |
| `policy_master_v4` | string / JSON | full canonical artifact |
| `route_index_v4` | string / JSON | webapp-facing route index |

Notes:
- `policy_effective_date`, `last_review_date`, and `next_review_date` should be extracted from the parser artifact when present.
- `artifact_created_datetime` should be assigned by the ingestion pipeline or dataset write step.

Primary uniqueness expectation:
- one active row per `policy_id + schema_version + policy_source_hash`

### Dataset 2: `retrieval_plan_cache_v1`

Purpose:
- deterministic runtime cache for selected route/phase/cluster planning

Recommended columns:

| Column | Type | Notes |
| --- | --- | --- |
| `policy_id` | string | foreign key to policy artifact |
| `schema_version` | string | expected parser schema version |
| `planner_version` | string | retrieval planner version |
| `semantic_model_version` | string | optional EHR semantic layer version |
| `selected_route_id` | string | chosen request route |
| `selected_phase` | string | `initial`, `continuation`, or `other` |
| `selected_cluster_id` | string | chosen condition cluster |
| `plan_created_datetime` | string | plan creation datetime |
| `cache_key` | string | deterministic composite key or hash |
| `retrieval_plan_v1` | string / JSON | full retrieval plan artifact |

Notes:
- `planner_version` and `semantic_model_version` are cache-management fields owned by the orchestrator.
- `plan_created_datetime` should be assigned when the cache row is written.

Primary uniqueness expectation:
- one active row per `policy_id + planner_version + semantic_model_version + selected_route_id + selected_phase + selected_cluster_id`

### Optional Dataset 3: `prior_auth_session_state`

Purpose:
- lightweight persistence for in-progress webapp sessions

Recommended columns:

| Column | Type | Notes |
| --- | --- | --- |
| `session_id` | string | unique webapp session identifier |
| `subject_id` | string | patient identifier |
| `policy_id` | string | selected policy |
| `current_screen` | string | `screen_1`, `screen_2`, `screen_3` |
| `session_state_json` | string / JSON | full orchestrator state snapshot |
| `updated_at_utc` | string | ISO timestamp |

This is optional, but helpful if the app needs resume/reload behavior.

## Screen Payload Contracts

The webapp should treat the Structured Visual Agent as a JSON backend. Each screen submit sends a typed payload and receives a typed payload.

### Shared Envelope

All requests should include:

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_1 | screen_2 | screen_3",
  "payload": {}
}
```

All responses should include:

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_1 | screen_2 | screen_3",
  "status": "ok | warning | blocked | complete | error",
  "payload": {},
  "messages": [
    {
      "level": "info | warning | error",
      "text": "string"
    }
  ]
}
```

### Screen 1 Contracts

#### Screen 1 Request

Used by deterministic app/backend logic for initial route resolution and for resubmission after clinician input.

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_1",
  "payload": {
    "billing_code": "string",
    "selected_phase": "initial | continuation | other | null",
    "selected_route_id": "string | null",
    "route_guard_answers": {
      "GUARD_ID": {
        "answer": true,
        "comment": "optional string"
      }
    },
    "selected_cluster_id": "string | null",
    "cluster_entry_guard_answers": {
      "GUARD_ID": {
        "answer": true,
        "comment": "optional string"
      }
    }
  }
}
```

#### Screen 1 Response

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_1",
  "status": "ok | warning | blocked | error",
  "payload": {
    "route_resolution": {
      "selected_route_id": "string | null",
      "route_label": "string | null",
      "coverage_status": "covered | not_covered | investigational | null",
      "terminal_disposition": "continue | stop_not_covered | stop_investigational | null"
    },
    "phase": {
      "phase_prompt_required": true,
      "allowed_phases": ["initial", "continuation"],
      "selected_phase": "initial | continuation | other | null"
    },
    "route_guards": [
      {
        "guard_id": "string",
        "label": "string",
        "prompt": "string",
        "required": true
      }
    ],
    "cluster_shortlist": [
      {
        "cluster_id": "string",
        "condition_label": "string",
        "diagnosis_code_candidates": ["string"],
        "chart_match_rank": 1,
        "chart_match_reason": "string | null"
      }
    ],
    "also_detected_clusters": [
      {
        "cluster_id": "string",
        "condition_label": "string",
        "chart_match_reason": "string"
      }
    ],
    "cluster_entry_guards": [
      {
        "guard_id": "string",
        "label": "string",
        "prompt": "string",
        "required": true
      }
    ],
    "next_action": "collect_phase | collect_route_guards | collect_cluster | collect_cluster_guards | proceed_screen_2 | stop"
  },
  "messages": []
}
```

### Screen 2 Contracts

#### Screen 2 Request

Used after Screen 1 is completed and whenever the clinician edits answers. This request is handled by the Structured Visual Agent.

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_2",
  "payload": {
    "selected_route_id": "string",
    "selected_phase": "initial | continuation | other",
    "selected_cluster_id": "string",
    "include_additional_cluster_ids": ["string"],
    "criterion_answers": {
      "CRITERION_ID": {
        "answer": true,
        "value": "optional typed value",
        "comment": "optional string",
        "override_prefill": false
      }
    }
  }
}
```

#### Screen 2 Response

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_2",
  "status": "ok | warning | blocked | error",
  "payload": {
    "selected_scope": {
      "selected_route_id": "string",
      "selected_phase": "initial | continuation | other",
      "selected_cluster_id": "string"
    },
    "criteria": [
      {
        "criterion_id": "string",
        "prompt": "string",
        "required": true,
        "prefill_status": "auto | suggest | none",
        "prefill_value": "typed value or null",
        "clinician_value": "typed value or null",
        "adjudication_status": "Found | Missing | Ambiguous | Unreviewed",
        "conflict_with_chart": true,
        "sources": {},
        "justification": "string | null"
      }
    ],
    "additional_cluster_suggestions": [
      {
        "cluster_id": "string",
        "condition_label": "string",
        "reason": "string"
      }
    ],
    "next_action": "stay_screen_2 | proceed_screen_3"
  },
  "messages": []
}
```

### Screen 3 Contracts

#### Screen 3 Request

Used when the clinician is ready to review the compiled result. This request is handled by the Structured Visual Agent.

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_3",
  "payload": {
    "selected_route_id": "string",
    "selected_phase": "initial | continuation | other",
    "selected_cluster_id": "string",
    "finalize_review": true
  }
}
```

#### Screen 3 Response

```json
{
  "session_id": "string",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_3",
  "status": "complete | warning | blocked | error",
  "payload": {
    "review_summary": {
      "selected_route_id": "string",
      "selected_phase": "initial | continuation | other",
      "selected_cluster_id": "string",
      "all_required_answered": true,
      "has_chart_conflicts": true
    },
    "answered_criteria": [
      {
        "criterion_id": "string",
        "prompt": "string",
        "final_answer": "typed value",
        "chart_supported": true,
        "sources": {},
        "justification": "string | null"
      }
    ],
    "unanswered_required_items": ["CRITERION_ID"],
    "warnings": [
      {
        "type": "chart_conflict | incomplete | additional_cluster_detected",
        "text": "string"
      }
    ],
    "submission_ready": true
  },
  "messages": []
}
```

## Cache Behavior Rules

### Policy Artifact Cache
- always read Tier 1 by `policy_id`
- refresh only when the source policy changes or parser version changes

### Retrieval Plan Cache
- lookup before generating a new retrieval plan
- cache key should include:
  - `policy_id`
  - `selected_route_id`
  - `selected_phase`
  - `selected_cluster_id`
  - `planner_version`
  - optional `semantic_model_version`
- invalidate when:
  - planner prompt changes
  - policy artifact changes
  - semantic model changes in a way that affects retrieval planning

## POC Success Criteria

The POC is successful if:
- the correct route is resolved from billing code
- phase is only prompted when truly required by policy logic
- route and cluster-entry dependencies are preserved
- the correct disease cluster is materialized
- no required clinical criteria are dropped
- high-confidence EHR prefills are shown when available
- unresolved or conflicting items are surfaced clearly to clinicians

## Reference Files
- `functions/selection_resolver.py`
- `scripts/production/agents/policy_parser_agent_prompt_v4.md`
- `scripts/production/agents/retrieval_planner_agent_prompt_v1.md`
- `scripts/schema_v4/prior_auth_v4_schema.md`
- `scripts/schema_v4/retrieval_plan_schema.md`
- `scripts/criterion_reasoning_agent_prompt.md`
- `scripts/questionnaire_traverse_w_router_code_agent.py` (legacy runtime to replace/refactor)
