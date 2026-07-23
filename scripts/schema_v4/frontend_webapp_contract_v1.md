# Prior Auth Webapp Contract v1

## Purpose

This document defines the product-facing functional scope and frontend/backend
contract for the prior-authorization webapp.

POC guardrail:
- Don't overcode. This is a POC.

Document role:
- describe what the webapp must do for clinicians
- define the stable webapp-facing JSON contracts
- describe how the webapp interacts with the Structured Agent and the human
  review tool
- capture current implemented scope and the planned next work without turning
  this document into a build notebook

Canonical references:
- workflow and ownership:
  `scripts/schema_v4/prior-auth_assistant.md`
- Structured Agent technical build spec:
  `scripts/schema_v4/screen2_structured_agent_spec.md`
- human review tool spec:
  `scripts/schema_v4/screen2_human_review_tool_spec.md`

## Product Scope

The webapp provides a three-stage clinician workflow:
- Screen 1: deterministic scope selection
- Screen 2: clinical eligibility review
- Screen 3: final submission review

The webapp must support two runtime modes:
- `local`
  - fixture/static-data mode for local development and DSS static testing
- `dss`
  - live DSS dataset mode with a Structured Agent run and human-validation step

The webapp must support two review patterns:
- `standard webapp review mode`
  - Screen 2 is rendered directly from `screen_2_payload`
  - clinician edits are submitted through the webapp
  - backend deterministically builds Screen 3
- `native DSS approval mode`
  - the Structured Agent pauses at the human-validation step
  - the webapp starts a run, polls run state, renders the paused review
    payload, and resumes the same run after clinician approval or edits

In both review patterns, the clinician-answer schema must remain the same.

## Current Functional Scope

### Screen 1

The webapp currently supports:
- patient selection
- policy selection
- billing code selection
- phase selection when required
- cluster selection
- route-guard and cluster-entry-guard questions
- deterministic generation of `selected_scope_context`

Screen 1 is owned by deterministic backend logic. The frontend should treat the
Screen 1 payload as the only supported webapp contract for this stage.

### Screen 2

The webapp currently supports:
- selected-scope display in the left rail
- criteria count derived from `selected_scope_context.selected_criteria_catalog`
- criterion cards with:
  - criterion type
  - chart evidence status
  - chart evidence explanation
  - clinician answer input
  - clinician comment input
  - override warning when clinician judgment differs from chart-backed evidence
- cluster-level status and criterion counts
- local synchronous bootstrap for fixture/static mode
- DSS run-based bootstrap with polling and HITL resume path

Current DSS behavior:
- the backend starts a run
- the frontend polls run state
- the frontend may display partial run progress and a partial Screen 2 snapshot
- the paused human-review payload is rendered using the same Screen 2 contract
  as the standard webapp path

### Screen 3

The webapp currently supports:
- final review summary
- submission readiness
- total criterion counts
- answered criteria
- unanswered required items
- advisory warnings

## System Boundaries

### Webapp frontend

The frontend is responsible for:
- rendering Screen 1, Screen 2, and Screen 3
- storing current clinician input
- handling page flow and page-level loading/error states
- rendering run-state feedback in DSS mode

### Webapp backend

The backend is responsible for:
- serving the Screen 1 deterministic payload
- loading patient summary data
- choosing the runtime path based on `local` or `dss`
- in `dss` mode, resolving the Structured Agent from the current DSS project
  context
- in `local` mode:
  - loading fixture/static Screen 2 data
  - deterministically building Screen 3 after review
- in `dss` mode:
  - starting the Structured Agent run
  - normalizing run state for the frontend
  - resuming the paused HITL run after clinician review

### Structured Agent

The Structured Agent is responsible for:
- Screen 2 orchestration after Screen 1 scope is already resolved
- planning retrieval
- running criterion reasoning
- accumulating `criterion_result_map`
- evaluating logic
- building `screen_2_payload`
- calling the human review tool
- returning the reviewed Screen 2 artifact after approved review input

### Human review tool

The human review tool is the managed approval boundary in native DSS mode. Its
job is to carry the review payload through the DSS approval experience and
return approved or edited clinician answers. It must not do additional chart
retrieval or LLM reasoning.

## Runtime Modes And User Flows

### `local` mode

Flow:
1. Screen 1 is resolved deterministically.
2. Screen 2 is loaded synchronously from the local/static path.
3. The clinician edits answers in the webapp.
4. The backend deterministically builds Screen 3.

### `dss` mode

Flow:
1. Screen 1 is resolved deterministically.
2. The backend starts a Structured Agent run.
3. The frontend polls run state.
4. The Structured Agent pauses at the human-validation step.
5. The paused review payload is rendered in the webapp.
6. The clinician approves or edits criterion answers.
7. The backend resumes the paused run.
8. The backend deterministically builds Screen 3 from the reviewed artifact.

