# Screen 2 Structured Agent Spec

## Purpose

This Structured Visual Agent owns Screen 2 and Screen 3 orchestration after
Screen 1 has already resolved the selected route, phase, cluster, and guards.

It should:
- accept `subject_id + scoped_policy_context`
- load or generate `retrieval_plan_v1`
- execute one reasoning pass per flattened criterion
- build `criterion_result_map`
- evaluate the selected cluster logic tree
- prepare the Screen 2 review payload
- call an approval-enabled managed Python review tool
- capture approved or edited review input and return the reviewed Screen 2 artifact

Screen 1 remains deterministic backend logic and is out of scope for this
agent.

POC guardrail:
- Don't overcode. This is a POC.

Document role:
- use this file as the technical Screen 2 / Screen 3 Structured Agent build
  spec
- use `scripts/schema_v4/prior-auth_assistant.md` for higher-level workflow,
  webapp, and ownership guidance

## Inputs

### Screen 2 initial request

```json
{
  "session_id": "optional string correlation id",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_2",
  "payload": {
    "selected_route_id": "string",
    "selected_phase": "initial | continuation | other",
    "selected_cluster_id": "string",
    "scoped_policy_context": {},
    "policy_master_v4": {},
    "retrieval_plan_v1": null,
    "criterion_answers": {}
  }
}
```

Notes:
- `scoped_policy_context` is required.
- `policy_master_v4` is required so the agent can evaluate the selected logic
  tree after criterion execution.
- `session_id` is optional for the POC. When present, it is a correlation id
  from the webapp or backend request context and should be forwarded unchanged.
- `retrieval_plan_v1` is optional. If present, the agent should skip planner
  delegation.
- `criterion_answers` is optional, but when present it may already contain
  Screen 1 answers for selected route guards and cluster-entry guards.
- skipped Screen 1 questions should remain unanswered rather than being set to
  `false`.
- `criterion_answers` is the working clinician-input map keyed by
  `criterion_id`.
- inside agent state, persist the inner scope object under the clearer key
  `selected_scope_context`

### Optional Screen 2 submit request fallback

This fallback is only needed if a custom webapp cannot use the DSS managed-tool
approval flow directly. The primary POC path is the approval-enabled Screen 2
human review tool.

```json
{
  "session_id": "optional string correlation id",
  "subject_id": "string",
  "policy_id": "string",
  "screen_id": "screen_2_submit",
  "payload": {
    "selected_route_id": "string",
    "selected_phase": "initial | continuation | other",
    "selected_cluster_id": "string",
    "criterion_answers": {
      "CRITERION_ID": {
        "answer": true,
        "value": "optional typed value",
        "comment": "optional string",
        "override_prefill": false
      }
    },
    "criterion_result_map": {},
    "logic_evaluation": {}
  }
}
```

## Output

### Screen 2 review payload

This object is saved to `state["screen_2_payload"]` and sent to the
approval-enabled Screen 2 review tool. A custom webapp fallback may also return
this object directly.

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

### Screen 3 response

```json
{
  "status": "complete | warning | blocked | error",
  "payload": {
    "review_summary": {},
    "answered_criteria": [],
    "unanswered_required_items": [],
    "warnings": [
      {
        "criterion_id": "string",
        "criterion_kind": "route_guard | cluster_entry_guard | inherited_diagnosis | cluster_criterion",
        "prompt": "string",
        "display_state": "satisfied | not_satisfied | needs_clinician | unanswered",
        "type": "clinician_override | other_warning_type",
        "message": "string"
      }
    ],
    "submission_ready": true
  },
  "messages": []
}
```

## State Contract

Persistent `state` keys:
- `session_id`
- `subject_id`
- `policy_id`
- `selected_route_id`
- `selected_phase`
- `selected_cluster_id`
- `selected_scope_context`
- `policy_master_v4`
- `retrieval_plan_v1`
- `criterion_answers`
- `criterion_result_map`
- `criterion_ui_map`
- `logic_evaluation`
- `screen_2_payload`
- `screen_2_review_tool_input`
- `screen_2_review_result`
- `messages`

Temporary `scratchpad` keys:
- `current_plan_item`
- `current_reasoning_result`
- `current_criterion_id`
- `iteration_output`

## Required deterministic helpers

The agent depends on these Python helpers outside the block graph:
- `scripts/agent_flow/functions/python_code_blocks.py`

The agent does not need to run the Selection Resolver. That work is already done
before Screen 2.

## Block Graph

Recommended DSS 14.5+ flow:

