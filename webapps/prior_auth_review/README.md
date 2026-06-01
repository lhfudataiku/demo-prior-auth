# Prior Auth Review Webapp

Fixture-first Dataiku standard webapp for prior-authorization Screen 2 and
Screen 3 review.

## Purpose

This webapp lets us start frontend development against the frozen POC contract
while DSS Step 10 persistence debugging continues.

Current scope:
- load fixture-backed Screen 2 payloads
- allow clinician-style answer edits
- submit a deterministic review request
- render a deterministic Screen 3 summary

Source fixtures live under:
- `scripts/artifacts/fixtures/screen_payloads`

## Structure

- `backend/backend.py`: fixture-backed Flask routes
- `backend/wsgi.py`: local development entry point
- `src/Api.ts`: typed API contract
- `src/stores/priorAuthStore.ts`: scenario loading and review state
- `src/components/`: Screen 2 / Screen 3 UI pieces

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

Expected local ports:
- frontend: `5173`
- backend: `5001`

## Fixture API

- `GET /api/scenarios`
- `GET /api/scenarios/<policy_id>/bootstrap`
- `POST /api/scenarios/<policy_id>/review`

## Notes

- This scaffold is intentionally fixture-first.
- Live DSS integration can replace the fixture endpoints later without changing
  the frontend contract.
