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
- return the Screen 2 payload
- accept Screen 2 submit input and return the Screen 3 payload

Screen 1 remains deterministic backend logic and is out of scope for this
agent.

## Inputs

### Screen 2 initial request

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
- `retrieval_plan_v1` is optional. If present, the agent should skip planner
  delegation.
- inside agent state, persist the inner scope object under the clearer key
  `selected_scope_context`

### Screen 2 submit request

```json
{
  "session_id": "string",
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

### Screen 2 response

```json
{
  "status": "ok | warning | blocked | error",
  "payload": {
    "selected_scope": {
      "selected_route_id": "string",
      "selected_phase": "initial | continuation | other",
      "selected_cluster_id": "string"
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
    "warnings": [],
    "submission_ready": true
  },
  "messages": []
}
```

## State Contract

Persistent `state` keys:
- `subject_id`
- `policy_id`
- `selected_route_id`
- `selected_phase`
- `selected_cluster_id`
- `selected_scope_context`
- `policy_master_v4`
- `retrieval_plan_v1`
- `criterion_result_map`
- `criterion_ui_map`
- `logic_evaluation`
- `screen_2_payload`
- `screen_3_payload`
- `messages`

Temporary `scratchpad` keys:
- `current_plan_item`
- `current_reasoning_result`
- `current_criterion_id`
- `iteration_output`

## Required deterministic helpers

The agent depends on these Python helpers outside the block graph:
- `scripts/production/functions/python_code_blocks.py`

The agent does not need to run the Selection Resolver. That work is already done
before Screen 2.

## Block Graph

Recommended DSS 14.5+ flow:

1. `init_state` — `SET_STATE_ENTRIES`
   - initialize empty `criterion_result_map`, `messages`, and output containers
   - copy request payload fields into state
   - map `payload.scoped_policy_context` into `state["selected_scope_context"]`

2. `have_plan?` — `ROUTING`
   - if `state["retrieval_plan_v1"]` exists and has non-empty `plan_items`, go to `execute_plan`
   - otherwise go to `plan_retrieval`

3. `plan_retrieval` — `DELEGATE_TO_OTHER_AGENT`
   - call `scripts/production/agents/retrieval_planner_agent_prompt_v1_1.md`
   - input:
     - `subject_id`
     - `selected_scope_context`
   - save result to `state["retrieval_plan_v1"]`
   - note: `retrieval_plan_v1` is tool-agnostic; it carries archetypes,
     retrieval strategies, query fragments, and time rules, but not concrete
     tool-routing objects
   - for diagnosis-grounded hybrid disease-state criteria, the plan must
     preserve a diagnosis-code structured leg plus a qualifier-resolution leg

4. `execute_plan` — `FOR_EACH`
   - iterate over `state["retrieval_plan_v1"]["plan_items"]`
   - for each item, set `scratchpad["current_plan_item"]`

5. `reason_one_criterion` — `DELEGATE_TO_OTHER_AGENT`
   - call `scripts/production/agents/criterion_reasoning_agent_prompt_v1_1.md`
   - input:
     - `subject_id`
     - `current_plan_item`
     - optional clinician answers already present for this criterion
   - the reasoning agent derives tool order from
     `current_plan_item.execution_hints.retrieval_strategy` and
     `current_plan_item.execution_hints.criterion_archetype`
   - for `ARC_disease_activity_or_severity_state`, the reasoning agent should
     first execute diagnosis-grounded structured retrieval when diagnosis codes
     are available, then resolve activity/severity/remission qualifiers from
     notes and/or observations
   - save result to `scratchpad["current_reasoning_result"]`

6. `accumulate_result` — `PYTHON_CODE`
   - call
     `scripts.production.functions.python_code_blocks.accumulate_current_reasoning_result(...)`
   - merge/update `state["criterion_result_map"][criterion_id]`
   - later iterations should overwrite earlier incomplete results for the same
     criterion if needed

7. `build_criterion_ui_map` — `PYTHON_CODE`
   - merge:
     - `selected_criteria_catalog`
     - any existing clinician answers
     - `criterion_result_map`
   - compute one UI view-model row per criterion
   - save to `state["criterion_ui_map"]`

8. `evaluate_logic_tree` — `PYTHON_CODE`
   - call
     `scripts.production.functions.python_code_blocks.evaluate_logic_tree_from_state(...)`
   - the helper derives the primary cluster root plus supporting route-guard,
     cluster-entry-guard, logic-profile, and inherited-diagnosis roots from
     `selected_scope_context`
   - save to `state["logic_evaluation"]`

9. `build_screen_2_payload` — `PYTHON_CODE`
   - build ordered criterion rows from `criterion_ui_map`
   - compute `next_action`
   - save final object to `state["screen_2_payload"]`

10. `emit_screen_2` — `GENERATE_OUTPUT`
   - return Screen 2 payload as JSON

11. `screen_2_submit` — second entry path
   - merge clinician answers into state
   - rebuild `criterion_ui_map`
   - recompute completeness and conflicts
   - build `state["screen_3_payload"]`
   - emit final review JSON

## Routing Rules

### Initial Screen 2 path
- if request already contains a valid `retrieval_plan_v1`, skip planner
- if `retrieval_plan_v1.plan_items` is empty, return warning payload
- if any agent delegate fails, return warning/error payload with preserved state

### Screen 2 submit path
- if any required criterion remains unresolved and unanswered, `submission_ready=false`
- if clinician answers conflict with chart-backed `criterion_result_map`, include warning
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

Guidance:
- `criterion_ui_map` is a webapp-facing derived state, not the canonical
  adjudication artifact
- `chart_result` should mirror `criterion_result_map[criterion_id]`
- `clinician_input` should mirror the latest user-entered answer for that
  criterion
- `ui_resolution` should be derived by deterministic merge rules rather than
  generated by the LLM
- Screen 2 response payloads should emit the ordered `criteria` rows as the
  primary frontend contract and should keep `criterion_result_map` in backend
  state rather than duplicating it in the response payload

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
  - set `display_state = conflict`
  - set `conflict_flag = true`
  - explain the mismatch in `conflict_reason`

Recommended presentation order:
- show route guards first
- then cluster-entry guards
- then cluster criteria
- preserve the flattened backend execution model; ordering is a UI concern

## First POC Build Scope

Build the first Structured Agent with these constraints:
- only Screen 2 initial request + Screen 2 submit
- one selected cluster only
- no parallel execution yet
- no additional cluster suggestions yet
- no artifact generation yet

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
- `build_screen3_payload(...)`

This will keep block-level Python concise and easier to debug in DSS.
