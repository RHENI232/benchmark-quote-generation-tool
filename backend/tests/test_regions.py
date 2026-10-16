from fastapi.testclient import TestClient
import pytest
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.core.security import get_password_hash

def get_auth_headers(client: TestClient, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
def test_users(db):
    users_data = [
        ("sales@test.com", RoleTier.SALES),
        ("catalog@test.com", RoleTier.CATALOG_ENTRY),
        ("mgmt@test.com", RoleTier.MANAGEMENT),
        ("admin@test.com", RoleTier.ADMIN),
    ]
    for email, role in users_data:
        db.execute(User.__table__.delete().where(User.email == email))
        user = User(email=email, role_tier=role, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
        db.add(user)
    db.commit()

def test_get_regions_unauthorized(client: TestClient):
    resp = client.get("/api/regions")
    assert resp.status_code == 403 or resp.status_code == 401

def test_get_regions_authorized(client: TestClient, test_users):
    headers = get_auth_headers(client, "sales@test.com", "pass")
    resp = client.get("/api/regions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0 # Seeded regions should exist

    # Check structure
    first = data[0]
    assert "id" in first
    assert "country_name" in first
    assert "currency_code" in first
    assert "tax_enabled" in first

def test_update_region_fx_rate_authorized_admin(client: TestClient, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    # First get regions to find a region ID
    regions = client.get("/api/regions", headers=headers).json()
    india = next(r for r in regions if r["currency_code"] == "INR")

    payload = {
        "fx_rate_to_usd": 0.012500,
        "currency_code": "INR",
        "fx_rate_as_of": "2026-10-16 12:00:00 UTC",
        "notes": "Updated by Admin"
    }
    resp = client.put(f"/api/regions/{india['id']}/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["fx_rate_to_usd"]) == 0.0125
    assert data["fx_rate_as_of"] == "2026-10-16 12:00:00 UTC"

def test_update_region_fx_rate_authorized_management(client: TestClient, test_users):
    headers = get_auth_headers(client, "mgmt@test.com", "pass")
    regions = client.get("/api/regions", headers=headers).json()
    india = next(r for r in regions if r["currency_code"] == "INR")

    payload = {
        "fx_rate_to_usd": 0.012345,
        "currency_code": "INR",
        "fx_rate_as_of": "2026-10-16 12:15:00 UTC"
    }
    resp = client.put(f"/api/regions/{india['id']}/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["fx_rate_to_usd"]) == 0.012345

def test_update_region_fx_rate_forbidden_sales(client: TestClient, test_users):
    headers = get_auth_headers(client, "sales@test.com", "pass")
    payload = {"fx_rate_to_usd": 0.0125, "currency_code": "INR"}
    resp = client.put("/api/regions/1/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 403

def test_update_region_fx_rate_forbidden_catalog_entry(client: TestClient, test_users):
    headers = get_auth_headers(client, "catalog@test.com", "pass")
    payload = {"fx_rate_to_usd": 0.0125, "currency_code": "INR"}
    resp = client.put("/api/regions/1/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 403

def test_update_region_fx_rate_unauthenticated(client: TestClient):
    payload = {"fx_rate_to_usd": 0.0125, "currency_code": "INR"}
    resp = client.put("/api/regions/1/fx-rate", json=payload)
    assert resp.status_code == 401 or resp.status_code == 403

def test_update_region_fx_rate_validation_negative(client: TestClient, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    payload = {"fx_rate_to_usd": -0.012, "currency_code": "INR"}
    resp = client.put("/api/regions/1/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 422

def test_update_region_fx_rate_validation_zero(client: TestClient, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    payload = {"fx_rate_to_usd": 0.0, "currency_code": "INR"}
    resp = client.put("/api/regions/1/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 422

def test_update_region_fx_rate_currency_mismatch(client: TestClient, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    regions = client.get("/api/regions", headers=headers).json()
    india = next(r for r in regions if r["currency_code"] == "INR")

    payload = {"fx_rate_to_usd": 0.0125, "currency_code": "USD"}
    resp = client.put(f"/api/regions/{india['id']}/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "mismatch" in resp.json()["detail"].lower()

def test_update_region_fx_rate_nonexistent_region(client: TestClient, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    payload = {"fx_rate_to_usd": 0.0125, "currency_code": "INR"}
    resp = client.put("/api/regions/99999/fx-rate", json=payload, headers=headers)
    assert resp.status_code == 404
