# PROJECT_CONTEXT

Don't overcode. This is a POC.

## Project Goal

This repo contains a prior-authorization POC with:

- a Dataiku Structured Agent flow for Screen 2 reasoning and human review
- a Dataiku standard webapp for Screen 1 / review / summary UI
- local fixture support for design-time development
- a path toward DSS-backed datasets and a live Structured Agent call

## Current Architecture

### Webapp

Location:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review`

Frontend:

- Vue app for the clinician workflow
- current UI is considered good enough for POC iteration

Backend:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/backend.py`
  - route/controller layer only
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/utils.py`
  - pure transforms and review merge logic
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`
  - explicit data source access layer
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`
  - local launcher
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi.py`
  - DSS / `webaiku` launcher

### Structured Agent / Artifacts

Core helper code:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/agent_flow/functions`

Artifacts and fixtures:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts`

Schema / scoping docs:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4`

## Runtime Modes

There are 2 important distinctions.

### 1. Webapp data source mode

Configured as a simple runtime value:

- `local`
- `dss`

Behavior:

- `local`
  - reads local CSV / JSON artifacts
- `dss`
  - reads DSS datasets and uses DSS objects
  - no silent fallback to local

This mode selection is implemented in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`

Current cleanup direction:

- callers should be able to pass the data source explicitly into backend helpers
- env-var fallback can remain for local convenience, but DSS integration should
  not depend on a system variable as the primary control path

### 2. Screen 2 review runtime mode

Documented in the schema docs:

- native DSS approval mode
- standard webapp review mode

Current recommendation:

- keep both documented
- native DSS mode demonstrates human-in-the-loop capability
- standard webapp mode is simpler operationally

Current implementation direction:

- `local` mode keeps a synchronous Screen 2 bootstrap path for fixture/static
  UI and backend testing
- `dss` mode uses an independent asynchronous run/session path so the webapp
  can display streamed Structured Agent workflow and resume after required human
  validation

## Important Environment Variables

- `PRIOR_AUTH_PATIENT_DATASET`
  - defaults to `Patient`
- `PRIOR_AUTH_POLICY_ARTIFACTS_DATASET`
  - defaults to `policy_artifacts`
- `VITE_API_PORT`
  - used by local launcher

## Structured Agent Target

Current live agent target:

- agent id: `NkBiV9OM`
- version: `v2`

Referenced in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`

## Current Data Access Behavior

### Local mode

Reads from:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/Patient.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/policy_artifacts.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/<policy_id>/*.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/screen_payloads/<policy_id>/screen_2_response.json`

### DSS mode

Reads from:

- DSS dataset `Patient`
- DSS dataset `policy_artifacts`
- DSS Structured Agent `NkBiV9OM` / `v2`

## Current Webapp Backend Endpoints

Implemented in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/backend.py`

Endpoints:

- `GET /api/scenarios`
- `GET /api/runtime`
- `GET /api/scenarios/<policy_id>/screen1/bootstrap`
- `POST /api/scenarios/<policy_id>/screen1/advance`
- `POST /api/scenarios/<policy_id>/bootstrap`
- `POST /api/scenarios/<policy_id>/review`
- `POST /api/scenarios/<policy_id>/screen2/run`
- `GET /api/runs/<run_id>/state`
- `POST /api/runs/<run_id>/hitl/respond`
- `GET /api/patients/<subject_id>`

## Screen Workflow

### Screen 1

Purpose:

- collect:
  - patient id
  - policy
  - billing code
  - phase
  - disease cluster
- ends in `selected_scope_context`

Important principle:

- Screen 1 should produce `selected_scope_context`
- Screen 2 consumes that artifact / state

Core logic:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/agent_flow/functions/selection_resolver.py`

Current backend rule:

- live Screen 2 / review requests should derive `selected_scope_context`
  deterministically from the current Screen 1 selection inputs
- do not depend on saved `selected_scope_context` artifacts for the standard
  webapp runtime path

### Screen 2

Purpose:

- render chart-backed criterion review
- merge clinician edits
- support review / approval flow

Current POC source:

- `local` mode
  - synchronous bootstrap from fixture/static payloads
- `dss` mode
  - start a Structured Agent run
  - stream workflow state to the webapp
  - pause at the required human-validation step
  - resume the same run after clinician approval/edit

### Screen 3

Purpose:

- deterministic final summary after clinician review

Current backend merge logic:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/utils.py`

## Answer Map Semantics

Keep both names:

- `criterion_answers`
  - working clinician-input state
- `approved_criterion_answers`
  - approved/submitted snapshot

Same inner schema, different lifecycle stage.

## Human-In-The-Loop Clarification

Critical transition is between Structured Agent Step 10 and Step 11.

Conceptually:

- Step 10 is the human review boundary
- Step 11 consumes the approved review snapshot and recomputes deterministically

Important docs:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_structured_agent_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_human_review_tool_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/frontend_webapp_contract_v1.md`

## DSS Standard Webapp Integration

Current direction:

- use `webaiku`
- local launcher:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`
- DSS launcher:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi.py`

Expected DSS backend integration pattern:

- `WEBAIKU(app, "webapps/prior_auth_review/dist")`
- `WEBAIKU.extend(app, [api])`

## What Was Just Refactored

Recently completed:

- backend cleanup into:
  - `backend.py`
  - `utils.py`
  - `data_access.py`
- explicit env-var data source switch
- split local vs DSS launchers
- preserved POC behavior while reducing backend complexity

Validated:

- backend import/compile checks passed
- local smoke tests passed for the main API routes

## Known Gaps / Next Likely Work

1. Replace remaining artifact-based `selected_scope_context` assumptions in DSS mode with the true Screen 1 -> Structured Agent handoff.
2. Test `PRIOR_AUTH_DATA_SOURCE=dss` against real DSS datasets.
3. Test the live Structured Agent call end-to-end in DSS.
4. Finalize the standard webapp packaging details (`body.html`, static assets, JS wrapper) if needed.
5. Keep schema docs aligned with any runtime/API changes.

## Local Run Commands

Backend:

```bash
cd /Users/li-hengfu/Documents/GitHub/demo-prior-auth
PRIOR_AUTH_DATA_SOURCE=local webapps/prior_auth_review/.venv/bin/python webapps/prior_auth_review/backend/wsgi_local.py
```

Frontend:

```bash
cd /Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review
npm run dev
```

## Primary Scoping Docs

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/prior-auth_assistant.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/frontend_webapp_contract_v1.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_structured_agent_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_human_review_tool_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/prior-auth_assistant_flowchart.md`

## Guiding Principle

Keep the code and runtime model simple.

Don't overcode. This is a POC.