### Current transport rule

- `local` mode may use synchronous Screen 2 bootstrap
- `dss` mode should use the run-based API
- the frontend-facing Screen 2, review-result, and Screen 3 payload shapes
  should remain consistent across both modes

### Current DSS deployment coupling

- the deployed DSS project key is `DEMO_PRIOR_AUTH_AGENT`
- the current backend resolves `agent:NkBiV9OM` from the active/default DSS
  project context rather than passing an explicit project key to the agent call
- operationally, this means the standard webapp and Structured Agent are
  expected to live in the same DSS project context

## Frontend Information Architecture

### Left rail

The left rail should contain:
- Patient summary
- Policy Review
- Reviewer note

The workflow stepper remains in the main content area.

### Screen 1 layout

Screen 1 should present:
- title: `Prior authorization requirement review`
- a Scope Builder card
- optional guard-question card when needed
- a CTA to open Screen 2

### Screen 2 layout

Screen 2 should present:
- title: `Clinical eligibility review`
- section header: `Eligibility review`
- a status card showing:
  - cluster status
  - next action
  - criteria count
  - satisfied count
  - not-satisfied count
  - unresolved count
- one criterion card per ordered criterion

### Screen 3 layout

Screen 3 should present:
- title: `Final submission review`
- submission readiness summary
- counts summary
- warnings when present
- unanswered required items
- answered criteria

### Shared UI rules

- use human-readable labels for backend enum values such as `next_action`
- use consistent status tones across Screen 2 and Screen 3
- use criterion-type color coding:
  - route guard
  - disease cluster entry guard
  - inherited diagnosis
  - cluster criterion
- use the same criteria count source in `local` and `dss` mode:
  `selected_scope_context.selected_criteria_catalog`

## Canonical Webapp Contracts

### 1. Runtime info

```json
{
  "data_source": "local | dss"
}
```

### 2. Screen 1 response

```json
{
  "status": "ok | blocked | error",
  "payload": {
    "step": "collect_billing_code | collect_phase | collect_cluster | review_scope",
    "selection": {
      "subject_id": "string or null",
      "policy_id": "string or null",
      "billing_code": "string or null",
      "selected_route_id": "string or null",
      "selected_phase": "string or null",
      "selected_cluster_id": "string or null"
    },
    "route_display": {
      "route_id": "string or null",
      "route_label": "string or null"
    },
    "phase_options": [],
    "cluster_options": [],
    "route_guard_questions": [],
    "cluster_entry_guard_questions": [],
    "selected_scope_context": {},
    "criterion_answers": {},
    "next_action": "collect_billing_code | collect_phase | collect_cluster | review_scope | proceed_screen_2 | blocked"
  },
  "messages": [],
  "patient_summary": {},
  "scenario": {}
}
```

Frontend may rely on:
- `payload.step`
- `payload.selection`
- `payload.route_display`
- `payload.phase_options`
- `payload.cluster_options`
- `payload.route_guard_questions`
- `payload.cluster_entry_guard_questions`
- `payload.selected_scope_context`
- `payload.criterion_answers`
- `payload.next_action`

### 3. Screen 2 response

```json
{
  "status": "ok | warning | blocked | error",
  "payload": {
    "selected_scope": {
      "selected_route_id": "string",
      "selected_phase": "initial | continuation | other",
      "selected_cluster_id": "string"
    },
    "selected_scope_display": {
      "route_label": "string",
      "phase_label": "string",
      "cluster_label": "string"
    },
    "criteria": [],
    "logic_evaluation": {},
    "additional_cluster_suggestions": [],
    "next_action": "stay_screen_2 | proceed_screen_3"
  },
  "messages": []
}
```

Frontend may rely on:
- `payload.selected_scope`
- `payload.selected_scope_display`
- ordered `payload.criteria`
- `payload.logic_evaluation`
- `payload.next_action`
- top-level `status`

Criteria count rule:
- derive criteria count from
  `selected_scope_context.selected_criteria_catalog.length` when available
- use `payload.criteria.length` only as a presentation fallback

### 4. Criterion row contract