1. `init_state` — `SET_STATE_ENTRIES`
   - this is a required production ingestion step, not a test-only adapter
   - initialize empty `criterion_result_map`, `messages`, and output containers
   - copy request fields into state:
     - `subject_id`
     - `policy_id`
     - `session_id`
     - `payload.selected_route_id`
     - `payload.selected_phase`
     - `payload.selected_cluster_id`
     - `payload.policy_master_v4`
     - `payload.criterion_answers`
   - persist `payload.scoped_policy_context` as
     `state["selected_scope_context"]`
   - preserve incoming `criterion_answers` so Screen 1 clinician input is
     available during conflict detection

2. `plan_retrieval` — `DELEGATE_TO_OTHER_AGENT`
   - call `scripts/agent_flow/agents/retrieval_planner_agent_prompt_v1_1.md`
   - input:
     - `subject_id`
     - `selected_scope_context`
   - save result to `state["retrieval_plan_v1"]`
   - note: `retrieval_plan_v1` is tool-agnostic; it carries archetypes,
     retrieval strategies, query fragments, and time rules, but not concrete
     tool-routing objects
   - for diagnosis-grounded hybrid disease-state criteria, the plan must
     preserve a diagnosis-code structured leg plus a qualifier-resolution leg

3. `execute_plan` — `FOR_EACH`
   - iterate over `state["retrieval_plan_v1"]["plan_items"]`
   - for each item, set `scratchpad["current_plan_item"]`

4. `reason_one_criterion` — `DELEGATE_TO_OTHER_AGENT`
   - call `scripts/agent_flow/agents/criterion_reasoning_agent_prompt_v1_1.md`
   - input:
     - `subject_id`
     - `current_plan_item`
     - optional clinician answers already present for this criterion from
       Screen 1 and/or Screen 2
   - the reasoning agent derives tool order from
     `current_plan_item.execution_hints.retrieval_strategy` and
     `current_plan_item.execution_hints.criterion_archetype`
   - for `ARC_disease_activity_or_severity_state`, the reasoning agent should
     first execute diagnosis-grounded structured retrieval when diagnosis codes
     are available, then resolve activity/severity/remission qualifiers from
     notes and/or observations
   - save result to `scratchpad["current_reasoning_result"]`

5. `accumulate_result` — `PYTHON_CODE`
   - call
     `scripts.agent_flow.functions.python_code_blocks.accumulate_current_reasoning_result(...)`
   - merge/update `state["criterion_result_map"][criterion_id]`
   - later iterations should overwrite earlier incomplete results for the same
     criterion if needed

6. `build_criterion_ui_map` — `PYTHON_CODE`
   - merge:
     - `selected_criteria_catalog`
     - any existing clinician answers
     - `criterion_result_map`
   - compute one UI view-model row per criterion
   - compare chart-backed results against the latest clinician input, including
     answers first collected in Screen 1, to set `conflict_flag`
   - save to `state["criterion_ui_map"]`

7. `evaluate_logic_tree` — `PYTHON_CODE`
   - call
     `scripts.agent_flow.functions.python_code_blocks.evaluate_logic_tree_from_state(...)`
   - the helper derives the primary cluster root plus supporting route-guard,
     cluster-entry-guard, logic-profile, and inherited-diagnosis roots from
     `selected_scope_context`
   - save to `state["logic_evaluation"]`

8. `prepare_screen_2_review_payload` — `PYTHON_CODE`
   - call
     `scripts.agent_flow.functions.python_code_blocks.prepare_screen2_review_payload(...)`
   - build ordered criterion rows from `criterion_ui_map`
   - copy clinician-friendly scope labels from `selected_scope_context` into:
     - `screen_2_payload.payload.selected_scope_display.route_label`
     - `screen_2_payload.payload.selected_scope_display.phase_label`
     - `screen_2_payload.payload.selected_scope_display.cluster_label`
   - compute `next_action`
   - save final object to `state["screen_2_payload"]`
   - build `state["screen_2_review_tool_input"]` for the human-review tool,
     including:
     - `session_id`
     - `subject_id`
     - `policy_id`
     - `selected_scope`
     - `screen_2_payload`
     - current `criterion_answers`

Screen 2 display-note:
- patient demographics should not be injected into the Structured Agent payload
  solely for UI rendering
- the webapp/backend layer should load `subject_id`, `gender`, and `birth_date`
  directly from the DSS `Patient` dataset and render them as a separate patient
  summary panel

