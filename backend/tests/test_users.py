import pytest
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.quote import Quote
from backend.app.core.security import get_password_hash

def get_auth_headers(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
def super_admin(db):
    db.execute(User.__table__.delete().where(User.email == 'admin@benchmark.local'))
    db.commit()
    user = User(email="super@test.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
    db.add(user)
    db.commit()
    return user

@pytest.fixture
def sales_user(db):
    user = User(email="sales@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
    db.add(user)
    db.commit()
    return user

def test_list_users(client, super_admin, sales_user):
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2
    
def test_invite_user_success(client, super_admin):
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.post("/api/users/invite", json={"email": "newuser@test.com", "role_tier": "Sales"}, headers=headers)
    assert resp.status_code == 201
    assert "token" in resp.json()

def test_sales_cannot_invite(client, sales_user):
    headers = get_auth_headers(client, "sales@test.com", "pass")
    resp = client.post("/api/users/invite", json={"email": "newuser2@test.com", "role_tier": "Sales"}, headers=headers)
    assert resp.status_code == 403

def test_admin_invariant_disable(client, super_admin):
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.put(f"/api/users/{super_admin.id}/status", json={"enabled": False}, headers=headers)
    assert resp.status_code == 400
    assert "last enabled Admin" in resp.json()["detail"]

def test_admin_invariant_demote(client, super_admin):
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.put(f"/api/users/{super_admin.id}/role", json={"role_tier": "Sales"}, headers=headers)
    assert resp.status_code == 400

def test_admin_invariant_delete(client, super_admin):
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.delete(f"/api/users/{super_admin.id}", headers=headers)
    assert resp.status_code == 400

def test_admin_invariant_success_with_multiple(client, db, super_admin):
    admin2 = User(email="admin2@test.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
    db.add(admin2)
    db.commit()
    
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.put(f"/api/users/{admin2.id}/status", json={"enabled": False}, headers=headers)
    assert resp.status_code == 200

def test_cannot_delete_user_with_quotes(client, db, super_admin, sales_user):
    from datetime import datetime, timezone
    from backend.app.models.quote import QuoteStatus
    from backend.app.models.region import Region
    from backend.app.models.solution import Solution
    
    region = db.query(Region).first()
    solution = db.query(Solution).first()
    
    q = Quote(
        client_name="Test", 
        quote_ref_no="Q123",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        attention="attn",
        description="desc",
        version=1,
        requirement_data={},
        created_by_user_id=sales_user.id,
        last_edited_by_user_id=sales_user.id,
        status=QuoteStatus.DRAFT,
        region_id=region.id if region else None,
        solution_id=solution.id if solution else None
    )
    db.add(q)
    db.commit()
    
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.delete(f"/api/users/{sales_user.id}", headers=headers)
    assert resp.status_code == 400
    assert "quote history" in resp.json()["detail"]
    
def test_can_delete_user_without_quotes(client, db, super_admin):
    user = User(email="delete_me@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
    db.add(user)
    db.commit()
    
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.delete(f"/api/users/{user.id}", headers=headers)
    assert resp.status_code == 204
