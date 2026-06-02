# Prior Auth Webapp Contract v1

## Purpose

This document freezes the frontend-facing POC contract so the Dataiku standard
webapp can be built while Step 10 persistence debugging continues.

POC guardrail:
- Don't overcode. This is a POC.

Assumption for this freeze:
- `screen_2_review_result` is available to the backend submit path, whether from
  live DSS state or from fixture/mock mode

Canonical references:
- workflow and ownership:
  `scripts/schema_v4/prior-auth_assistant.md`
- structured agent runtime contract:
  `scripts/schema_v4/screen2_structured_agent_spec.md`
- human review tool contract:
  `scripts/schema_v4/screen2_human_review_tool_spec.md`

## Frontend scope

The webapp should implement three clinician-facing stages:
- Screen 1: deterministic route and cluster selection
- Screen 2: criterion review with chart prefills, unresolved items, and conflict
  highlighting
- Screen 3: final review summary before downstream submission

For the current freeze, frontend implementation can start at Screen 2 and Screen
3 using fixture mode.

Current implementation note:
- the current work is still in UI-design mode
- Screen 1 is now rendered in the webapp, but Screen 2 is still populated from
  a static `structured_agent_context.json` for development
- patient summary is still populated from a local `Patient.csv` fixture
- both of these are temporary development adapters and should be replaced in
  deployment mode without changing the frontend-facing payload shapes

Deployment target:
- Screen 1 computes the final `selected_scope_context`
- the webapp/backend submits the current Screen 1 selection and clinician guard
  answers, and the backend deterministically re-resolves `selected_scope_context`
  before calling the Dataiku Structured Agent
- the Structured Agent generates `structured_agent_context`
- Screen 2 is populated from the live `screen_2_payload` inside that generated
  artifact
- patient summary is loaded from the DSS `Patient` dataset rather than from a
  CSV fixture

Runtime modes:
- `native DSS approval mode`
  - the Structured Agent pauses at the managed tool approval checkpoint
  - the webapp should start a run, poll streamed state, render the paused
    review payload when validation is requested, and resume the same run after
    clinician approval/edit
  - the resumed run deterministically builds Screen 3
- `standard webapp review mode`
  - the webapp renders Screen 2 from `screen_2_payload`
  - clinician edits are submitted as `approved_criterion_answers`
  - backend deterministically builds Screen 3
- both modes should reuse the same clinician-answer shape

## Layered schema plan

To keep Screen 1 and Screen 2 understandable, the webapp/backend contract
should follow three distinct layers:

### 1. Selection decision

This is the deterministic decision-engine output from
`resolve_selection_scope(...)`.

Purpose:
- decide what Screen 1 should ask next
- identify the selected route / phase / cluster by ID
- produce the final scoped artifact once selection is complete

This layer is:
- internal backend logic
- not a saved artifact
- not the final frontend payload contract

Recommended shape:

```json
{
  "status": "ok | blocked",
  "next_action": "collect_phase | collect_cluster | collect_cluster_guards | proceed_screen_2",
  "reason": "optional string",
  "messages": [],
  "selection": {
    "billing_code": "string",
    "selected_route_id": "string or null",
    "selected_phase": "string or null",
    "selected_cluster_id": "string or null"
  },
  "phase_values": [],
  "cluster_ids": [],
  "scoped_policy_context": {}
}
```

### 2. `selected_scope_context`

This is the durable Screen 1 artifact and the canonical handoff into the
Structured Agent for Screen 2.

Purpose:
- preserve the exact selected route / phase / cluster scope
- carry the hydrated policy context Screen 2 needs for planning, criterion
  ordering, and logic evaluation

This layer is:
- saved as the Screen 1 artifact
- the only scope artifact passed into Screen 2
- intentionally richer than the Selection decision layer

Current rule:
- keep `selected_scope_context` rich for now because Screen 2 helpers already
  depend on hydrated route / cluster / guard / criteria content
- do not thin this object until Screen 2 is explicitly refactored to rehydrate
  from `policy_master_v4`

Artifact naming rule:
- `scoped_policy_context` is the Screen 1 / API field name
- `selected_scope_context` is the runtime and saved-artifact name
- saved artifact files should store the inner scoped object only, not an extra
  wrapper object

### 3. Screen 1 payload

This is the only webapp-facing Screen 1 response contract.

Purpose:
- drive the Screen 1 step-by-step UI
- expose only the current step inputs and current selection state
- attach the final `selected_scope_context` once the selection is complete

This layer is:
- frontend-facing
- page-oriented
- built from the Selection decision layer

Recommended shape:

```json
{
  "status": "ok | blocked",
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
      "route_id": "string",
      "route_label": "string"
    },
    "phase_options": [],
    "cluster_options": [],
    "route_guard_questions": [],
    "cluster_entry_guard_questions": [],
    "selected_scope_context": {},
    "criterion_answers": {},
    "next_action": "collect_billing_code | collect_phase | collect_cluster | review_scope | proceed_screen_2"
  },
  "messages": []
}
```

Screen 1 contract rules:
- `build_screen1_payload(...)` should be the only frontend-facing Screen 1
  contract
- `resolve_selection_scope(...)` should not also act like a webapp payload
- avoid duplicating large objects like `route_summary`, `phase_summary`, and
  `cluster_shortlist` when the same information is already available through
  the final `selected_scope_context`
- only include `selected_scope_context` once the user has selected enough scope
  to enter the review stage

## Frozen payloads

### 0. Screen 1 response

The frontend should treat the Screen 1 payload as the canonical deterministic
selection contract for:
- patient ID entry
- policy selection
- billing code entry
- phase selection
- cluster selection
- route-guard / cluster-entry-guard review before Screen 2

Minimal stable shape:

```json
{
  "status": "ok | blocked",
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
    "next_action": "collect_billing_code | collect_phase | collect_cluster | review_scope | proceed_screen_2"
  },
  "messages": []
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

Frontend should not rely on:
- internal Selection decision objects
- direct resolver-specific helper fields that are not part of the Screen 1
  payload contract

Screen 1 layout direction:
- use one primary Scope Builder card for:
  - patient ID
  - policy
  - billing code
  - phase
  - disease cluster
- move patient summary above the Review Steps card in the left rail
- keep patient-summary fields empty until the user fills in the Scope Builder
- drop the separate Selected Scope card because it duplicates the Scope Builder
- in fixture mode, the policy selector may remain visible as a development-only
  control
- billing-code labels shown beside codes are placeholders for now; a later
  revision should use labels derived from `policy_master_v4.billing_code_sets`

### 1. Screen 2 response

The frontend should treat `screen_2_response.json` as the canonical payload for
initial eligibility review.

Backend runtime rule:
- the standard webapp should not load a saved `selected_scope_context` artifact
  to open Screen 2
- instead, it should re-run deterministic Screen 1 scope resolution from the
  current billing code, phase, cluster, and guard answers, then submit that
  resolved scope into the Structured Agent call

Mode-specific transport:
- `local` mode may keep a synchronous Screen 2 bootstrap route for fixture/static
  testing
- `dss` mode should use a run-based API:
  - start run
  - poll run state
  - read block-level streaming progress from Structured Agent event context
    rather than from free-text output
  - submit human-validation response
  - render final Screen 3 from the resumed run

Minimal stable shape:

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

Frontend patient-summary behavior:
- do not expect patient demographics in the Structured Agent payload
- load a small `patient_summary` object directly from the DSS `Patient` dataset
  in the webapp/backend layer using:
  - `subject_id`
  - `gender`
  - `birth_date`

Frontend should not rely on:
- free-text wording inside `messages`
- exact `chart_result.extracted_value` subfields across all policies

Screen 2 layout direction:
- move the review-context card to the left panel and rename it `Policy Review`
- include policy name and policy ID in that card
- move the reviewer-note card to the left panel
- left-panel order should be:
  - Patient summary
  - Policy Review
  - Review Steps
  - Reviewer note
- unify the status bar so keys and values are visually separated rather than
  merged inside a single pill
- keep status colors aligned to Dataiku functional color semantics
- criterion cards should emphasize:
  - the `Chart result` header
  - the chart evidence content
  - the `Clinician review` header
- drop the extra line `Chart assessment: criterion supported.`
- keep clinical evidence hidden by default behind an expandable section backed
  by `chart_result.sources`

### 2. Screen 2 review result

The frontend should treat `screen_2_review_result.json` as the canonical shape
returned after human review.

Stable shape:

```json
{
  "approval_status": "approved | edited | rejected",
  "approved_criterion_answers": {},
  "reviewed_screen_2_payload": {},
  "review_metadata": {
    "reviewer": "string or null",
    "reviewed_at": "string or null",
    "comment": "string or null"
  },
  "human_validated": true
}
```

Frontend should produce clinician edits in the same `approved_criterion_answers`
shape:

```json
{
  "CRITERION_ID": {
    "answer": true,
    "value": "optional typed value",
    "comment": "optional string",
    "override_prefill": false
  }
}
```

Answer-map semantics:
- `criterion_answers` is the in-progress working answer map used before human
  approval or final submit
- `approved_criterion_answers` is the approved snapshot returned by the native
  DSS approval path or submitted by the standard webapp path
- both should use the same inner object schema keyed by `criterion_id`

### 3. Screen 3 response

The frontend should treat `screen_3_response.json` as the canonical final review
payload.

Stable shape:

```json
{
  "status": "complete | warning | blocked | error",
  "payload": {
    "review_summary": {},
    "answered_criteria": [],
    "unanswered_required_items": [],
    "warnings": [],
    "submission_ready": true
  },
  "messages": []
}
```

Frontend may rely on:
- `payload.review_summary.selected_scope`
- `payload.review_summary.criterion_totals`
- `payload.answered_criteria`
- `payload.unanswered_required_items`
- `payload.warnings`
- `payload.submission_ready`

Screen 3 layout direction:
- do not show `approval_status` inside the submission-readiness card
- include answered route guards and cluster-entry guards in the answered
  criteria summary, not just cluster criteria

## Criterion row contract

Each Screen 2 criterion row is stable at this level:

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
    "final_answer": true,
    "final_source": "chart | clinician | unresolved"
  }
}
```

