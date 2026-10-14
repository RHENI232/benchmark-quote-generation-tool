import pytest
from unittest.mock import patch
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.quote import Quote
from backend.app.models.invite import InviteToken, TokenType
from backend.app.core.security import get_password_hash
from backend.app.core.config import settings
from backend.app.services.email_service import EmailDeliveryError

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

@pytest.fixture(autouse=True)
def default_console_email_provider(monkeypatch):
    """Ensure user management tests default to console email provider for isolation."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")

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


# -----------------------------------------------------------------------------
# CP12: Secure User Invitation & Resend Integration Tests
# -----------------------------------------------------------------------------

def test_cp12_invite_user_gmail_mode_no_token_in_response(client, super_admin, monkeypatch, db):
    """In Gmail delivery mode, raw token must NOT be returned in API response."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    headers = get_auth_headers(client, "super@test.com", "pass")
    with patch("backend.app.api.routers.users.send_invitation_email") as mock_send:
        resp = client.post("/api/users/invite", json={"email": "produser@test.com", "role_tier": "Catalog Entry"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["token"] is None
        assert "sent" in resp.json()["message"].lower()
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert kwargs["recipient_email"] == "produser@test.com"
        assert "token=" in kwargs["invitation_url"]

    # Verify user in database
    u = db.query(User).filter(User.email == "produser@test.com").first()
    assert u is not None
    assert u.enabled is False
    assert u.password_hash is None
    assert u.is_pending_invite is True


def test_cp12_invite_user_email_delivery_failure_rolls_back(client, super_admin, db):
    """If email delivery fails, the transaction must roll back with zero phantom user/token records."""
    headers = get_auth_headers(client, "super@test.com", "pass")
    with patch("backend.app.api.routers.users.send_invitation_email", side_effect=EmailDeliveryError("SMTP connection timeout")):
        resp = client.post("/api/users/invite", json={"email": "failed_delivery@test.com", "role_tier": "Sales"}, headers=headers)
        assert resp.status_code == 502
        assert "failed to send invitation email" in resp.json()["detail"].lower()

    # User and token must NOT exist in the database
    u = db.query(User).filter(User.email == "failed_delivery@test.com").first()
    assert u is None


def test_cp12_resend_invite_invalidates_prior_token(client, super_admin, db):
    """Resending an invite invalidates prior tokens and issues a fresh working token."""
    headers = get_auth_headers(client, "super@test.com", "pass")

    # 1. First invite in console mode
    resp1 = client.post("/api/users/invite", json={"email": "resend_test@test.com", "role_tier": "Sales"}, headers=headers)
    assert resp1.status_code == 201
    tok1 = resp1.json()["token"]
    assert tok1 is not None

    u = db.query(User).filter(User.email == "resend_test@test.com").first()
    assert u.is_pending_invite is True

    # 2. Resend invite
    resp2 = client.post(f"/api/users/{u.id}/resend-invite", headers=headers)
    assert resp2.status_code == 200
    tok2 = resp2.json()["token"]
    assert tok2 is not None
    assert tok2 != tok1

    # 3. Attempting to accept with old token tok1 must fail (400)
    fail_resp = client.post("/api/auth/invite/accept", json={"token": tok1, "new_password": "validpassword123"})
    assert fail_resp.status_code == 400
    assert "invalid or expired" in fail_resp.json()["detail"].lower()

    # 4. Accepting with fresh token tok2 must succeed (200)
    success_resp = client.post("/api/auth/invite/accept", json={"token": tok2, "new_password": "validpassword123"})
    assert success_resp.status_code == 200

    # User is now active
    db.refresh(u)
    assert u.enabled is True
    assert u.password_hash is not None
    assert u.is_pending_invite is False

    # Login works
    login_resp = client.post("/api/auth/login", json={"email": "resend_test@test.com", "password": "validpassword123"})
    assert login_resp.status_code == 200


def test_cp12_resend_invite_forbidden_for_non_admin(client, sales_user, super_admin, db):
    """Non-admin users cannot resend invites."""
    admin_headers = get_auth_headers(client, "super@test.com", "pass")
    resp_inv = client.post("/api/users/invite", json={"email": "pending_resend@test.com", "role_tier": "Sales"}, headers=admin_headers)
    assert resp_inv.status_code == 201

    u = db.query(User).filter(User.email == "pending_resend@test.com").first()

    sales_headers = get_auth_headers(client, "sales@test.com", "pass")
    resp_resend = client.post(f"/api/users/{u.id}/resend-invite", headers=sales_headers)
    assert resp_resend.status_code == 403


def test_cp12_resend_invite_fails_for_active_user(client, super_admin, sales_user):
    """Resending an invite for an already active user returns 400 Bad Request."""
    headers = get_auth_headers(client, "super@test.com", "pass")
    resp = client.post(f"/api/users/{sales_user.id}/resend-invite", headers=headers)
    assert resp.status_code == 400
    assert "already activated" in resp.json()["detail"].lower()


def test_invited_user_activation_lifecycle_and_status(client, super_admin, db):
    """
    Verify complete user activation lifecycle:
    1. Newly invited user appears as 'Pending Invite' in GET /api/users.
    2. After accepting invitation, user appears as 'Active' in GET /api/users.
    3. The activated user can log in with new password.
    4. Existing role and permission behavior remains unchanged (e.g. Sales cannot access /api/users).
    """
    admin_headers = get_auth_headers(client, "super@test.com", "pass")

    # 1. Invite a new Sales user
    invite_resp = client.post(
        "/api/users/invite",
        json={"email": "lifecycle_sales@test.com", "role_tier": "Sales"},
        headers=admin_headers
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json().get("token")
    assert token is not None

    # Verify user appears as 'Pending Invite' in GET /api/users
    list_resp1 = client.get("/api/users", headers=admin_headers)
    assert list_resp1.status_code == 200
    user_entry = next((u for u in list_resp1.json() if u["email"] == "lifecycle_sales@test.com"), None)
    assert user_entry is not None
    assert user_entry["is_pending_invite"] is True
    assert user_entry["status"] == "Pending Invite"
    assert user_entry["enabled"] is False

    # 2. User accepts the invitation and sets their password
    accept_resp = client.post(
        "/api/auth/invite/accept",
        json={"token": token, "new_password": "MySecretPassword123!"}
    )
    assert accept_resp.status_code == 200
    assert "activated successfully" in accept_resp.json()["message"].lower()

    # Verify user now appears as 'Active' in GET /api/users
    list_resp2 = client.get("/api/users", headers=admin_headers)
    assert list_resp2.status_code == 200
    user_entry_after = next((u for u in list_resp2.json() if u["email"] == "lifecycle_sales@test.com"), None)
    assert user_entry_after is not None
    assert user_entry_after["is_pending_invite"] is False
    assert user_entry_after["status"] == "Active"
    assert user_entry_after["enabled"] is True

    # 3. The activated user can log in
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "lifecycle_sales@test.com", "password": "MySecretPassword123!"}
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json().get("access_token")
    assert access_token is not None

    # 4. Existing role and permission behavior remains unchanged
    # (Sales role cannot list /api/users, returns 403 Forbidden)
    sales_headers = {"Authorization": f"Bearer {access_token}"}
    forbidden_resp = client.get("/api/users", headers=sales_headers)
    assert forbidden_resp.status_code == 403