```json
{
  "criterion_id": "string",
  "criterion_kind": "route_guard | cluster_entry_guard | inherited_diagnosis | cluster_criterion",
  "prompt": "string",
  "answer_type": "boolean | string | number",
  "required": true,
  "clinician_input": {
    "answer": true,
    "value": "optional",
    "comment": "optional",
    "override_prefill": false,
    "answered": true
  },
  "chart_result": {
    "status": "Found | Missing | Ambiguous | Unreviewed",
    "meets_criterion": true,
    "extracted_value": {},
    "justification": "string or null",
    "sources": {
      "structured": [],
      "notes": []
    }
  },
  "ui_resolution": {
    "display_state": "satisfied | not_satisfied | needs_clinician | conflict | unanswered",
    "prefill_value": true,
    "use_chart_as_prefill": true,
    "conflict_flag": false,
    "conflict_reason": "string or null",
    "comment_required": false,
    "comment_guidance": "string or null",
    "final_answer": true,
    "final_source": "chart | clinician | unresolved"
  }
}
```

Ordering rule:
- preserve backend criterion order exactly as delivered

### 5. Screen 2 review result

```json
{
  "approval_status": "approved | edited | rejected",
  "approved_criterion_answers": {
    "CRITERION_ID": {
      "answer": true,
      "value": "optional typed value",
      "comment": "optional string",
      "override_prefill": false
    }
  },
  "reviewed_screen_2_payload": {},
  "review_metadata": {
    "reviewer": "string or null",
    "reviewed_at": "string or null",
    "comment": "string or null"
  },
  "human_validated": true
}
```

Answer-map semantics:
- `criterion_answers` is the working clinician-input map before approval or
  final submit
- `approved_criterion_answers` is the approved snapshot after review
- both use the same inner schema keyed by `criterion_id`

### 6. Screen 3 response

```json
{
  "status": "complete | warning | blocked | error",
  "payload": {
    "review_summary": {
      "selected_scope": {},
      "selected_scope_display": {},
      "criterion_totals": {
        "total": 0,
        "satisfied": 0,
        "rejected": 0,
        "unresolved": 0
      },
      "logic_evaluation": {}
    },
    "satisfied_criteria": [
      {
        "criterion_id": "string",
        "criterion_kind": "route_guard | cluster_entry_guard | inherited_diagnosis | cluster_criterion",
        "prompt": "string",
        "final_answer": true,
        "final_source": "chart | clinician | unresolved",
        "display_state": "satisfied | not_satisfied | needs_clinician | conflict | unanswered | unresolved",
        "justification": "string or null",
        "comment": "string or null",
        "conflict_flag": false,
        "conflict_reason": "string or null"
      }
    ],
    "rejected_criteria": [
      {
        "criterion_id": "string",
        "criterion_kind": "route_guard | cluster_entry_guard | inherited_diagnosis | cluster_criterion",
        "prompt": "string",
        "final_answer": false,
        "final_source": "chart | clinician | unresolved",
        "display_state": "not_satisfied",
        "justification": "string or null",
        "comment": "string or null",
        "conflict_flag": true,
        "conflict_reason": "string or null"
      }
    ],
    "unresolved_criteria": [
      {
        "criterion_id": "string",
        "criterion_kind": "route_guard | cluster_entry_guard | inherited_diagnosis | cluster_criterion",
        "prompt": "string",
        "display_state": "needs_clinician | unanswered | unresolved",
        "justification": "string or null",
        "final_answer": null,
        "final_source": "unresolved",
        "comment": "string or null",
        "conflict_flag": false,
        "conflict_reason": "string or null"
      }
    ],
    "review_alerts": [
      {
        "type": "human_review_rejected | missing_review_result | other_alert_type",
        "message": "string"
      }
    ],
    "submission_ready": true
  },
  "messages": []
}
```

Frontend may rely on:
- `payload.review_summary.selected_scope`
- `payload.review_summary.criterion_totals`
- `payload.review_summary.logic_evaluation`
- `payload.satisfied_criteria`
- `payload.rejected_criteria`
- `payload.unresolved_criteria`
- `payload.review_alerts`
- `payload.submission_ready`

Screen 3 readiness rule:
- `submission_ready=true` only when
  `payload.review_summary.logic_evaluation.selected_cluster_status = satisfied`
- a fully reviewed but ineligible case therefore remains not ready for
  submission
- `review_alerts` are reserved for global review/runtime issues and are not used
  as criterion-grouping buckets

Screen 3 presentation rule:
- `status` remains the deterministic workflow status for the Screen 3 payload
  (`complete | warning | blocked | error`)
- the webapp may present
  `payload.review_summary.logic_evaluation.selected_cluster_status` as the
  primary eligibility status in the audited-summary header
- criterion cards should be grouped by final disposition only:
  - `satisfied_criteria`
  - `rejected_criteria`
  - `unresolved_criteria`
- clinician/chart disagreement should remain card-level audit metadata via
  `conflict_flag` and `conflict_reason`, rather than create a duplicate
  criterion section

### 7. DSS run-based API

