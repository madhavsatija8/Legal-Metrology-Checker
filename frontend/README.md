# Frontend — Compliance Register (Step 6)

React + TypeScript + Vite + Tailwind, talking directly to the FastAPI
backend in `../backend`. No mock data — every screen is wired to the
real endpoints documented in the backend's README/`/docs`.

## Screens

| Route | What it does | Endpoints used |
|---|---|---|
| `/login` | Sign in, stores the JWT | `POST /auth/login`, `GET /auth/me` |
| `/products` | Search + create products | `GET/POST /products` |
| `/products/:id` | Edit a product, see its scan history, start a new scan | `GET/PATCH /products/{id}`, `GET /scans?product_id=`, `POST /scans` |
| `/scans` | Feed of all scans, filterable by status | `GET /scans` |
| `/scans/:id` | Upload a label photo, view OCR'd fields, set px/mm calibration, re-run the compliance engine, resolve violations | `POST /scans/{id}/image`, `PATCH /scans/{id}`, `POST /scans/{id}/evaluate`, `PATCH /violations/{id}` |
| `/violations` | Cross-scan violation dashboard, filter by severity/resolved | `GET /violations` |
| `/rule-versions` (admin) | See which rule config is active, sync a new one | `GET /rule-versions`, `POST /rule-versions/sync-from-file` |
| `/users` (admin) | Manage roles and account status | `GET/PATCH /users`, `POST /auth/register` |

Role-gated UI (edit product, set calibration, admin pages) mirrors the
backend's `require_role(...)` checks — but the backend is the real
enforcement point; the frontend just hides actions a role can't use.

## Running locally

Requires Node 18+.

```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000 by default
npm run dev
```

Then open http://localhost:5173. Sign in with a seeded account (see the
backend README), e.g. `inspector@metrology.gov.in` / `inspector123`.

Make sure the backend is running first (`uvicorn app.main:app --reload`
from `backend/`) — it now has CORS enabled for `http://localhost:5173`
and serves uploaded label images at `/storage/<filename>` (both added
alongside this frontend; see `backend/app/main.py`).

## Building for production

```bash
npm run build   # outputs static files to dist/
npm run preview # sanity-check the build locally
```

`dist/` is a static bundle — serve it from nginx/any static host, and
point `VITE_API_URL` at wherever the backend is actually deployed
(baked in at build time, since Vite env vars aren't runtime-configurable).

## Design notes

The palette and type system (see `tailwind.config.js`) deliberately
avoid generic dashboard defaults: a warm ledger-paper background, a
serif for headings (this is a legal/enforcement tool, not a SaaS
product), and severity/status shown as left-bordered tags rather than
filled pills. Extend `tailwind.config.js`'s `colors`/`fontFamily`
rather than hardcoding new colors in components.

## What's not done yet

- No pagination on `/products`, `/scans`, `/violations` lists — fine at
  pilot scale, worth adding if the product/scan count grows.
- No client-side form validation beyond HTML5 `required`/`type` — the
  backend's Pydantic validation is the real guard, this just improves UX.
- No toast/notification system — errors surface inline per-panel via
  `ErrorNote`, successes are implicit (the UI updates).
- Mobile app (React Native) reusing `src/lib/api.ts` and `types.ts` is
  the natural next step per the original project plan, once these web
  screens are validated against real scans.
