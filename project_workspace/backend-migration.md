# Migrate `prior_auth_review` webapp: Flask + webaiku → FastAPI (bs-blueprint style)

## Context

The `DEMO_PRIOR_AUTH_AGENT` webapp renders a blank page in DSS. Root cause (already
proven): the app is served through the **webaiku** `ServeBlueprint`, which rewrites
`index.html` with an injected `<base href>` derived from a `?URL=` query param the
iframe never sends → `<base href="None/">` → the JS bundle 404s → blank page. Locally
it works only because `npm run dev` (Vite) serves the app and webaiku is never in the path.

The reference framework `~/Documents/GitHub/bs-blueprint` solved this by **dropping
webaiku entirely**: a FastAPI backend serves the SPA directly (untouched `index.html`,
`/assets` mounted, SPA fallback) and the DSS iframe uses a plain `getWebAppBackendUrl('')`.
This migration ports `prior_auth_review` onto that proven pattern.

> **Note:** Before this full migration, a **minimal Flask-static fix** was applied first
> (serve `dist/` directly from Flask, drop webaiku's `ServeBlueprint`, plain iframe). If that
> minimal fix is sufficient in production, this FastAPI migration becomes an optional
> follow-up for full alignment with the `bs-blueprint` framework.

**Decisions (confirmed with user):**
- **Keep the repo layout.** Stay under `webapps/prior_auth_review/`, keep importing
  `scripts.agent_flow.functions.*` and reading `scripts/artifacts/` fixtures via the
  existing whole-repo project-library sync. No `LIB_NS` repackage, no `deploy.sh`/`app.env`/
  `Makefile` framework files.
- **Rebuild the DSS agent flow as SSE streaming**, replacing the background-thread +
  module-global run-store + 2s polling model.

**Outcome:** webapp renders in DSS, served by FastAPI; agent runs stream live via SSE;
local dev unchanged (Vite + FastAPI dev server).

## Backend changes (`webapps/prior_auth_review/backend/`)

Convert the Flask app to FastAPI. `data_access.py` and `utils.py` are framework-agnostic
(no Flask imports) — they stay as-is except one config wiring change. The bulk of work is
`backend.py` (`flask` → FastAPI) plus new `app.py`/`config.py` and the DSS entry.

### New: `backend/config.py`
Mirror `bs-blueprint/backend/config.py` (env-driven), minimal surface:
- `DSS_MODE = bool(os.environ.get("PRIOR_AUTH_DSS_MODE"))`
- `DATA_SOURCE = os.environ.get("PRIOR_AUTH_DATA_SOURCE", "dss" if DSS_MODE else "local")`
- `CORS_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`)
- `LOG_LEVEL`