## Ordering rules

The frontend must preserve backend criterion order exactly as delivered.

Expected ordering policy:
- route guards first
- cluster-entry guards second
- inherited diagnosis criteria third
- cluster criteria last

The frontend should not reorder by status or by local heuristics.

## Screen behavior rules

### Screen 2

Render:
- selected scope summary
- one review card per criterion
- chart-backed prefill when `ui_resolution.use_chart_as_prefill = true`
- clinician input controls
- conflict state when `ui_resolution.conflict_flag = true`

Primary CTA behavior:
- if `payload.next_action = "stay_screen_2"`, continue review
- if `payload.next_action = "proceed_screen_3"`, allow transition to Screen 3

### Screen 3

Render:
- review summary counts
- answered criteria
- unanswered required items
- warnings
- final readiness state

Primary CTA behavior:
- disable downstream submission if `payload.submission_ready = false`

## Fixture mode

Fixture folder:
- `scripts/artifacts/fixtures/screen_payloads`

Available policy scenarios:
- `0059`: clean satisfied path
- `0314`: blocked / oncology continuation example
- `0655`: mixed unresolved continuation example
- `0685`: additional branch example

Per-policy files:
- `criterion_ui_map.json`
- `screen_2_response.json`
- `screen_2_review_result.json`
- `screen_3_response.json`

Recommended frontend dev flow:
1. load `screen_2_response.json`
2. render and locally edit clinician answers
3. compare against `screen_2_review_result.json` for submit-path shape
4. load `screen_3_response.json` for final review rendering

Current adapter placeholders:
- a backend adapter should continue to isolate how Screen 2 is loaded in
  development mode
- that adapter currently reads a static `structured_agent_context.json`
- in deployment mode, replace it with a Dataiku Structured Agent API call that
  accepts `selected_scope_context` and returns the generated
  `structured_agent_context`
- a backend adapter should continue to isolate how patient summary is loaded
- that adapter currently reads `scripts/artifacts/fixtures/Patient.csv`
- in deployment mode, replace it with a DSS dataset read against the canonical
  `Patient` dataset

## Dataiku standard webapp implementation notes

Use the existing team standard shape:
- Vue + Vite frontend
- Dataiku backend API
- store-driven page state

Useful local references:
- standard Vue template:
  `/Users/li-hengfu/Documents/GitHub/solutions-contrib/bs-templates/vue/{{cookiecutter.__project_slug}}`
- HITL example webapp:
  `/Users/li-hengfu/Downloads/webapps/regulatory_wizard`

Recommended structure for this project:
- `src/Api.ts`: typed frontend contract and backend calls
- `src/api/index.ts`: Dataiku-aware axios/base URL setup
- `src/stores/priorAuthStore.ts`: Screen 1/2/3 state, fixture mode, submit flow
- `src/components/`: criterion cards, scope summary, review summary, warnings
- `backend/backend.py`: fixture endpoints first, live DSS integration second

Relevant reference files:
- webapp API wrapper example:
  `/Users/li-hengfu/Downloads/webapps/regulatory_wizard/src/Api.ts`
- store and HITL state example:
  `/Users/li-hengfu/Downloads/webapps/regulatory_wizard/src/stores/wizardStore.ts`
- backend API shape example:
  `/Users/li-hengfu/Downloads/webapps/regulatory_wizard/backend/backend.py`

## Freeze boundary

Frontend can proceed now against these contracts.

Still unstable / backend-only:
- Step 10 DSS persistence mechanics for live `screen_2_review_result`
- correlation metadata such as `session_id`
- any future additional cluster suggestion behavior

The frontend should be written so that fixture mode and live mode share the same
payload shapes.
