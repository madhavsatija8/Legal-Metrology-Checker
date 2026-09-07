# Rule configuration

`rules/legal_metrology_rules.json` is the single source of truth the
compliance engine (`backend/app/compliance/engine.py`) reads against —
no legal threshold is ever hardcoded in application code. This doc
covers the file's format and how a change to it actually takes effect.

## File structure

| Section | Consumed by | Notes |
|---|---|---|
| `mandatory_declarations` | `_evaluate_mandatory_declarations` | One entry per Rule 6 declaration. `field` must match a key the OCR field classifier (`app/ocr/field_classifier.py`) actually produces. `condition` (currently only `is_imported`) gates rules that only apply to a subset of products. |
| `font_and_readability` | `_evaluate_font_and_readability` | Letter-height and width-ratio thresholds (Rule 7(3)). `applies_if` selects a more specific rule (e.g. the 2mm molded-surface threshold) over the 1mm default via `ComplianceContext.surface_treatment`. |
| `structural_rules` | not automated | Currently just the principal-display-panel-area basis — needs package shape/dimension input the pipeline doesn't capture yet, so it's always surfaced as a `review_item`, never auto-evaluated. |
| `exemptions` | not automated | Chapter II exemption text — small-pack, bulk-pack, food-service, scheduled-drugs. Also not yet automated (needs net-quantity-vs-threshold comparison and category matching); see `Scan.compliance_review.exempt` for where this should eventually be wired in. |
| `ecommerce_note` | informational only | Rule 6(10) — not evaluated against scans; kept here as a reference for anyone extending this to e-commerce listing checks. |

Every rule entry carries a `rule_id` (referenced by `Violation.rule_id`
and `ReviewItem.rule_id` — see `DATA_MODEL.md`) and a `citation` (the
actual Rule/sub-rule number), so every violation a report shows traces
back to specific statutory text.

### `NEEDS_VERIFICATION` entries

`R7-numeral-height-slabs` has an empty `slabs: []` array and a
`NEEDS_VERIFICATION` description — the numeral-height-by-net-quantity
table (Rule 7, Tables I & II) needs to be transcribed from the official
gazette text before it's enforced. Until then, the engine surfaces a
`rule_pending_verification` review item instead of silently skipping it
or guessing at thresholds. **Do not populate `slabs` from anything other
than the primary legal text** — this is exactly the kind of error that
turns into a wrongly-issued violation against a real business.

## Amending a rule

1. Edit `rules/legal_metrology_rules.json` directly. Keep every entry's
   `rule_id` stable once it's shipped — `Violation.rule_id` values in
   existing scan history reference it, and changing it breaks that
   traceability.
2. As an admin, call `POST /rule-versions/sync-from-file`. This:
   - Computes a SHA-256 hash of the file's current contents.
   - If that exact content has been seen before, re-activates the
     existing `RuleVersion` (no duplicate rows).
   - Otherwise registers a new `RuleVersion` and marks it active.
3. Every *new* scan from this point stamps `Scan.rule_version_id` with
   the newly active version. **Existing scans and their reports are
   unaffected** — a report always renders against the `RuleVersion` a
   scan was originally evaluated under, even if the file has since
   changed again. This is what keeps historical compliance reports
   legally accurate after an amendment.
4. To re-evaluate an *existing* scan against the newly active rules
   (e.g. to see how a still-open scan looks under an amendment), call
   `POST /scans/{id}/evaluate` — this reads the rules file fresh (not
   the stamped `RuleVersion`) and re-runs the engine, replacing
   unresolved engine-generated violations while preserving already-
   resolved ones.

## Adding a genuinely new rule

If a new rule needs a field the OCR pipeline doesn't extract yet, or a
condition the `ComplianceContext` doesn't carry:

1. Add the field to `app/ocr/field_classifier.py`'s classification logic
   (or the context field to `ComplianceContext` in `engine.py`) first.
2. Add the rule entry to the JSON.
3. Add a case to `backend/tests/test_compliance_engine.py` (and, if it's
   font/readability-related, a fixture in
   `backend/tests/sample_labels/` + `test_ocr_pipeline.py`) before
   relying on it — the engine's own docstring principle is "never
   silently pass or silently violate," and a test is how you confirm a
   new rule doesn't do either.
4. Sync the new version via `POST /rule-versions/sync-from-file`.
