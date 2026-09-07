# Legal Metrology Packaged Commodity Compliance Checker

Software system to check compliance of packaged commodities under the
Legal Metrology (Packaged Commodities) Rules, 2011, by scanning product
labels, images, and listings.

This repo is being built module by module, following the project plan.
So far this covers:
- **Step 1: project scaffold** — the backend service, database models,
  auth, and the digitized rule config.
- **Step 3: auth, database schema & core APIs** — Alembic migrations,
  full CRUD across products/scans/violations/rule-versions/users,
  role-based access control (inspector/supervisor/admin), and a seed
  script so the whole API is testable with no frontend.
- **Step 4: OCR & extraction pipeline** — image preprocessing (deskew,
  denoise, contrast), OCR via Tesseract, and field classification that
  maps extracted text to the mandatory declaration categories, wired
  into a `POST /scans/{scan_id}/image` upload endpoint. Verified against
  three concrete sample labels (clean, rotated/low-contrast, and one
  with genuinely missing fields) in `backend/tests/`. Each matched field
  also carries a pixel `bbox` (its OCR source line's bounding box), used
  by the Step 7 report generator to draw evidence boxes.
- **Step 5: compliance engine & readability checker** — reads
  `rules/legal_metrology_rules.json` plus a scan's extracted fields and
  produces violations (with rule citations), review items for anything
  it can't confidently decide, and exemption handling. Font-size checks
  convert pixel heights to millimetres via an inspector-supplied
  px/mm calibration (`app/compliance/engine.py`).
- **Step 6: frontend** — a React + TypeScript dashboard (upload, scan
  review, violations, product/rule-version management), wired directly
  to the tested API endpoints (`frontend/`).
- **Step 7: reporting module** — on-demand PDF and DOCX compliance
  reports generated from a scan's stored data via
  `GET /scans/{scan_id}/report?format=pdf|docx`
  (`backend/app/reports/`). Both formats are built from one shared
  `ReportData` snapshot (`reports/data.py`) so they can't drift apart,
  and include an annotated copy of the label image with evidence boxes
  drawn around any declaration tied to an open violation
  (`reports/annotate.py`). The PDF is the locked record copy; the DOCX
  is meant for an inspector to annotate before finalizing. Covered
  end-to-end (image in → report out) in
  `backend/tests/test_report_generation.py`. A "Download PDF" / "Download
  Word" pair on the scan detail page (`frontend/src/pages/ScanDetail.tsx`)
  calls this endpoint once a scan has extracted fields.
- **Step 8: testing, documentation & deployment** — a full API-level
  integration test suite (`backend/tests/test_api_e2e_pipeline.py`,
  `test_auth_rbac.py`) exercising image-in-to-report-out and role-based
  access over real HTTP, frontend smoke tests (`frontend/src/test/`),
  a CI workflow (`.github/workflows/ci.yml`), a production Docker
  Compose stack with Caddy/TLS (`docker-compose.prod.yml`,
  `Caddyfile`), and full docs in [`docs/`](./docs/) — see
  [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md),
  [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md),
  [`docs/RULES_CONFIG.md`](./docs/RULES_CONFIG.md),
  [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md), and
  [`docs/PILOT_CHECKLIST.md`](./docs/PILOT_CHECKLIST.md) (plus
  `backend/scripts/pilot_batch_check.py`, a standalone batch runner for
  validating against real products before wider rollout).

All eight steps of the original project plan are now covered. See
`docs/DEPLOYMENT.md` for how to actually stand this up somewhere real.

## Project structure

```
legal-metrology-checker/
├── backend/                 # FastAPI backend service
│   ├── app/
│   │   ├── main.py          # app entrypoint, mounts routers
│   │   ├── database.py      # SQLAlchemy engine/session setup
│   │   ├── models.py        # ORM models: User, Product, Scan, Violation, RuleVersion
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   ├── auth.py          # password hashing, JWT, role-based auth deps
│   │   ├── ocr/
│   │   │   ├── preprocessing.py     # deskew, denoise, contrast enhancement
│   │   │   ├── extraction.py        # Tesseract OCR, word/line grouping (keeps pixel bbox per line)
│   │   │   ├── field_classifier.py  # maps OCR'd lines to declaration fields + pixel height
│   │   │   └── pipeline.py          # ties the above into one call
│   │   ├── storage/          # local stand-in for object storage (uploaded images)
│   │   ├── compliance/
│   │   │   └── engine.py       # Step 5 rule-evaluation engine
│   │   ├── reports/
│   │   │   ├── data.py         # single ReportData snapshot shared by both output formats
│   │   │   ├── annotate.py     # draws evidence boxes on the label image for open violations
│   │   │   ├── pdf_report.py   # locked PDF via ReportLab
│   │   │   └── docx_report.py  # editable DOCX via python-docx
│   │   ├── seed.py           # dev seed data: one user per role + sample products/scans
│   │   └── routers/
│   │       ├── auth.py           # /auth/register, /auth/login, /auth/me
│   │       ├── users.py          # admin-only user/role management
│   │       ├── products.py       # product CRUD (create/list/search/update/delete)
│   │       ├── scans.py          # scan lifecycle + image upload & OCR
│   │       ├── reports.py        # GET /scans/{scan_id}/report?format=pdf|docx
│   │       ├── violations.py     # list/filter/resolve violations (dashboard + Step 5 target)
│   │       └── rule_versions.py  # track & activate versions of the rules JSON
│   ├── migrations/            # Alembic migrations (source of truth for schema in real deployments)
│   ├── tests/
│   │   ├── sample_labels/      # 3 concrete sample label images used as OCR test fixtures
│   │   ├── conftest.py         # Step 8: isolated in-memory DB + TestClient fixtures
│   │   ├── test_ocr_pipeline.py
│   │   ├── test_compliance_engine.py
│   │   ├── test_report_generation.py   # Step 7: image in -> OCR -> engine -> PDF/DOCX out
│   │   ├── test_api_e2e_pipeline.py    # Step 8: same flow, over real HTTP end to end
│   │   └── test_auth_rbac.py           # Step 8: role-based access regression coverage
│   ├── scripts/
│   │   ├── pilot_batch_check.py   # Step 8: batch-run real photos through the pipeline
│   │   └── metadata_template.csv
│   ├── alembic.ini
│   ├── entrypoint.sh          # runs migrations (+ optional seed) before the API starts
│   ├── requirements.txt
│   └── Dockerfile
├── rules/
│   └── legal_metrology_rules.json   # digitized Rule 6 / Rule 7 declarations, versioned
├── frontend/                 # React + TypeScript dashboard (Step 6)
│   ├── src/test/             # Step 8: Vitest + Testing Library smoke tests
│   ├── Dockerfile            # Step 8: multi-stage build -> nginx static serve
│   └── nginx.conf
├── docs/                     # Step 8: architecture, data model, rules, deployment, pilot
├── .github/workflows/ci.yml  # Step 8: CI — backend + frontend tests, Docker build check
├── docker-compose.yml        # local dev
├── docker-compose.prod.yml   # Step 8: production stack (gunicorn, nginx, Caddy/TLS)
├── Caddyfile
├── .env.prod.example
├── .gitignore
└── README.md
```

## Running locally (without Docker)

The OCR pipeline needs the Tesseract binary installed on your system
(separate from the Python packages in requirements.txt):

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract
```

Then:

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create the schema (use migrations, not create_all, once you have real data):
alembic upgrade head

# Optional: seed one user per role + sample products so there's data to hit immediately.
python -m app.seed

uvicorn app.main:app --reload
```

This uses SQLite by default (`./legal_metrology.db`) so you can start
testing immediately with no external database. Visit
`http://localhost:8000/docs` for interactive API docs (Swagger UI).

## Running with Docker (Postgres-backed)

```bash
docker compose up --build
```

This starts Postgres plus the backend. The container's `entrypoint.sh`
runs `alembic upgrade head` automatically, then seeds dev data (one
user per role, sample products) since `SEED_ON_START=true` is set in
`docker-compose.yml` — turn that off once you have real data.

## Testing

```bash
cd backend
pytest -v          # full suite, including the Step 8 API-level tests
```

`test_api_e2e_pipeline.py` and `test_auth_rbac.py` (Step 8) hit the real
FastAPI app over HTTP against an isolated in-memory SQLite DB per test —
covering image-in-to-report-out and role-based access the way an actual
client would, on top of the existing unit-level coverage
(`test_ocr_pipeline.py`, `test_compliance_engine.py`,
`test_report_generation.py`). Tests that touch OCR skip themselves if
`tesseract-ocr` isn't on `PATH`.

```bash
cd frontend
npm test            # Vitest + Testing Library smoke tests
```

CI (`.github/workflows/ci.yml`) runs both suites plus a Docker build
check on every push/PR.

## Deploying

See [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) for the full runbook —
`docker-compose.prod.yml` runs gunicorn+uvicorn workers, a static-built
frontend behind nginx, and Caddy handling TLS automatically. Before a
pilot rollout, also see [`docs/PILOT_CHECKLIST.md`](./docs/PILOT_CHECKLIST.md)
and `backend/scripts/pilot_batch_check.py` for validating the pipeline
against real products first.

## Database schema (Step 3)

| Table | Purpose |
|---|---|
| `users` | Inspector/supervisor/admin accounts, bcrypt-hashed passwords, role-based access. |
| `products` | The commodity being tracked, independent of any single scan. |
| `scans` | One inspection event: an uploaded label image, its OCR extraction, status, and which `rule_versions` row it was evaluated against. |
| `violations` | Individual rule breaches found on a scan, each carrying the `rule_id`/citation from `rules/legal_metrology_rules.json`, a severity, and a resolution workflow. |
| `rule_versions` | Tracks which snapshot (by content hash) of the rules JSON is active, so historical reports stay accurate after a rule amendment. |

Schema changes go through Alembic (`backend/migrations/`) — `alembic
revision --autogenerate -m "..."` after editing `models.py`, then
`alembic upgrade head`. `Base.metadata.create_all()` in `main.py` is
kept only as a zero-config fallback for local SQLite runs.

## First things to try

Seeded logins (from `python -m app.seed` or `SEED_ON_START=true`):
`inspector@metrology.gov.in` / `inspector123`,
`supervisor@metrology.gov.in` / `supervisor123`,
`admin@metrology.gov.in` / `admin123`.

1. `POST /auth/login` (form fields `username`/`password`) — get a JWT
   access token, then click **Authorize** in `/docs` and paste it in.
2. `GET /products` — see the seeded products; `POST /products` to add
   your own.
3. `POST /rule-versions/sync-from-file` (as admin) — registers
   `rules/legal_metrology_rules.json` as the active rule version so new
   scans get stamped with it (the seed script already does this once).
4. `POST /scans` — create a scan against a product.
5. `POST /scans/{scan_id}/image` — upload a label photo (multipart
   `file` field). This runs the full OCR & extraction pipeline and
   stores the structured result on `scan.extracted_fields`.
6. `GET /violations?scan_id=...` — once Step 5's compliance engine
   writes `Violation` rows from a scan's `extracted_fields`, this is
   where the dashboard (Step 6) reads them from, with filters by
   severity/rule/resolved status already built.
7. `GET /users` (as admin) — manage who has inspector/supervisor/admin
   access.

## OCR & extraction pipeline — current scope and honest limitations

Verified end-to-end against three concrete sample labels checked into
`backend/tests/sample_labels/` (a clean label, a rotated + low-contrast
one simulating a real phone photo, and one with genuinely missing MRP
and consumer-care fields) — see `backend/tests/test_ocr_pipeline.py`.
Run with `pytest` from `backend/` (needs the `tesseract-ocr` binary on
PATH; the test skips itself if it isn't installed).

`app/ocr/field_classifier.py` uses regex + keyword anchors, not a
trained model. It's genuinely solid for structured fields with a
predictable shape:
- `net_quantity`, `retail_sale_price` (MRP, plus whether "inclusive of
  all taxes" wording is present), and the manufacture/packing date all
  tested correctly against both a clean sample label and a deliberately
  rotated, low-contrast one, and correctly reported MRP and consumer
  care as *absent* on a label genuinely missing them — a compliance
  engine (Step 5) is only as good as its false-negative rate here.
- Every matched field also carries a `pixel_height` (the average glyph
  height, in pixels, of the OCR'd line it was found on) — this is the
  raw ingredient Step 5's font-size/readability check needs; converting
  it to millimetres still requires a reference object in frame or a
  manually entered package dimension, which is Step 5's job, not
  extraction's.

It's weaker, by design, on free-text fields:
- `manufacturer_packer_importer_details` and `consumer_care_details`
  are keyword-anchored heuristics — every match is flagged
  `needs_inspector_confirmation` and should be treated as a candidate,
  not ground truth.
- `generic_name` isn't attempted at all yet — reliably identifying
  "what this product actually is" needs a product-category classifier,
  not a regex; it's left for a later iteration.

The numeral-height slab table that varies by declared net quantity
(Rule 7, Tables I & II) is still marked `NEEDS_VERIFICATION` in the
rule config — Step 5 shouldn't rely on it for real enforcement
decisions until that's transcribed and checked against the gazette
text.

## Rule config

`rules/legal_metrology_rules.json` is the single source of truth for
compliance logic — every rule has an ID and a citation back to the
specific clause of the Legal Metrology (Packaged Commodities) Rules,
2011 it encodes. **Do not hardcode rule thresholds in application
code** — the compliance engine should always read from this file, so
that a rule amendment only requires a config update, not a code change.

Some declaration-presence rules (Rule 6) and the general font-height
floor (Rule 7(3): 1mm minimum, 2mm if embossed/molded/blown/perforated,
letter width ≥ 1/3 of height) are filled in. The **numeral-height
slabs that vary by declared net quantity** (Rule 7, Tables I & II) are
left as a `TODO` placeholder — those exact breakpoints need to be
transcribed carefully from the official gazette text before the
readability-check module (Step 5) can rely on them; getting a legal
threshold wrong is worse than leaving it unfilled for now.
