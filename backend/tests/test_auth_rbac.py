"""
Step 8: role-based access control regression tests. The compliance
engine and OCR pipeline already have solid coverage (test_compliance_engine.py,
test_ocr_pipeline.py) — this file covers the layer that actually gates who
can do what, which is the part most likely to silently regress when a new
endpoint is added without its `require_role(...)` dependency, or with the
wrong one.

Uses in-memory users (via the `make_user` fixture) rather than routing
everything through /auth/register, so each test can set up exactly the
role it needs without depending on the registration endpoint's own
behavior (covered separately below).
"""
from datetime import timedelta

from app import models
from app.auth import create_access_token


def _make_product(client, headers) -> str:
    resp = client.post("/products", json={"name": "Test Product"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---- Registration / login ----


def test_register_then_login_round_trip(client):
    resp = client.post(
        "/auth/register",
        json={"email": "newuser@metrology.test", "password": "somepassword1", "full_name": "New User"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "inspector"  # default role from schemas.UserCreate

    resp = client.post("/auth/login", data={"username": "newuser@metrology.test", "password": "somepassword1"})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


def test_duplicate_registration_is_rejected(client):
    payload = {"email": "dupe@metrology.test", "password": "somepassword1", "full_name": "Dupe"}
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 400, resp.text


def test_login_with_wrong_password_is_rejected(client, make_user):
    make_user("wrongpass@metrology.test", models.UserRole.INSPECTOR, password="correcthorsebattery")
    resp = client.post(
        "/auth/login", data={"username": "wrongpass@metrology.test", "password": "not-the-password"}
    )
    assert resp.status_code == 401, resp.text


def test_request_without_a_token_is_rejected(client):
    resp = client.get("/products")
    assert resp.status_code == 401


def test_request_with_a_garbage_token_is_rejected(client):
    resp = client.get("/products", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_expired_token_is_rejected(client, make_user):
    user = make_user("expired@metrology.test", models.UserRole.INSPECTOR)
    # A token that "expired" a minute ago should behave the same as no token.
    token = create_access_token(subject=user.id, expires_delta=timedelta(minutes=-1))
    resp = client.get("/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_deactivated_user_token_is_rejected(client, make_user, db_session):
    user = make_user("deactivated@metrology.test", models.UserRole.INSPECTOR)
    token = create_access_token(subject=user.id)

    # Token is valid and the account is active — should work.
    resp = client.get("/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Deactivate (e.g. an inspector leaving the department, done via
    # PATCH /users/{id} in practice) — the same *previously issued* token
    # must stop working immediately, not just new logins.
    user.is_active = False
    db_session.add(user)
    db_session.commit()

    resp = client.get("/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---- Role-based access: products ----


def test_any_authenticated_role_can_read_products(client, make_user, login):
    for email, role in [
        ("insp_read@metrology.test", models.UserRole.INSPECTOR),
        ("sup_read@metrology.test", models.UserRole.SUPERVISOR),
        ("adm_read@metrology.test", models.UserRole.ADMIN),
    ]:
        make_user(email, role)
        headers = login(email)
        resp = client.get("/products", headers=headers)
        assert resp.status_code == 200, f"{role} should be able to list products"


def test_inspector_can_create_but_not_update_or_delete_products(client, make_user, login):
    make_user("insp_crud@metrology.test", models.UserRole.INSPECTOR)
    headers = login("insp_crud@metrology.test")

    resp = client.post("/products", json={"name": "Inspector Created Product"}, headers=headers)
    assert resp.status_code == 201, "inspectors can create products (e.g. while cataloging a new scan)"
    product_id = resp.json()["id"]

    resp = client.patch("/products/" + product_id, json={"name": "Renamed"}, headers=headers)
    assert resp.status_code == 403, "updating a product is supervisor/admin only"

    resp = client.delete("/products/" + product_id, headers=headers)
    assert resp.status_code == 403, "deleting a product is admin only"


def test_supervisor_can_update_but_not_delete_products(client, make_user, login):
    make_user("sup_crud@metrology.test", models.UserRole.SUPERVISOR)
    headers = login("sup_crud@metrology.test")
    product_id = _make_product(client, headers)

    resp = client.patch("/products/" + product_id, json={"name": "Renamed by supervisor"}, headers=headers)
    assert resp.status_code == 200

    resp = client.delete("/products/" + product_id, headers=headers)
    assert resp.status_code == 403, "deleting a product is admin only, even for a supervisor"


def test_admin_can_delete_a_product_with_no_scans(client, make_user, login):
    make_user("adm_crud@metrology.test", models.UserRole.ADMIN)
    headers = login("adm_crud@metrology.test")
    product_id = _make_product(client, headers)

    resp = client.delete("/products/" + product_id, headers=headers)
    assert resp.status_code == 204


# ---- Role-based access: users ----


def test_only_admin_can_list_users(client, make_user, login):
    make_user("insp_users@metrology.test", models.UserRole.INSPECTOR)
    make_user("sup_users@metrology.test", models.UserRole.SUPERVISOR)
    make_user("adm_users@metrology.test", models.UserRole.ADMIN)

    for email, role in [
        ("insp_users@metrology.test", models.UserRole.INSPECTOR),
        ("sup_users@metrology.test", models.UserRole.SUPERVISOR),
    ]:
        headers = login(email)
        resp = client.get("/users", headers=headers)
        assert resp.status_code == 403, f"{role} must not be able to list users"

    headers = login("adm_users@metrology.test")
    resp = client.get("/users", headers=headers)
    assert resp.status_code == 200


# ---- Role-based access: rule versions ----


def test_only_admin_can_sync_rule_versions(client, make_user, login):
    make_user("insp_rules@metrology.test", models.UserRole.INSPECTOR)
    make_user("adm_rules@metrology.test", models.UserRole.ADMIN)

    headers = login("insp_rules@metrology.test")
    resp = client.post("/rule-versions/sync-from-file", headers=headers)
    assert resp.status_code == 403

    headers = login("adm_rules@metrology.test")
    resp = client.post("/rule-versions/sync-from-file", headers=headers)
    assert resp.status_code == 201


# ---- Role-based access: scans ----


def test_only_supervisor_or_admin_can_set_scan_status_or_calibration(client, make_user, login):
    make_user("insp_scan@metrology.test", models.UserRole.INSPECTOR)
    make_user("sup_scan@metrology.test", models.UserRole.SUPERVISOR)

    inspector_headers = login("insp_scan@metrology.test")
    product_id = _make_product(client, inspector_headers)
    resp = client.post("/scans", json={"product_id": product_id}, headers=inspector_headers)
    scan_id = resp.json()["id"]

    resp = client.patch(f"/scans/{scan_id}", json={"status": "escalated"}, headers=inspector_headers)
    assert resp.status_code == 403, "inspectors cannot change scan status directly"

    supervisor_headers = login("sup_scan@metrology.test")
    resp = client.patch(f"/scans/{scan_id}", json={"status": "escalated"}, headers=supervisor_headers)
    assert resp.status_code == 200


def test_only_admin_can_delete_scans(client, make_user, login):
    make_user("sup_del@metrology.test", models.UserRole.SUPERVISOR)
    make_user("adm_del@metrology.test", models.UserRole.ADMIN)

    supervisor_headers = login("sup_del@metrology.test")
    product_id = _make_product(client, supervisor_headers)
    resp = client.post("/scans", json={"product_id": product_id}, headers=supervisor_headers)
    scan_id = resp.json()["id"]

    resp = client.delete(f"/scans/{scan_id}", headers=supervisor_headers)
    assert resp.status_code == 403, "even a supervisor cannot delete scans — admin only"

    admin_headers = login("adm_del@metrology.test")
    resp = client.delete(f"/scans/{scan_id}", headers=admin_headers)
    assert resp.status_code == 204