Wire `data_access.py:22`'s hardcoded `DATA_SOURCE = "local"` to read `config.DATA_SOURCE`
(currently it's always `"local"` — this is why dss-mode paths never activate today).

### New: `backend/app.py` — the `configure(app)` factory
Follow `bs-blueprint/backend/app.py` exactly:
- `app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, ...)`
- `app.include_router(api_router)` (the ported routes)
- **Static SPA serving, DSS only** (`if config.DSS_MODE`): `_find_dist_dir()` → `dist/`;
  `app.mount("/assets", StaticFiles(directory=dist/"assets"))`; serve root files; SPA
  fallback `@app.get("/{path:path}") -> FileResponse(dist/"index.html")`.
- Module-level `app = FastAPI(); configure(app)` for local `uvicorn`.

### Rewrite: `backend/backend.py` → FastAPI `APIRouter`
`api = Blueprint("...", url_prefix="/api")` → `router = APIRouter(prefix="/api")`. Mechanical
per-route conversion (reuse ALL existing helper functions and the `scripts.agent_flow` /
`data_access` / `utils` calls unchanged — only the HTTP framing changes):
- `@api.route(path, methods=["GET"])` → `@router.get(path)`, `POST` → `@router.post(path)`
- `request.get_json(force=True) or {}` → a Pydantic body model or `body: dict = Body(...)`
- `jsonify(x)` → `return x`; `return jsonify(...), 404` → `raise HTTPException(404, detail=...)`
- Path args `<policy_id>` → `{policy_id}` typed params.

**Plain JSON routes (port 1:1):** `GET /api/runtime`, `GET /api/scenarios`,
`GET /api/scenarios/{policy_id}/screen1/bootstrap`, `POST .../screen1/advance`,
`POST .../bootstrap` (local), `POST .../review` (local), `GET /api/patients/{subject_id}`.

**Drop:** the `compat` blueprint (`/first_api_call`, `/dist/<path>`) — webaiku legacy;
FastAPI now serves `dist/` natively. Also drop `GET /api/runs/{run_id}/state` (polling).

### SSE rebuild of the agent flow (the hard part)
Replace `start_screen2_run` + `_run_dss_completion` (threads/`_runs`/`_run_lock`) + poll
endpoint with two streaming endpoints. Use FastAPI **`StreamingResponse` with a sync
generator** (`media_type="text/event-stream"`) — this lets us reuse the existing sync
`completion.execute_streamed()` loop almost verbatim (FastAPI iterates sync generators in
the threadpool), converting each `_runs[run_id].update(...)` mutation point into a
`yield _sse(event, data)`. No asyncio bridging, no new dependency.

- `POST /api/scenarios/{policy_id}/screen2/run` (dss only) → `StreamingResponse` that:
  builds the agent request (existing `_build_screen2_agent_request`), opens the LLM
  completion, iterates chunks, and yields SSE events: `progress`, `screen2` (snapshot +
  `criterion_answers`), and terminal `hitl_required` **or** `completed`/`error`.
- **HITL over SSE:** on `hitl_required`, stash the resume context
  (`memory_fragment`, `hitl_requests`, `original_query`, `context`, `review_request`) in a
  small in-memory `_runs[run_id]` dict (resume-context only, not for polling), emit the
  event with `run_id` + review payload, and end the stream.
- `POST /api/runs/{run_id}/hitl/respond` (dss only) → `StreamingResponse` that loads the
  stashed context, resumes the completion (reusing the existing HITL-resume message
  assembly in `_run_dss_completion` lines ~383-404 and `_build_review_result`), streams
  events, and ends with `completed`/`error`.

Event contract (SSE `event:` / JSON `data:`): `progress`, `screen2`, `hitl_required`,
`completed`, `error`. Reuse the existing extractors verbatim: `_extract_stream_state`,
`_extract_progress_from_graph`, `_extract_review_request_from_*`,
`build_screen3_payload_from_review_result_data`, `normalize_review_result_data`.

### Dependencies / entry points
- `requirements.txt`: drop `Flask`; add `fastapi>=0.100.0`, `uvicorn[standard]>=0.20.0`.
  Remove `webaiku` usage. (StreamingResponse needs no extra dep.)
- Delete `wsgi.py` (webaiku entry). Replace `wsgi_local.py` with a uvicorn launch
  (`uvicorn webapps.prior_auth_review.backend.app:app --reload --port 5001`) or a thin runner.
- The DSS **code env** `demo_prior-auth` must contain `fastapi` + `uvicorn[standard]`
  (verify/add via `dku code-env`). Requires **DSS 14.4+** for native FASTAPI (bs-blueprint
  already runs FASTAPI on this same instance, so this holds — confirm in verification).

## Frontend changes (`webapps/prior_auth_review/src/`)

Vite config already builds `--base=./` single-bundle — compatible; no build changes needed.

- **`src/api/index.ts`** — replace the `getWebAppBackendUrl`-based axios `baseURL` with the
  blueprint's iframe-safe pattern: add `src/utils/embeddedBase.ts` (copy
  `bs-blueprint/frontend/src/utils/embeddedBase.ts`) and set axios `baseURL` =
  `embeddedBasePath()` when `window.self !== window.top`, else `''` (dev proxy). This is the
  load-bearing fix that makes `/api` calls resolve inside the DSS iframe.
