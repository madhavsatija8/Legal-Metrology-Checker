"""
Step 8: exercises the full pipeline the way a real client actually would —
over HTTP, through the FastAPI app, with a real (in-memory) database —
rather than calling pipeline functions directly like
test_compliance_engine.py / test_ocr_pipeline.py / test_report_generation.py
do. Those three test the engine and generators in isolation; this test is
what proves the routers, auth, and DB wiring connecting them actually work
end to end: image in -> report out, exactly as described in the Step 8 brief.

Requires the tesseract-ocr binary (see test_report_generation.py's same
skip condition) since it uploads a real label image and lets the OCR
pipeline run for real rather than mocking it.
"""
import os
import shutil

import pytest

from app import models

from .conftest import SAMPLES_DIR

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract-ocr binary not installed",
)


def _register_and_login(client, email, password, full_name, role):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_pipeline_image_in_to_report_out(client):
    # 1. Onboard an inspector and an admin via the real registration endpoint.
    inspector_headers = _register_and_login(
        client, "inspector@pilot.test", "inspectpass1", "Pilot Inspector", "inspector"
    )
    admin_headers = _register_and_login(client, "admin@pilot.test", "adminpass123", "Pilot Admin", "admin")

    # 2. Admin activates the current rules file as a RuleVersion, exactly as
    # an operator would after an amendment, before any scan can be stamped.
    resp = client.post("/rule-versions/sync-from-file", headers=admin_headers)
    assert resp.status_code == 201, resp.text
    rule_version_id = resp.json()["id"]

    # 3. Inspector registers a product and creates a scan for it.
    resp = client.post(
        "/products",
        json={"name": "Instant Noodles 70g", "brand": "TastyMax", "category": "Packaged Food"},
        headers=inspector_headers,
    )
    assert resp.status_code == 201, resp.text
    product_id = resp.json()["id"]

    resp = client.post("/scans", json={"product_id": product_id}, headers=inspector_headers)
    assert resp.status_code == 201, resp.text
    scan = resp.json()
    scan_id = scan["id"]
    assert scan["status"] == "pending"
    assert scan["rule_version_id"] == rule_version_id

    # 4. Upload a label photo with genuinely missing declarations — this runs
    # preprocessing -> OCR -> field classification -> compliance engine for real.
    image_path = os.path.join(SAMPLES_DIR, "label_missing_fields.png")
    with open(image_path, "rb") as f:
        resp = client.post(
            f"/scans/{scan_id}/image",
            files={"file": ("label_missing_fields.png", f, "image/png")},
            headers=inspector_headers,
        )
    assert resp.status_code == 200, resp.text
    scan = resp.json()
    assert scan["status"] == "review"
    assert scan["extracted_fields"] and "fields" in scan["extracted_fields"]
    assert len(scan["violations"]) > 0
    assert any(v["description"].startswith("Missing declaration") for v in scan["violations"])
    # Font-size checks can't run without a px/mm calibration — the engine
    # should say so via a review item rather than silently pass them.
    assert scan["compliance_review"]["review_items"], "expected an uncalibrated-scan review item"

    # 5. Supervisor/admin sets calibration; this should re-run the engine.
    resp = client.patch(f"/scans/{scan_id}", json={"calibration_px_per_mm": 8.0}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    recalibrated = resp.json()
    assert recalibrated["calibration_px_per_mm"] == 8.0

    # 6. The violations triage surface should see the same violations by scan_id.
    resp = client.get("/violations", params={"scan_id": scan_id}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    violations = resp.json()
    assert len(violations) > 0

    # 7. Inspector resolves one violation (e.g. seller fixed the label on
    # re-inspection) and it should stick.
    violation_id = violations[0]["id"]
    resp = client.patch(
        f"/violations/{violation_id}",
        json={"is_resolved": True, "resolution_note": "Corrected label verified on re-inspection."},
        headers=inspector_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_resolved"] is True

    # Re-evaluating the scan (e.g. a subsequent PATCH/upload) must not wipe
    # that resolution — routers/scans.py's _run_compliance_evaluation only
    # deletes *unresolved* engine-generated violations.
    resp = client.post(f"/scans/{scan_id}/evaluate", headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    resp = client.get(f"/violations/{violation_id}", headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_resolved"] is True

    # 8. Reporting module (Step 7) end to end via the actual download route.
    resp = client.get(f"/scans/{scan_id}/report", params={"format": "pdf"}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000

    resp = client.get(f"/scans/{scan_id}/report", params={"format": "docx"}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    assert "wordprocessingml" in resp.headers["content-type"]
    assert len(resp.content) > 1000

    # 9. Repository/search facility: the scan and product must be discoverable
    # afterwards, matching the "maintain a repository" functional requirement.
    resp = client.get("/products", params={"q": "Noodles"}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    assert any(p["id"] == product_id for p in resp.json())

    resp = client.get("/scans", params={"product_id": product_id}, headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    assert any(s["id"] == scan_id for s in resp.json())


def test_clean_label_produces_no_open_violations(client, make_user, login):
    """Sanity check in the other direction — a label with every mandatory
    declaration present and legible shouldn't manufacture violations out of
    nothing. Guards against a change to the engine or rule config that makes
    it over-eager."""
    inspector = make_user("inspector2@pilot.test", models.UserRole.INSPECTOR)
    headers = login(inspector.email)

    resp = client.post(
        "/products",
        json={"name": "Refined Sunflower Oil 1L", "brand": "SunGold", "category": "Edible Oil"},
        headers=headers,
    )
    product_id = resp.json()["id"]

    resp = client.post(
        "/scans",
        json={"product_id": product_id, "calibration_px_per_mm": 8.0},
        headers=headers,
    )
    scan_id = resp.json()["id"]

    image_path = os.path.join(SAMPLES_DIR, "label_clean.png")
    with open(image_path, "rb") as f:
        resp = client.post(
            f"/scans/{scan_id}/image",
            files={"file": ("label_clean.png", f, "image/png")},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    scan = resp.json()
    open_violations = [v for v in scan["violations"] if not v["is_resolved"]]
    assert open_violations == [], f"unexpected violations on a clean label: {open_violations}"