#### Start Screen 2 run

`POST /api/scenarios/<policy_id>/screen2/run`

Response:

```json
{
  "run_id": "string",
  "scenario": {},
  "patient_summary": {}
}
```

#### Get run state

`GET /api/runs/<run_id>/state`

Normalized response shape:

```json
{
  "status": "running | hitl_paused | completed | failed",
  "text_so_far": "string",
  "events": [],
  "progress": {
    "current_block_id": "string or null",
    "current_criterion_id": "string or null",
    "current_criterion_prompt": "string or null",
    "completed_criteria": 0,
    "total_criteria": 0
  },
  "hitl_payload": {
    "message": "string or null",
    "review_request": {}
  },
  "screen_2_response": {},
  "screen_2_snapshot": {},
  "screen_3_response": {},
  "edited_answers": {},
  "review_result": {},
  "error": "string or null"
}
```

#### Resume HITL run

`POST /api/runs/<run_id>/hitl/respond`

Request:

```json
{
  "approved_criterion_answers": {},
  "review_metadata": {
    "reviewer": "string or null",
    "reviewed_at": "string or null",
    "comment": "string or null"
  }
}
```

## Schema Alignment Notes

### Alignment with `screen2_structured_agent_spec.md`

The current webapp contract is aligned with the Structured Agent spec on these
core objects:
- Screen 2 initial request uses:
  - `subject_id`
  - `policy_id`
  - `screen_id`
  - `payload.selected_route_id`
  - `payload.selected_phase`
  - `payload.selected_cluster_id`
  - `payload.scoped_policy_context`
  - `payload.policy_master_v4`
  - `payload.criterion_answers`
- Screen 2 response shape matches the documented `screen_2_payload`
- Screen 3 response shape still matches the documented `screen_3_payload`, but
  in `dss` mode it is now derived deterministically by the backend from the
  stateful reviewed `screen_2_review_result` artifact rather than emitted
  directly by the Structured Agent
- `criterion_answers` remains the working answer map

Terminal-output rule:
- the current Structured Agent emits clinician-readable `agent_review_summary`
  Markdown as its terminal text output
- the webapp does not parse that text as an API payload; it uses the paused
  review request and retained `screen_2_review_result` state artifact instead

Important translation rule:
- the webapp/backend request uses `payload.scoped_policy_context`
- inside agent state and most runtime discussion, the same object is referred to
  as `selected_scope_context`

Current abstraction:
- the webapp contract does not expose `criterion_result_map`,
  `criterion_ui_map`, or other internal agent-state keys as primary frontend
  contracts
- those remain Structured Agent implementation details

### Alignment with `screen2_human_review_tool_spec.md`

The current webapp contract is aligned with the human review tool spec on these
core objects:
- the inner review payload is:
  - `session_id`
  - `subject_id`
  - `policy_id`
  - `selected_scope`
  - `screen_2_payload`
  - `criterion_answers`
- the review result uses:
  - `approval_status`
  - `approved_criterion_answers`
  - `reviewed_screen_2_payload`
  - `review_metadata`

Important wrapper rule:
- the native DSS tool call wraps the inner payload as:
  - `{"review_request": ...}`
- the webapp itself usually works with the inner review payload after backend
  normalization

Current normalization rule:
- the backend should extract and normalize the wrapped DSS payload before
  exposing it to the frontend
- the frontend should not depend directly on raw DSS tool-call wrapper details

Current DSS wrapper note:
- the deployed standard-webapp shell may still use an older browser bootstrap
  around the backend iframe
- the backend currently keeps compatibility for legacy wrapper requests such as
  `/first_api_call` and `/dist/...` while the wrapper definition is being
  aligned with the current Vite/Flask implementation

## Current Gaps And Temporary Adapters

- `local` mode still exists as a deliberate fixture/static development path
- patient summary is still a separate webapp/backend concern rather than part
  of the Structured Agent payload
- DSS streaming state is currently surfaced to the frontend in a normalized run
  state and rendered inside the standard Screen 2 criterion-review surface
- in live `dss` mode, the frontend should not render placeholder criterion
  cards before the first real `screen_2_snapshot` is available

## Planned Work

Planned next work at the time of this revision:
- continue polishing the DSS streaming presentation inside the standard Screen
  2 layout rather than maintaining a separate workflow-status panel
- progressively stream the same Screen 2 status card and real criterion cards
  while the DSS run is active
- keep Screen 2 UI behavior visually consistent between `local` and `dss`
  runtime modes
- continue tightening backend run-state normalization so the frontend depends on
  a stable product contract rather than raw DSS stream internals
- keep the JSON payload shapes above stable while improving transport handling
  and UI polish
