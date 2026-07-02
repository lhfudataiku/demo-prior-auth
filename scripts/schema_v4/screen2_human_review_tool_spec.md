# Screen 2 Human Review Tool Spec

## Purpose

This managed custom Python tool is the POC human-in-the-loop boundary between
Screen 2 evidence review and deterministic downstream Screen 3 generation.

POC guardrail:
- Don't overcode. This is a POC.

The Structured Agent calls this tool after building the Screen 2 payload. The
tool must be configured in DSS with human approval before execution so the
reviewer can inspect the payload and, when enabled, edit criterion answers.

## Dataiku tool configuration

Required setting:
- enable `Enforce human approval before making tool call`

Recommended setting:
- allow humans to edit tool inputs before approval, if available in the target
  DSS version

Tool type:
- managed custom Python agent tool

Implementation:
- `scripts/agent_flow/agent_tools/screen2_human_review_tool.py`
- class: `Screen2HumanReviewTool`

Invocation:
- direct tool call from the Structured Agent after
  `prepare_screen_2_review_payload`
- in DSS 14.5, use a `CORE_LOOP` block with
  `scripts/agent_flow/agents/review_request_agent_prompt.md`
- the core loop must wrap the prepared state object under
  `review_request` and pass it through unchanged

Runtime note:
- this tool spec defines the review payload shape for the native DSS approval
  path
- the same answer-map shape should also be reused by a standard webapp submit
  path, even when the managed approval UI is bypassed

## Input schema

```json
{
  "review_request": {
    "session_id": "optional string correlation id",
    "subject_id": "string",
    "policy_id": "string",
    "selected_scope": {
      "selected_route_id": "string",
      "selected_phase": "initial | continuation | other",
      "selected_cluster_id": "string"
    },
    "screen_2_payload": {},
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

Notes:
- `session_id` is optional for the POC and acts only as a correlation id for
  tracing or webapp request linkage.
- the tool should reject calls that omit required nested fields such as
  `screen_2_payload` or `criterion_answers`.
- `criterion_answers` is the pre-approval working clinician-input map

## Output schema

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
  }
}
```

## Behavior

- Return `approval_status = approved` when the reviewer accepts the payload
  without changing criterion answers.
- Return `approval_status = edited` when the reviewer changes one or more
  criterion answers.
- Return `approval_status = rejected` when the reviewer declines to proceed.
- Do not call an LLM.
- Do not perform chart retrieval.
- Do not change `criterion_result_map`.
- Treat returned answers as clinician input for
  `build_criterion_ui_map(...)`.
- Let the backend/webapp layer deterministically recompute conflicts,
  completeness, and Screen 3 payloads after approval.
- `approved_criterion_answers` is the approved snapshot of clinician input and
  should keep the same inner schema as `criterion_answers`.

## POC implementation note

For the first build, the tool can act as a simple pass-through after approval:
it receives the Screen 2 payload and returns the approved or edited
`criterion_answers`. The value is in the DSS-managed approval checkpoint, not in
complex tool logic.
