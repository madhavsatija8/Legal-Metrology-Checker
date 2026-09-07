# Pilot run checklist

Goal: before enforcement teams rely on this system's verdicts, validate
it against real packaged products and have an inspector confirm the
engine agrees with their own manual read — catching false
positives/negatives in OCR, field classification, or the rule config
while the stakes are still "double-check a report," not "an enforcement
action based on a wrong verdict."

## 1. Pick 10-20 real products

Aim for variety across:
- **Categories** — at minimum one edible oil/food item, one imported
  product (exercises the country-of-origin rule), and one item with a
  molded/embossed declaration if you can find one (exercises the 2mm
  threshold vs. the 1mm default).
- **Label condition** — a few clean, well-lit labels and a few realistic
  phone-photo conditions (angled, glare, low light) so you're testing
  the OCR preprocessing, not just the compliance logic.

## 2. Capture photos + measure calibration

For each product:
- Take a clear photo of the principal display panel.
- Measure the pixels-per-mm calibration for that photo — the simplest
  approach is including a reference object of known size (a ruler, or a
  coin of known diameter) in frame and measuring its pixel width, or
  measuring a known package dimension directly. Record this per photo —
  it varies with camera distance/zoom, it's not a fixed constant.

## 3. Run the batch script

```bash
cd backend
cp scripts/metadata_template.csv my_pilot_metadata.csv
# edit my_pilot_metadata.csv: one row per photo, with real product info
# and the calibration you measured in step 2

python -m scripts.pilot_batch_check \
  --images-dir /path/to/your/photos \
  --metadata my_pilot_metadata.csv \
  --out-dir ./pilot_reports
```

This produces `pilot_reports/pilot_summary.csv` (one row per product:
violation counts by severity, review-item count, exempt flag) and one
PDF report per product.

## 4. Manual review

For each product, have an inspector who has physically examined the
package:
- Open the PDF report.
- Compare every listed violation against their own read of the label —
  is it real, or a false positive (OCR misread a field, or matched
  something it shouldn't have)?
- Check for false negatives — did the engine miss something the
  inspector can see is actually wrong on the label?
- Note anything in the review_items list that a human could actually
  resolve but the engine couldn't (e.g. a width-ratio check that isn't
  automated yet — is it obviously fine or obviously a problem at a
  glance?).

## 5. Log discrepancies

Keep a simple table (a spreadsheet is fine) of:

| Product | rule_id | Engine said | Inspector says | Root cause |
|---|---|---|---|---|

For each discrepancy, the root cause is usually one of:
- **OCR misread** — wrong text extracted. Check
  `backend/app/ocr/preprocessing.py`/`extraction.py`; may need a
  preprocessing tweak for that lighting/angle condition, or is just an
  OCR limitation to note and work around procedurally (re-shoot the photo).
- **Field misclassification** — text extracted correctly but mapped to
  the wrong declaration, or not matched. Check
  `backend/app/ocr/field_classifier.py`'s keyword/pattern logic.
- **Rule config issue** — the engine correctly extracted and matched the
  field, but the threshold/logic in
  `rules/legal_metrology_rules.json` is wrong or incomplete. Fix via the
  amend-and-sync workflow in
  [`RULES_CONFIG.md`](../docs/RULES_CONFIG.md).
- **Genuinely not automated yet** — expected; it should show as a
  `review_item`, not silently missing. If it's showing as a false pass
  instead, that's a real bug worth filing.

## 6. Go/no-go

Before wider rollout, you want:
- Zero false negatives on **critical** severity items (missing net
  quantity, missing/malformed MRP) — these are the highest-stakes to
  get wrong.
- An acceptable false-positive rate on minor/major items, with a clear
  process for an inspector to override/resolve a wrong violation
  (`PATCH /violations/{id}` — see `docs/ARCHITECTURE.md`'s request flow).
- Confidence that uncalibrated scans are actually getting flagged for
  calibration rather than silently skipping font-size checks (check the
  `review_items` column in the summary CSV for `missing_calibration`).

If discrepancies are widespread rather than isolated, that's a signal
to go back to steps 3-5 with a fresh batch after fixing the root causes
— rather than rolling out and discovering the same class of error at
enforcement scale.
