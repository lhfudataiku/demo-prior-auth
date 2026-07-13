Screen payload fixtures for webapp development.

Contents:
- one folder per policy artifact set
- `selected_scope_context.json`
- `criterion_result_map.json`
- `criterion_ui_map.json`
- `screen_2_response.json`
- `screen_2_review_result.json`
- `screen_3_response.json`

Source:
- generated from saved Structured Agent contexts, currently under
  `scripts/artifacts/fixtures/structured_agent_requests/*_agent_context.json`
- `screen_2_review_result.json` is a deterministic approved-review fixture
  derived from `screen_2_response.json` plus current `criterion_answers`

Refresh:
```bash
python3 scripts/agent_flow/functions/generate_screen_payload_fixtures.py
```

To refresh from a newly saved ad hoc agent context:
```bash
python3 scripts/agent_flow/functions/generate_screen_payload_fixtures.py \
  --policy-id 0059 \
  --source scripts/artifacts/fixtures/structured_agent_requests/0059_agent_context.json
```