- **`src/Api.ts` + `src/stores/priorAuthStore.ts`** — replace polling with SSE:
  - `startScreen2Run` / `respondHitl` become SSE consumers using `fetch()` +
    `ReadableStream` reader + `TextDecoder` (EventSource can't POST a body), parsing
    `event:`/`data:` frames.
  - In the store, remove `pollTimer` / `pollRunState` / 2s `setInterval` and the
    `getRunState` call; drive state transitions from streamed events (`progress` → progress
    UI, `screen2` → snapshot/answers, `hitl_required` → review UI, `completed` → screen 3,
    `error` → error). Keep the existing `currentPage` / answer-tracking logic.

## DSS deploy glue (`webapps/prior_auth_review/dss/`)

Adopt the blueprint's `dss_webapp/` shape; keep the existing sync-script mechanism.
- **`standard-webapp.definition.patch.json`**: set `backendFramework: "FASTAPI"`, keep
  `backendEnabled/autoStartBackend: true`, add `envSelection: {envMode: "EXPLICIT_ENV",
  envName: "demo_prior-auth"}`; **revert the `?URL=` change** — `js` becomes the plain
  blueprint iframe (`ifrm.src = getWebAppBackendUrl('')`); `html` = `<div id="app-frame"></div>`;
  `css` = body reset; `python` = new FastAPI entry (below).
- **`python` tab** (keep-repo-layout entry): sets env then configures the injected app:
  ```python
  import os
  os.environ["PRIOR_AUTH_DSS_MODE"] = "1"
  from webapps.prior_auth_review.backend.app import configure
  configure(app)  # `app` injected by DSS as a FastAPI instance
  ```
- **`sync_standard_webapp_definition.sh`**: unchanged mechanism (merge patch → `set-definition`);
  since we keep the repo layout, backend source + `dist/` continue to arrive via the
  existing whole-repo project-library sync (the user already syncs it). Deploy =
  build frontend → sync library → run sync script → restart webapp.

## Critical files

- Rewrite: `webapps/prior_auth_review/backend/backend.py`
- New: `webapps/prior_auth_review/backend/app.py`, `backend/config.py`
- Edit: `webapps/prior_auth_review/backend/data_access.py` (line 22 → config-driven)
- Delete/replace: `backend/wsgi.py`, `backend/wsgi_local.py`
- Edit: `requirements.txt` (drop Flask/webaiku, add fastapi/uvicorn)
- Edit: `src/api/index.ts`; New: `src/utils/embeddedBase.ts`
- Edit: `src/Api.ts`, `src/stores/priorAuthStore.ts` (SSE)
- Edit: `dss/standard-webapp.definition.patch.json` (FASTAPI + glue)
- Reference (copy patterns, do not modify): `bs-blueprint/backend/app.py`,
  `bs-blueprint/frontend/src/utils/{api,embeddedBase}.ts`, `bs-blueprint/dss_webapp/*`.

## Verification (end-to-end)

1. **Local backend:** `uvicorn webapps.prior_auth_review.backend.app:app --port 5001`;
   `curl localhost:5001/api/runtime` → `{"data_source":"local"}`; `curl /api/scenarios` → items.
2. **Local frontend:** `npm run dev`; load via Claude Preview browser; confirm Screen 1
   renders and advances (same as today's working local render).
3. **Build:** `npm run build` clean; `npm run type-check` clean.
4. **DSS code env:** confirm `demo_prior-auth` has `fastapi`+`uvicorn` (`dku code-env get`),
   add if missing; confirm instance is DSS 14.4+.
5. **Deploy:** sync library (whole-repo) → run `dss/sync_standard_webapp_definition.sh
   DEMO_PRIOR_AUTH_AGENT Oa6EjMT` → `dku webapp restart Oa6EjMT`.
6. **DSS render (the actual fix):** reload the webapp; confirm via `dku webapp logs Oa6EjMT`
   that assets load 200 (`GET /assets/index-*.js 200`, no `None/`), and the SPA mounts
   (Screen 1 visible) instead of blank.
7. **Agent SSE (dss mode):** run a Screen 2 scenario; confirm streamed `progress` updates,
   a `hitl_required` pause with the review form, resume via `hitl/respond`, and a
   `completed` Screen 3 — all without the old 2s polling.

## Risks / notes

- **SSE + DSS WSGI/proxy:** the blueprint's webapps.md warns DSS production doesn't support
  websockets; SSE over plain HTTP streaming with FASTAPI/uvicorn is fine, but verify no
  buffering/timeout on the DSS proxy during a long agent run. If buffering appears, fall
  back to `sse-starlette` `EventSourceResponse` (blueprint's choice) or chunked flushing.
- **`scripts.agent_flow` import path in DSS:** relies on the project-library containing the
  repo (`project-python-libs/DEMO_PRIOR_AUTH_AGENT/python/scripts/...`), which the current
  deploy already provides — no change, but a hard dependency to keep in mind.
- **DSS version:** FASTAPI backend needs 14.4+. Confirmed indirectly (bs-blueprint targets
  the same instance); step 4 verifies explicitly.
