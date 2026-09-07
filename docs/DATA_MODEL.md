# Data model

Source of truth: `backend/app/models.py`. Schema changes go through
Alembic migrations in `backend/migrations/versions/` — never hand-edit
the DB or add a column only to the ORM model without a matching
migration, or `alembic upgrade head` and the model will drift apart.

## Entity-relationship diagram

```
┌───────────────┐        ┌───────────────┐        ┌────────────────┐
│     User        │        │    Product      │        │  RuleVersion    │
│──────────────│        │──────────────│        │───────────────│
│ id (PK)         │        │ id (PK)         │        │ id (PK)          │
│ email (unique)  │        │ name             │        │ version_label    │
│ full_name       │        │ brand            │        │ source_file_hash │
│ hashed_password │        │ category         │        │ (unique)         │
│ role             │       │ manufacturer_name│        │ is_active        │
│ is_active        │       │ is_imported      │        │ activated_at     │
│ created_at       │       │ surface_treatment│        └────────┬────────┘
└───────┬─────────┘        │ created_at       │                 │
        │ 1                └────────┬─────────┘                 │ 1
        │                            │ 1                          │
        │ creates                    │ has many                   │ evaluated against
        ▼ *                          ▼ *                          ▼ *
┌─────────────────────────────────────────────────────────────────────┐
│                               Scan                                    │
│──────────────────────────────────────────────────────────────────│
│ id (PK)                                                               │
│ product_id (FK → Product)                                             │
│ created_by_id (FK → User)                                             │
│ rule_version_id (FK → RuleVersion, nullable)                          │
│ image_path                                                            │
│ status  [pending|processing|review|resolved|escalated]                │
│ extracted_fields (JSON — OCR pipeline output, Step 4)                 │
│ calibration_px_per_mm (nullable — inspector-supplied)                 │
│ compliance_review (JSON — exemption + review_items, Step 5)           │
│ created_at, updated_at                                                 │
└──────────────────────────────┬────────────────────────────────────┘
                                 │ 1
                                 │ has many
                                 ▼ *
                     ┌─────────────────────────┐
                     │        Violation           │
                     │───────────────────────│
                     │ id (PK)                    │
                     │ scan_id (FK → Scan)         │
                     │ rule_id (references         │
                     │   rules JSON, not a FK)      │
                     │ citation                     │
                     │ description                  │
                     │ severity [minor|major|       │
                     │   critical]                   │
                     │ needs_review                  │
                     │ is_resolved                    │
                     │ resolution_note                 │
                     │ created_at                       │
                     └─────────────────────────┘
```

## Notes on specific design choices

- **`rule_id` on `Violation` is a string reference into
  `rules/legal_metrology_rules.json`, not a foreign key.** The rule
  config is versioned as a file + `RuleVersion` hash, not as DB rows
  (see `RULES_CONFIG.md`) — a `Violation` records which rule fired and
  a `Scan` records which `RuleVersion` was active, which together is
  enough to reconstruct exactly what was checked, without needing every
  individual rule to be its own DB row.
- **`Scan.compliance_review` and `Scan.extracted_fields` are JSON
  columns, not normalized tables.** Both are pipeline *output* whose
  shape is expected to evolve as OCR/engine logic improves — normalizing
  them now would mean a migration on every field-classifier change.
  `Violation` rows are normalized because the dashboard and reports
  filter/query them directly (by severity, resolution state, scan).
- **`Violation.is_resolved` lives on the violation, not just the parent
  `Scan.status`.** A scan can have some violations resolved and others
  still open — the dashboard needs to filter at that granularity, and a
  re-run of the compliance engine (`_run_compliance_evaluation` in
  `routers/scans.py`) only replaces *unresolved* engine-generated
  violations, preserving resolution history across re-evaluations.
- **`RuleVersion.source_file_hash` is unique.** Re-running
  `POST /rule-versions/sync-from-file` against an unchanged rules file
  is a no-op (returns the existing version) rather than creating
  duplicate rows — this makes the sync endpoint safe to call repeatedly,
  e.g. from a deployment script.
- **`Product.is_imported` / `Product.surface_treatment`** exist purely to
  drive conditional rules in the config (country-of-origin only applies
  to imports; the 2mm-vs-1mm letter-height threshold depends on whether
  the declaration is molded/blown/embossed) that OCR cannot reliably
  infer from the label text alone — see `ComplianceContext` in
  `compliance/engine.py`.

## Migrations

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

`docker-compose.yml` / `docker-compose.prod.yml` both run
`alembic upgrade head` automatically on container start
(`backend/entrypoint.sh`) before the app boots.
