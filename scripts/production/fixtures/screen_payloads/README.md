Screen payload fixtures for webapp development.

Contents:
- one folder per policy artifact set
- `criterion_ui_map.json`
- `screen_2_response.json`
- `screen_3_response.json`

Source:
- generated from `structured_agent_context.json` under
  `scripts/production/policy_artifacts/<policy_id>/`

Refresh:
```bash
python3 scripts/production/functions/generate_screen_payload_fixtures.py
```
