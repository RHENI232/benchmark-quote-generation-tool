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