9. `request_screen_2_human_review` — `CORE_LOOP`
   - use prompt file
     `scripts/agent_flow/agents/review_request_agent_prompt.md`
   - enable `State aware` so the block can use the built-in state read/write
     tool
   - call the managed custom Python tool described in
     `scripts/schema_v4/screen2_human_review_tool_spec.md`
   - wrap the prepared payload under a single top-level object:
     - `{"review_request": state["screen_2_review_tool_input"]}`
   - `review_request` must be emitted as a JSON object, not as a quoted string
   - do not reconstruct or summarize nested payload fields in the core loop
   - after the tool returns, serialize the exact returned object to JSON and
     write that JSON string into `state["screen_2_review_result"]` using the
     built-in state tool
   - configure the managed tool with `Enforce human approval before making tool
     call`
   - allow human editing of tool inputs when available so the reviewer can
     update criterion answers before approval
   - do not rely on `Additional output handling: Save to state` as the primary
     persistence mechanism for this block
   - stop after the state write; do not re-enter another review iteration

Step 9 meaning:
- in `native DSS approval mode`, this is the actual managed human-review
  checkpoint
- in `standard webapp review mode`, the same logical boundary is implemented by
  rendering `screen_2_payload` in the webapp and collecting
  `approved_criterion_answers` directly from the clinician
- keep the clinician-answer schema the same in both modes

10. `emit_review_result_artifact` — `GENERATE_OUTPUT`
   - emit `state["screen_2_review_result"]` as the terminal JSON artifact from
     the Structured Agent
   - do not build `screen_3_payload` inside the Structured Agent
   - do not call the Retrieval Planner Agent or Criterion Reasoning Agent on
     this path
   - do not perform new chart retrieval on this path
   - keep this step as a pure artifact-emission boundary so downstream systems
     can deterministically transform the reviewed output into Screen 3, FHIR,
     or other future targets

Step 10 meaning:
- consume the approved review snapshot, not raw chart evidence
- treat `approved_criterion_answers` as the submitted clinician-reviewed answer
  map
- keep the reviewed artifact flexible for downstream deterministic transforms
  outside the Structured Agent

Optional API fallback:
- a separate `screen_2_submit` entry path can still be exposed for a custom
  webapp that cannot use the DSS approval UI directly
- this fallback should run the same deterministic merge and recomputation logic
  as the backend path that consumes `screen_2_review_result`
- do not add LLM blocks, delegated reasoning blocks, or chart retrieval to the
  fallback path

## Routing Rules

### Initial Screen 2 path
- the default deployable POC path goes directly from `init_state` to
  `plan_retrieval`
- if a later deployment explicitly preloads a valid `retrieval_plan_v1`, an
  optional routing step may skip planner and go directly to `execute_plan`
- if `retrieval_plan_v1.plan_items` is empty, return warning payload
- if any agent delegate fails, return warning/error payload with preserved state

### Screen 2 human approval path
- the managed Python review tool is the human-in-the-loop boundary
- DSS 14.5 may require a `CORE_LOOP` block instead of `MANUAL_TOOL_CALL`
- when using `CORE_LOOP`, the prompt must treat the prepared payload as opaque
  and pass it through unchanged under `review_request`
- the core loop must preserve JSON typing and must not convert the prepared
  object into a Python-style string literal
- enable `State aware` and use the built-in state write capability to persist
  the tool result explicitly as a JSON string
- configure the managed tool to enforce human approval before execution
- if the reviewer edits criterion answers, treat those edits as clinician input
- after approval, emit the reviewed Screen 2 artifact and let the backend
  deterministically recompute Screen 3
- no LLM block, delegated reasoning block, or chart retrieval is required after
  approval
- if approval is rejected, do not continue to Screen 3 submission-ready output
- if any required criterion remains unresolved and unanswered, `submission_ready=false`
- if clinician answers conflict with chart-backed `criterion_result_map`, emit a
  structured warning item without changing the clinician-selected final
  criterion disposition
- if all required criteria are answered, allow `proceed_screen_3`

## Recommended State Shapes

### `criterion_result_map`

```json
{
  "CRITERION_ID": {
    "status": "Found | Missing | Ambiguous | Unreviewed",
    "meets_criterion": true,
    "extracted_value": "compact normalized value or null",
    "sources": {},
    "justification": "string or null"
  }
}
```

Guidance:
- `status` is the chart-evidence resolution field:
  - `Found` means the chart is sufficient to classify the criterion
  - `Missing` means the chart does not contain the required supporting evidence
  - `Ambiguous` means relevant evidence exists but the qualifier-level
    conclusion is unresolved
  - `Unreviewed` means not yet evaluated
- `meets_criterion` is the adjudication field and may be `true` only when
  `status = Found`
- `extracted_value` should be a compact normalized result for UI prefill or
  downstream logic, not a duplicate of raw sources
- `sources.structured` should hold all relevant returned EHR records, not an
  aggregated summary row
- `sources.notes` should hold clinician-reviewable excerpts plus why they
  matter, not a single merged snippet
