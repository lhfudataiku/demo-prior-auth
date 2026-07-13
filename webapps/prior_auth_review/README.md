# Prior Auth Review Webapp

Fixture-first Dataiku standard webapp for prior-authorization Screen 2 and
Screen 3 review.

## Purpose

This webapp lets us start frontend development against the frozen POC contract
while DSS Step 10 persistence debugging continues.

Current scope:
- `local` mode:
  - load fixture-backed Screen 2 payloads
  - allow clinician-style answer edits
  - submit a deterministic review request
  - render a deterministic Screen 3 summary
- `dss` mode:
  - start a Structured Agent run
  - poll streamed workflow state
  - pause for required human validation
  - resume the same run after review

Source fixtures live under:
- `scripts/artifacts/fixtures/screen_payloads`

## Structure

- `backend/backend.py`: fixture-backed Flask routes
- `backend/wsgi.py`: local development entry point
- `src/Api.ts`: typed API contract
- `src/stores/priorAuthStore.ts`: scenario loading and review state
- `src/components/`: Screen 2 / Screen 3 UI pieces
- `dss/standard-webapp.definition.patch.json`: checked-in DSS standard webapp
  definition patch
- `dss/sync_standard_webapp_definition.sh`: CLI sync helper for the DSS webapp
  wrapper definition

## Local development

Backend:

```bash
python3 webapps/prior_auth_review/backend/wsgi_local.py
```

Frontend:

```bash
cd webapps/prior_auth_review
npm install
npm run dev
```

Built assets for `WEBAIKU`:

```bash
cd webapps/prior_auth_review
npm run build
```

Notes:
- `webapps/prior_auth_review/dist` is created by the Vite build step
- DSS and the local `WEBAIKU` shell both expect that `dist` folder to exist
- if `webaiku` or the DSS `dataiku` package is unavailable locally,
  `wsgi_local.py` falls back to serving the API only; use Vite for the frontend
- the deployed DSS standard-webapp wrapper is a separate definition from the
  backend/python code; keep it in sync with
  `dss/standard-webapp.definition.patch.json`

Expected local ports:
- frontend: `5173`
- backend: `5001`

## Backend API

- `GET /api/scenarios`
- `GET /api/runtime`
- `GET /api/scenarios/<policy_id>/screen1/bootstrap`
- `POST /api/scenarios/<policy_id>/screen1/advance`
- `POST /api/scenarios/<policy_id>/bootstrap`
- `POST /api/scenarios/<policy_id>/review`
- `POST /api/scenarios/<policy_id>/screen2/run`
- `GET /api/runs/<run_id>/state`
- `POST /api/runs/<run_id>/hitl/respond`

In `dss` mode, run state includes block-level streaming progress derived from
the Structured Agent context, so the frontend can show queue progress and the
current criterion while the agent is running.

## DSS standard webapp definition

The live DSS standard webapp wrapper for `Oa6EjMT` is not fully derived from
the Vite bundle or the Flask backend. Its browser-side `params.js` must also be
kept aligned.

Source of truth in this repo:

- `webapps/prior_auth_review/dss/standard-webapp.definition.patch.json`

Sync command after review:

```bash
webapps/prior_auth_review/dss/sync_standard_webapp_definition.sh DEMO_PRIOR_AUTH_AGENT Oa6EjMT
```

Important note:

- the current backend keeps compatibility routes for the legacy DSS wrapper
  paths `/first_api_call` and `/dist/...`
- this prevents blank-page failures while the deployed standard-webapp
  definition is still using the older bootstrap
- the long-term target is the simpler wrapper in
  `standard-webapp.definition.patch.json`, which iframes
  `dataiku.getWebAppBackendUrl('')` directly

## Notes

- This scaffold is intentionally fixture-first.
- `local` and `dss` are explicit runtime modes; do not silently fall back
  between them.
