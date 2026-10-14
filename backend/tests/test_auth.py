import pytest
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.core.security import get_password_hash
from backend.app.models.invite import InviteToken, TokenType

def test_login_valid(client, db):
    user = User(email="login@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("password123"), enabled=True)
    db.add(user)
    db.commit()
    
    resp = client.post("/api/auth/login", json={"email": "login@test.com", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

def test_login_wrong_password(client, db):
    user = User(email="login2@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("password123"), enabled=True)
    db.add(user)
    db.commit()
    
    resp = client.post("/api/auth/login", json={"email": "login2@test.com", "password": "wrong"})
    assert resp.status_code == 401
    
def test_login_unknown_email(client, db):
    resp = client.post("/api/auth/login", json={"email": "unknown@test.com", "password": "wrong"})
    assert resp.status_code == 401

def test_login_disabled(client, db):
    user = User(email="login3@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("password123"), enabled=False)
    db.add(user)
    db.commit()
    
    resp = client.post("/api/auth/login", json={"email": "login3@test.com", "password": "password123"})
    assert resp.status_code == 403

def test_forgot_password_anti_enumeration(client, db):
    resp = client.post("/api/auth/password/forgot", json={"email": "nobody@test.com"})
    assert resp.status_code == 200
    assert "receive a reset link shortly" in resp.json()["message"]

def test_forgot_and_reset_password(client, db):
    user = User(email="reset@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=get_password_hash("oldpass"), enabled=True)
    db.add(user)
    db.commit()
    
    resp = client.post("/api/auth/password/forgot", json={"email": "reset@test.com"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    
    resp2 = client.post("/api/auth/password/reset", json={"token": token, "new_password": "newpass"})
    assert resp2.status_code == 200
    
    # Verify login with new pass
    resp3 = client.post("/api/auth/login", json={"email": "reset@test.com", "password": "newpass"})
    assert resp3.status_code == 200
    
    # Token single use
    resp4 = client.post("/api/auth/password/reset", json={"token": token, "new_password": "newpass2"})
    assert resp4.status_code == 400

def test_invite_accept(client, db):
    user = User(email="invited@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, enabled=False)
    db.add(user)
    db.flush()
    
    from backend.app.core.security import generate_raw_token, hash_token
    from datetime import datetime, timezone, timedelta
    
    raw_token = generate_raw_token()
    invite = InviteToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        token_type=TokenType.INVITE,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=72)
    )
    db.add(invite)
    db.commit()
    
    resp = client.post("/api/auth/invite/accept", json={"token": raw_token, "new_password": "newpass"})
    assert resp.status_code == 200
    
    # Check enabled
    db.refresh(user)
    assert user.enabled == True
    assert user.password_hash is not None
    
    # Check login
    resp2 = client.post("/api/auth/login", json={"email": "invited@test.com", "password": "newpass"})
    assert resp2.status_code == 200


def test_cors_preflight_login_allowed_origins(client):
    """CORS preflight OPTIONS requests from allowed origins return 200 OK with correct headers."""
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.229.41:5173",
    ]
    for origin in allowed_origins:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization,cache-control,pragma",
        }
        resp = client.options("/api/auth/login", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"
        assert "POST" in resp.headers.get("access-control-allow-methods", "")


def test_cors_preflight_login_disallowed_origin(client):
    """CORS preflight OPTIONS request from untrusted origin does not receive allow-origin."""
    headers = {
        "Origin": "http://untrusted-domain.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/api/auth/login", headers=headers)
    assert resp.headers.get("access-control-allow-origin") != "http://untrusted-domain.com"