- `sources.notes[].excerpt` should be a focused 1-3 sentence local passage,
  usually about 300-600 characters, preserving the original note wording
- `sources.notes[].why_it_matters` should briefly explain why that passage was
  selected for this criterion
- `justification` should explain the decision, not restate the raw evidence
- for exclusionary criteria, chart silence is not enough for satisfaction; if
  documented absence of the disqualifying fact is not found, use
  `status = Missing` and `meets_criterion = false`

### `logic_evaluation`

```json
{
  "selected_cluster_satisfied": true,
  "selected_cluster_status": "satisfied | not_satisfied | unresolved",
  "unresolved_criterion_ids": ["CRITERION_ID"],
  "criterion_counts": {
    "satisfied": 0,
    "not_satisfied": 0,
    "unresolved": 0
  }
}
```

Guidance:
- `selected_cluster_status = satisfied`
  - cluster logic passes from chart-backed evidence alone
- `selected_cluster_status = not_satisfied`
  - at least one criterion is chart-backed and fails
- `selected_cluster_status = unresolved`
  - one or more criteria still require clinician follow-up because evidence is
    missing, ambiguous, or unreviewed
- `unresolved_criterion_ids` should drive the Screen 2 prompt list for
  clinician response

### `criterion_ui_map`

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
      "display_state": "satisfied | not_satisfied | needs_clinician | unanswered",
      "prefill_value": null,
      "use_chart_as_prefill": false,
      "conflict_flag": false,
      "conflict_reason": null,
      "comment_required": false,
      "comment_guidance": null,
      "final_answer": null,
      "final_source": "chart | clinician | unresolved | system"
    }
  }
}
```

Guidance:
- `criterion_ui_map` is a webapp-facing derived state, not the canonical
  adjudication artifact
- `chart_result` should mirror `criterion_result_map[criterion_id]`
- `clinician_input` should mirror the latest user-entered answer for that
  criterion, regardless of whether it was first captured in Screen 1 or Screen
  2
- `ui_resolution` should be derived by deterministic merge rules rather than
  generated by the LLM
- Screen 2 review payloads should include ordered `criteria` rows as the primary
  frontend/reviewer contract and should keep `criterion_result_map` in backend
  state rather than duplicating it in the review payload

Recommended merge rules:
- if `chart_result.status = Found` and `clinician_input.answered = false`
  - set `display_state = satisfied` or `not_satisfied` based on
    `chart_result.meets_criterion`
  - set `prefill_value` from `chart_result.extracted_value` when useful
  - set `use_chart_as_prefill = true`
- if `chart_result.status = Missing`
  - set `display_state = needs_clinician`
  - do not auto-fail the criterion in the UI
- if `chart_result.status = Ambiguous`
  - set `display_state = needs_clinician`
- if `chart_result.status = Unreviewed` and clinician has not answered
  - set `display_state = unanswered`
- if clinician answer exists and materially agrees with chart-backed `Found`
  result
  - set `conflict_flag = false`
  - keep `display_state` aligned to the agreed outcome
- if clinician answer exists and materially conflicts with a chart-backed
  `Found` result
  - keep `display_state` aligned to the clinician answer
  - set `conflict_flag = true`
  - explain the mismatch in `conflict_reason`
  - if the clinician comment is blank, set `comment_required = true`
  - use warnings for auditability, but do not let the warning override the
    clinician-selected final criterion state
- treat Screen 1 and Screen 2 clinician answers identically once they are in
  `criterion_answers`; the merge layer should not care where the answer was
  first entered

Recommended presentation order:
- show route guards first
- then cluster-entry guards
- then cluster criteria
- preserve the flattened backend execution model; ordering is a UI concern

## First POC Build Scope

Build the first Structured Agent with these constraints:
- one Screen 2 initial request with approval-enabled human review tool
- one selected cluster only
- no parallel execution yet
- no additional cluster suggestions yet
- no artifact generation yet
- no re-reasoning after approval; review capture is deterministic recomputation
  only

That keeps the first build small while still proving the value of the Structured
Agent.

## Suggested next implementation step

Use `python_code_blocks.py` as the shared helper module for Screen 2 Python
blocks:
- `initialize_placeholder_state(...)`
- `accumulate_current_reasoning_result(...)`
- `build_criterion_ui_map(...)`
- `evaluate_logic_tree(...)`
- `evaluate_logic_tree_from_state(...)`
- `build_screen2_payload(...)`
- `build_screen2_review_tool_input_data(...)`
- `prepare_screen2_review_payload(...)`

Use `scripts/agent_flow/agents/review_request_agent_prompt.md` as the
dedicated Step 10 core-loop prompt in DSS 14.5.

This will keep block-level Python concise and easier to debug in DSS.
