# PROJECT_CONTEXT

Don't overcode. This is a POC.

## Project Goal

This repo contains a prior-authorization POC with:

- a deterministic Screen 1 scope-selection flow
- a clinician-facing Vue webapp for Screen 1, Screen 2, and Screen 3
- explicit `local` and `dss` runtime paths in the webapp backend
- fixture-backed local development plus a live DSS Structured Agent path
- a native DSS human-in-the-loop review flow for Screen 2

## Current Status

The project has moved beyond the earlier fixture-only Screen 2 review scaffold.

Current state on branch `webapp-clean`:

- Screen 1 is implemented as a deterministic backend-driven flow with:
  - patient selection
  - policy selection
  - billing code selection
  - phase selection when required
  - cluster selection
  - route-guard and cluster-entry-guard questions
- Screen 2 supports 2 operational paths:
  - `local`
    - synchronous bootstrap from fixture/static artifacts
    - direct clinician editing in the webapp
    - deterministic Screen 3 generation in backend utils
  - `dss`
    - starts a live Structured Agent run
    - polls normalized run state from the backend
    - shows streamed block/criterion progress while the agent runs
    - renders the paused human-review payload when HITL is reached
    - resumes the same run after clinician approval or edits
- Screen 3 is produced deterministically from reviewed answers and current
  Screen 2 payload state
- the frontend UI has been tightened for Screen 1 and Screen 2 and now treats
  async DSS progress as a first-class state, not an afterthought

## Current Architecture

### Webapp

Location:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review`

Frontend:

- Vue 3 + Pinia + Vite application
- workflow pages/components for:
  - Screen 1 scope selection
  - Screen 2 eligibility review
  - Screen 3 final submission review
- store-driven runtime handling in:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/stores/priorAuthStore.ts`
- built frontend assets are committed under:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/dist`
  - required by `WEBAIKU` / DSS hosting flow

Backend:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/backend.py`
  - Flask API routes
  - Screen 1 bootstrap/advance endpoints
  - local Screen 2 bootstrap endpoint
  - DSS Screen 2 run start / poll / HITL resume endpoints
  - streaming-event normalization for frontend progress display
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`
  - explicit data source access layer
  - separate `local` and `dss` code paths
  - policy/patient loaders
  - Structured Agent request builder
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/utils.py`
  - selected-scope display helpers
  - patient age enrichment
  - clinician answer merge logic
  - deterministic Screen 3 payload generation
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`
  - local launcher
  - serves API-only when `webaiku` is unavailable
  - serves built frontend when `webaiku` and `dist` are available
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi.py`
  - DSS / `WEBAIKU` launcher

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

Configured in backend code as an explicit runtime value:

- `local`
- `dss`

Behavior:

- `local`
  - reads local CSV / JSON artifacts
  - supports synchronous Screen 2 bootstrap
- `dss`
  - reads DSS datasets and uses DSS objects
  - starts and resumes live Structured Agent runs
  - no silent fallback to local

This mode selection is implemented in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`

Important current note:

- `DATA_SOURCE` is currently a code-level constant in `data_access.py`
- helper functions still accept an optional explicit `data_source`
- current code no longer centers the mode switch around environment-variable
  configuration

### 2. Screen 2 review runtime pattern

Both patterns are still part of the documented product model:

- native DSS approval mode
- standard webapp review mode

Current implemented behavior in the webapp/backend:

- `local` mode effectively exercises the standard webapp review path
- `dss` mode exercises the live run-based native DSS approval path
- both paths use the same clinician answer-map shape

## Important Runtime Values

- Structured Agent id: `NkBiV9OM`
- Structured Agent version: `v2`
- patient dataset name constant: `Patient`
- policy artifacts dataset name constant: `policy_artifacts`
- `VITE_API_PORT`
  - used by the local launcher

Referenced in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`

## Current Data Access Behavior

### Local mode

Reads from:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/Patient.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/policy_artifacts.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/<policy_id>/*.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/<policy_id>/structured_agent_context.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/screen_payloads/<policy_id>/screen_2_response.json`

Behavior:

- prefers `structured_agent_context.json` when it contains `screen_2_payload`
- falls back to the older `screen_2_response.json` fixture only when needed

### DSS mode

Reads from:

- DSS dataset `Patient`
- DSS dataset `policy_artifacts`
- DSS Structured Agent `NkBiV9OM` / `v2`

Behavior:

- builds a fresh Screen 2 agent request from current Screen 1 scope
- starts a streamed completion for Screen 2 runs
- extracts graph state, HITL review request data, partial Screen 2 snapshots,
  criterion answers, and progress from the stream

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

Important endpoint split:

- `POST /api/scenarios/<policy_id>/bootstrap`
  - local-only Screen 2 bootstrap
- `POST /api/scenarios/<policy_id>/screen2/run`
  - dss-only Screen 2 run start

## Screen Workflow

### Screen 1

Purpose:

- collect:
  - patient id
  - policy
  - billing code
  - phase
  - disease cluster
  - route-guard answers
  - cluster-entry-guard answers
- end in `selected_scope_context`

Important principles:

- Screen 1 produces the canonical scope handoff for Screen 2
- Screen 2 requests should derive `selected_scope_context` deterministically
  from current selection inputs
- skipped guard answers remain unanswered rather than being forced to `false`

Core logic:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/agent_flow/functions/selection_resolver.py`

### Screen 2

Purpose:

- render chart-backed criterion review
- preserve Screen 1-carried answers
- merge clinician edits
- support live DSS run progress and HITL pause/resume
- derive criteria count from
  `selected_scope_context.selected_criteria_catalog`

Current webapp behavior:

- if the DSS run is still executing, the frontend can render:
  - agent status
  - current block
  - current criterion id
  - current criterion prompt
  - completed vs total criteria
- if the run pauses for human validation, the frontend renders the paused
  Screen 2 review payload using the same criterion-card model as local mode
- if the Screen 2 payload has not arrived yet, placeholder criterion rows can
  still be derived from `selected_scope_context.selected_criteria_catalog`

### Screen 3

Purpose:

- deterministic final summary after clinician review

Current backend merge logic:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/utils.py`

Current behavior:

- merges approved answers into the current Screen 2 payload
- recalculates criterion status buckets
- emits warnings for clinician/chart conflicts
- determines submission readiness from unanswered required items and conflicts

## Answer Map Semantics

Keep both names:

- `criterion_answers`
  - working clinician-input state
  - includes Screen 1 guard answers carried into Screen 2
- `approved_criterion_answers`
  - approved/submitted snapshot at review time

Same inner schema, different lifecycle stage.

## Human-In-The-Loop Clarification

Critical transition remains between the Screen 2 review request and Screen 3
recomputation.

Conceptually:

- the Structured Agent builds a review request and pauses
- the webapp renders that paused request
- clinician approval or edits are returned through HITL resume
- the same run then continues to final Screen 3 output

Important docs:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_structured_agent_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/screen2_human_review_tool_spec.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/schema_v4/frontend_webapp_contract_v1.md`

## DSS Standard Webapp Integration

Current direction:

- use `WEBAIKU`
- local launcher:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`
- DSS launcher:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi.py`

Current implementation note:

- local development supports 2 practical modes:
  - API-only Flask backend + Vite frontend
  - built frontend served through `WEBAIKU` when available
- DSS expects the committed `dist` bundle for hosted webapp delivery
