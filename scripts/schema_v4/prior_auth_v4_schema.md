# Prior Auth V4 Schema Notes

## Purpose

This file is now a lightweight index for the V4 documentation set.

The earlier version of this document duplicated material that is now maintained
more clearly in the framework document, the Structured Agent spec, and the
parser prompt. For the POC, those files should be treated as the canonical
sources.

## Canonical document roles

### 1. High-level architecture and workflow
- `scripts/schema_v4/prior-auth_assistant.md`
- owns project scope, webapp flow, component ownership, Screen 1 versus Screen
  2/3 responsibilities, and the Screen 1 -> Screen 2 handoff contract

### 2. Technical Structured Agent build spec
- `scripts/schema_v4/screen2_structured_agent_spec.md`
- owns the Screen 2 / Screen 3 request and response contracts, state keys,
  block graph, deterministic helper usage, and submit-path behavior

### 3. Screen 2 human review tool contract
- `scripts/schema_v4/screen2_human_review_tool_spec.md`
- owns the managed custom Python tool contract for approval-enabled Screen 2
  review

### 4. Executable parser schema contract
- `scripts/agent_flow/agents/policy_parser_agent_prompt_v4_1.md`
- owns the operational schema definition for `policy_master_v4`, including how
  routes, route guards, cluster-entry guards, condition clusters, and criteria
  should be modeled at parse time

## Practical guidance

- If you are deciding how the webapp and agent system should behave, start with
  `scripts/schema_v4/prior-auth_assistant.md`.
- If you are implementing or debugging the Screen 2 Structured Agent in DSS,
  start with `scripts/schema_v4/screen2_structured_agent_spec.md`.
- If you are configuring the Screen 2 approval checkpoint, start with
  `scripts/schema_v4/screen2_human_review_tool_spec.md`.
- If you are changing how policies are parsed into `policy_master_v4`, update
  `scripts/agent_flow/agents/policy_parser_agent_prompt_v4_1.md`.
- Avoid reintroducing a third full schema narrative here unless we truly need a
  standalone external-facing schema reference.

## Related implementation files

- `scripts/agent_flow/agent_tools/screen2_human_review_tool.py`
- `scripts/agent_flow/functions/selection_resolver.py`
- `scripts/agent_flow/functions/route_index_builder.py`
- `scripts/agent_flow/functions/python_code_blocks.py`
- `scripts/agent_flow/agents/review_request_agent_prompt.md`
- `scripts/agent_flow/agents/retrieval_planner_agent_prompt_v1_1.md`
- `scripts/agent_flow/agents/criterion_reasoning_agent_prompt_v1_1.md`
