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
    "criterion_result_map": {},
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
- `scoped_policy_context`
- `policy_master_v4`
- `retrieval_plan_v1`
- `criterion_result_map`
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
- `scripts/production/functions/logic_tree_evaluator.py`

The agent does not need to run the Selection Resolver. That work is already done
before Screen 2.

## Block Graph

Recommended DSS 14.5+ flow:

1. `init_state` — `SET_STATE_ENTRIES`
   - initialize empty `criterion_result_map`, `messages`, and output containers
   - copy request payload fields into state

2. `have_plan?` — `ROUTING`
   - if `state["retrieval_plan_v1"]` exists and has non-empty `plan_items`, go to `execute_plan`
   - otherwise go to `plan_retrieval`

3. `plan_retrieval` — `DELEGATE_TO_OTHER_AGENT`
   - call `retrieval_planner_agent_prompt_v1.md`
   - input:
     - `subject_id`
     - `scoped_policy_context`
   - save result to `state["retrieval_plan_v1"]`

4. `execute_plan` — `FOR_EACH`
   - iterate over `state["retrieval_plan_v1"]["plan_items"]`
   - for each item, set `scratchpad["current_plan_item"]`

5. `reason_one_criterion` — `DELEGATE_TO_OTHER_AGENT`
   - call `criterion_reasoning_agent_prompt.md`
   - input:
     - `subject_id`
     - `current_plan_item`
     - optional clinician answers already present for this criterion
   - save result to `scratchpad["current_reasoning_result"]`

6. `accumulate_result` — `PYTHON_CODE`
   - extract `criterion_id` from `scratchpad["current_reasoning_result"]`
   - merge/update `state["criterion_result_map"][criterion_id]`
   - later iterations should overwrite earlier incomplete results for the same
     criterion if needed

7. `evaluate_logic_tree` — `PYTHON_CODE`
   - locate the selected cluster in `policy_master_v4`
   - if the selected cluster references a `logic_profile_id`, fetch the profile
   - call `evaluate_logic_tree(...)`
   - save to `state["logic_evaluation"]`

8. `build_screen_2_payload` — `PYTHON_CODE`
   - build ordered criterion rows from:
     - `selected_criteria_catalog`
     - `criterion_result_map`
     - any existing clinician answers
   - compute `next_action`
   - save final object to `state["screen_2_payload"]`

9. `emit_screen_2` — `GENERATE_OUTPUT`
   - return Screen 2 payload as JSON

10. `screen_2_submit` — second entry path
   - merge clinician answers into state
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
    "extracted_value": "typed value or null",
    "sources": {},
    "justification": "string or null"
  }
}
```

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

Create a small Python helper for the two `PYTHON_CODE` blocks:
- `screen2_state_helpers.py`
  - `merge_criterion_result(...)`
  - `build_screen2_payload(...)`
  - `build_screen3_payload(...)`

This will keep block-level Python concise and easier to debug in DSS.
