# Architecture

## Overview

```
                        ┌─────────────────────────┐
                        │   React + TS frontend    │
                        │   (dashboard, Step 6)    │
                        └────────────┬─────────────┘
                                     │ HTTPS / JWT bearer
                                     ▼
                        ┌─────────────────────────┐
                        │     FastAPI backend       │
                        │  (routers/, Step 3 & 7)   │
                        └─────┬──────────┬──────────┘
                              │          │
              ┌───────────────┘          └────────────────┐
              ▼                                            ▼
   ┌─────────────────────┐                     ┌───────────────────────┐
   │  OCR & extraction     │                     │  Compliance engine     │
   │  pipeline (Step 4)     │                    │  (Step 5)               │
   │  preprocess→OCR→       │───extracted_fields─▶│  rules JSON + fields   │
   │  field_classifier      │                    │  → violations/review   │
   └─────────────────────┘                     └───────────┬────────────┘
                                                             │
                                                             ▼
                                                ┌───────────────────────┐
                                                │  Reporting module       │
                                                │  (Step 7): PDF/DOCX,    │
                                                │  annotated evidence     │
                                                └───────────┬────────────┘
                                                             │
              ┌──────────────────────────────────────────────┘
              ▼
   ┌─────────────────────────────────────────────┐
   │  PostgreSQL (products, scans, violations,      │
   │  rule_versions, users) + local/object storage   │
   │  for uploaded label images                       │
   └─────────────────────────────────────────────┘
```

## Components

### Frontend (`frontend/`)
React + TypeScript + Vite + Tailwind SPA. Talks to the backend over HTTPS
with a JWT bearer token (see `src/lib/api.ts`, `src/lib/auth.tsx`).
No server-side rendering, no mock data layer — every screen is wired to
a real endpoint. See `frontend/README.md` for the route → endpoint table.

### Backend API (`backend/app/`)
FastAPI application. `main.py` wires up CORS, static file serving for
uploaded images (`/storage`), and mounts one router per resource
(`routers/auth.py`, `products.py`, `scans.py`, `violations.py`,
`rule_versions.py`, `reports.py`, `users.py`). Auth is JWT-based
(`auth.py`), with role checks (`require_role(...)`) enforced at the
dependency level on every mutating/sensitive endpoint — this is the
actual enforcement point; the frontend's role-gating is UX only.

### OCR & extraction pipeline (`backend/app/ocr/`)
Runs synchronously inside the `POST /scans/{id}/image` request (no queue
— see "Known limitations" below):

1. **`preprocessing.py`** — deskew, denoise, contrast enhancement (CLAHE),
   so a real phone photo of a label is OCR-able.
2. **`extraction.py`** — runs Tesseract, groups word-level OCR output into
   lines with a bounding box and per-line pixel height.
3. **`field_classifier.py`** — maps lines to the mandatory declaration
   categories (net quantity, MRP, manufacturer details, date, consumer
   care, etc.) via keyword anchoring and pattern matching, carrying
   forward each match's pixel bounding box for later evidence annotation.
4. **`pipeline.py`** — orchestrates the above and returns the `fields`
   dict that gets stored on `Scan.extracted_fields`.

### Compliance engine (`backend/app/compliance/engine.py`)
Pure function: `evaluate_scan(extracted_fields, rules, calibration_px_per_mm, context) -> ComplianceResult`.
Reads `rules/legal_metrology_rules.json` (never a hardcoded threshold —
see the module's own docstring) and produces three kinds of output:

- **violations** — concrete rule breaches, persisted as `Violation` rows.
- **review_items** — things it couldn't confidently decide (missing
  calibration, checks not yet automated, rules pending legal
  verification) — surfaced to an inspector rather than silently passed.
- **exempt / exemption_reason** — Chapter II exemption carve-outs.

Called from `routers/scans.py` after every image upload, calibration
update, or explicit `POST /scans/{id}/evaluate`.

### Reporting module (`backend/app/reports/`)
Builds a single `ReportData` snapshot (`data.py`) from a scan's stored
state, then renders it two ways: `pdf_report.py` (ReportLab, the locked
record copy) and `docx_report.py` (python-docx, editable for an
inspector to annotate). `annotate.py` draws evidence boxes on a copy of
the label image around any declaration tied to an open violation. Both
formats are generated on demand from live data — nothing is cached, so a
report always reflects the current resolution state.

### Data layer
PostgreSQL in Docker (SQLite locally with no extra setup — see
`app/database.py`). Schema and migrations are Alembic-managed
(`backend/migrations/`); see [`DATA_MODEL.md`](./DATA_MODEL.md) for the
ERD and field-level notes. Uploaded label images live on local disk
under `backend/app/storage/` (a deliberate stand-in for S3/MinIO — see
"Known limitations").

### Rule configuration (`rules/legal_metrology_rules.json`)
The single source of truth for every mandatory declaration, font-size
threshold, and exemption the compliance engine checks against, with a
rule ID and citation on every entry. Changes to this file don't take
effect until an admin calls `POST /rule-versions/sync-from-file`, which
hashes the file and registers/activates a `RuleVersion` row — this is
what keeps historical reports accurate after a rule amendment (a scan's
report always renders against the `RuleVersion` it was stamped with, not
whatever the file currently says). See
[`RULES_CONFIG.md`](./RULES_CONFIG.md) for the full format and the
amend-and-roll-forward workflow.

## Request flow: image in → report out

1. Inspector logs in (`POST /auth/login`) → gets a JWT.
2. Inspector creates a `Product` (if new) and a `Scan` against it
   (`POST /products`, `POST /scans`) — the scan is stamped with whichever
   `RuleVersion` is currently active.
3. Inspector uploads a label photo (`POST /scans/{id}/image`):
   OCR pipeline runs → `extracted_fields` stored → compliance engine runs
   automatically → `Violation` rows + `compliance_review` written →
   scan status becomes `review`.
4. Inspector/supervisor sets the px/mm calibration if not already known
   (`PATCH /scans/{id}`) — this re-triggers the compliance engine so
   font-size checks that were skipped now run.
5. Inspector/supervisor triages violations (`GET/PATCH /violations`) —
   confirm, annotate, or resolve as the seller corrects the label.
6. Anyone with access downloads a report (`GET /scans/{id}/report?format=pdf|docx`)
   — built fresh from the scan's current state every time.

## Known limitations (flagged for wider rollout, not blocking a pilot)

- **Synchronous OCR** — a label photo is processed inline within the
  upload request. Fine at pilot volume; a real enforcement rollout
  processing many scans concurrently should move this to a background
  job queue (Celery/RQ + Redis) so uploads return immediately and OCR
  runs asynchronously.
- **Local-disk image storage** — `backend/app/storage/` is a bind-mounted
  directory, not object storage. It works for a single-server pilot but
  doesn't scale horizontally and has no built-in redundancy. Swap for
  S3/MinIO before a multi-server or high-availability deployment
  (`routers/scans.py`'s `STORAGE_DIR` and `main.py`'s `/storage` mount
  are the two places that would change).
- **No pagination** on `/products`, `/scans`, `/violations` list
  endpoints — fine at pilot scale (tens to low hundreds of records),
  worth adding (`?limit=&offset=` or cursor-based) once volume grows.
