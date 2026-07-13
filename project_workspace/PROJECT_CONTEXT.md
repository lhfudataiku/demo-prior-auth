# PROJECT_CONTEXT

Don't overcode. This is a POC.

## Project Goal

This repo contains a release-stage prior-authorization POC with:

- a deterministic Screen 1 scope-selection flow
- a clinician-facing Vue webapp for Screen 1, Screen 2, and Screen 3
- explicit `local` and `dss` runtime paths in the webapp backend
- a live DSS Structured Agent path for Screen 2 reasoning and human review
- deterministic backend/webapp generation of Screen 3 after review

## Release Status

This project has reached release stage for the current POC scope.

What is complete:

- Screen 1 is implemented as deterministic backend logic with:
  - patient selection
  - policy selection
  - billing code selection
  - phase selection when required
  - cluster selection
  - route-guard and cluster-entry-guard questions
- Screen 2 is implemented in both runtime modes:
  - `local`
    - synchronous fixture/static bootstrap
    - clinician editing in the webapp
    - deterministic Screen 3 generation after submit
  - `dss`
    - live Structured Agent run start
    - run-state polling
    - streamed progress display
    - HITL pause at human review
    - resume after clinician approval or edits
- Screen 3 is fully deterministic and is no longer owned by the Structured
  Agent
- the frontend has release-ready workflow polish for:
  - consistent Screen 1 / Screen 2 CTA behavior
  - agent progress feedback
  - return from Screen 3 to a targeted Screen 2 criterion for re-editing
  - deterministic re-edit flow without involving the Structured Agent

What is intentionally true for this release:

- the Structured Agent ends with the reviewed Screen 2 artifact
  `screen_2_review_result`
- Screen 3 is built downstream from that reviewed artifact by deterministic
  helpers/backend logic
- this keeps the post-review output flexible for future targets such as FHIR or
  other transformation layers without changing the agent graph contract

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
- store-driven runtime/navigation handling in:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/stores/priorAuthStore.ts`
- committed built assets under:
  - `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/dist`
  - required by `WEBAIKU` / DSS hosting flow

Backend:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/backend.py`
  - Flask API routes
  - Screen 1 bootstrap/advance endpoints
  - local Screen 2 bootstrap endpoint
  - DSS Screen 2 run start / poll / HITL resume endpoints
  - normalization of live run state for the frontend
  - deterministic Screen 3 derivation from reviewed artifacts
  - in `dss` mode, resolves the Structured Agent from the current DSS project
    context rather than hard-coding a project key
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`
  - explicit data source access layer
  - separate `local` and `dss` code paths
  - policy/patient loaders
  - Structured Agent request builder
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/utils.py`
  - selected-scope display helpers
  - patient age enrichment
  - deterministic review merge / Screen 3 generation entry points
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

There are 2 important runtime distinctions.

### 1. Webapp data source mode

Configured in backend code as an explicit runtime value:

- `local`
- `dss`

Behavior:

- `local`
  - reads local CSV / JSON artifacts
  - supports synchronous Screen 2 bootstrap
  - supports deterministic Screen 3 generation on submit
- `dss`
  - reads DSS datasets and uses DSS objects
  - starts and resumes live Structured Agent runs
  - returns reviewed Screen 2 artifact data for deterministic downstream
    Screen 3 generation
  - no silent fallback to local

This mode selection is implemented in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`

Current note:

- `DATA_SOURCE` remains a code-level constant in `data_access.py`
- helper functions still accept an optional explicit `data_source`

### 2. Screen 2 review runtime pattern

Both documented product patterns remain valid:

- native DSS approval mode
- standard webapp review mode

Current implemented behavior:

- `local` mode exercises the standard webapp review path
- `dss` mode exercises the live run-based native DSS approval path
- both paths use the same clinician answer-map shape
- both paths end in deterministic Screen 3 generation outside the Structured
  Agent

## Important Runtime Values

- DSS project key: `DEMO_PRIOR_AUTH_AGENT`
- Structured Agent id: `NkBiV9OM`
- Structured Agent version: `v2`
- patient dataset name constant: `Patient`
- policy artifacts dataset name constant: `policy_artifacts`
- `VITE_API_PORT`
  - used by the local launcher

Referenced in:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/project_workspace/project_wiki/template/release_notes_v0.1.0.md`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/data_access.py`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/backend/wsgi_local.py`

Current deployment note:

- the deployed standard webapp and Structured Agent live in DSS project
  `DEMO_PRIOR_AUTH_AGENT`
- the backend currently uses the active/default DSS project context to resolve
  `agent:NkBiV9OM`
- this means the webapp and agent must be deployed together in the same DSS
  project context unless the backend resolution logic is made explicit

## Current Data Access Behavior

### Local mode

Reads from:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/Patient.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/policy_artifacts.csv`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/<policy_id>/*.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/policy_artifacts/<policy_id>/structured_agent_context.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/screen_payloads/<policy_id>/screen_2_response.json`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/scripts/artifacts/fixtures/screen_payloads/<policy_id>/screen_2_review_result.json`

Behavior:

- prefers `structured_agent_context.json` when it contains `screen_2_payload`
- falls back to older Screen 2 fixture payloads only when needed

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
- consumes the reviewed Screen 2 artifact after HITL resume
- builds Screen 3 deterministically in backend/helper code

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
- `POST /api/runs/<run_id>/hitl/respond`
  - dss-only HITL resume with deterministic downstream Screen 3 build

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
- Screen 2 requests derive `selected_scope_context` deterministically from the
  current selection inputs
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
- if the user returns from Screen 3 to Screen 2, the frontend can
  deterministically navigate to and re-highlight a targeted criterion without
  invoking the Structured Agent

### Screen 3

Purpose:

- deterministic final summary after clinician review

Current behavior:

- builds from the reviewed Screen 2 artifact and approved clinician answers
- recalculates criterion status buckets
- emits warnings for clinician/chart conflicts
- determines submission readiness from unanswered required items
- keeps clinician answers authoritative for final criterion status, while
  preserving override warnings for auditability

## Answer Map Semantics

Keep both names:

- `criterion_answers`
  - working clinician-input state
  - includes Screen 1 guard answers carried into Screen 2
- `approved_criterion_answers`
  - approved/submitted snapshot at review time

Same inner schema, different lifecycle stage.

## Human-In-The-Loop Clarification

The critical transition for the current release is between the Screen 2 review
request and the deterministic downstream transformation of the reviewed result.

Conceptually:

- the Structured Agent builds a review request and pauses
- the webapp renders that paused request
- clinician approval or edits are returned through HITL resume
- the Structured Agent emits the reviewed Screen 2 artifact
- backend/helper code deterministically builds Screen 3 from that artifact

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

## Release Notes

This release finalizes the current POC architecture with these important
boundaries:

- Screen 1 is deterministic backend logic
- Screen 2 reasoning and human review orchestration use the Structured Agent
- post-review output generation is deterministic and not owned by the
  Structured Agent
- `local` and `dss` remain explicit runtime modes
- the frontend supports deterministic re-entry from Screen 3 to Screen 2 for
  further clinician edits

For future work, treat the reviewed Screen 2 artifact as the stable handoff
object for downstream transformations.
