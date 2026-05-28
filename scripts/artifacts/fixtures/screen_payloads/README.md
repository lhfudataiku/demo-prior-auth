Screen payload fixtures for webapp development.

Contents:
- one folder per policy artifact set
- `criterion_ui_map.json`
- `screen_2_response.json`
- `screen_2_review_result.json`
- `screen_3_response.json`

Source:
- generated from `structured_agent_context.json` under
  `scripts/artifacts/policy_artifacts/<policy_id>/`
- `screen_2_review_result.json` is a deterministic approved-review fixture
  derived from `screen_2_response.json` plus current `criterion_answers`

Refresh:
```bash
python3 scripts/agent_flow/functions/generate_screen_payload_fixtures.py
```
