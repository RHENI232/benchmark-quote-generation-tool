import pytest
from fastapi import APIRouter, Depends
from backend.app.main import app
from backend.app.api.deps import require_permission
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.core.security import get_password_hash
from backend.tests.test_users import get_auth_headers

# Add test routes to verify RBAC
test_router = APIRouter()

@test_router.get("/test/sales", dependencies=[Depends(require_permission("sales_user"))])
def route_sales(): return {"ok": True}

@test_router.get("/test/catalog", dependencies=[Depends(require_permission("catalog_edit"))])
def route_catalog(): return {"ok": True}

@test_router.get("/test/cost", dependencies=[Depends(require_permission("cost_visibility"))])
def route_cost(): return {"ok": True}

@test_router.get("/test/finance", dependencies=[Depends(require_permission("finance_tax_admin"))])
def route_finance(): return {"ok": True}

@test_router.get("/test/solution", dependencies=[Depends(require_permission("solution_admin"))])
def route_solution(): return {"ok": True}

@test_router.get("/test/super", dependencies=[Depends(require_permission("super_admin"))])
def route_super(): return {"ok": True}

app.include_router(test_router)

@pytest.fixture
def users_fixture(db):
    pw = get_password_hash("pass")
    sales = User(email="t_sales@test.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL, password_hash=pw, enabled=True)
    catalog = User(email="t_cat@test.com", role_tier=RoleTier.CATALOG_ENTRY, account_type=AccountType.MANUAL, password_hash=pw, enabled=True)
    management = User(email="t_mgmt@test.com", role_tier=RoleTier.MANAGEMENT, account_type=AccountType.MANUAL, password_hash=pw, enabled=True)
    admin = User(email="t_admin@test.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL, password_hash=pw, enabled=True)
    db.add_all([sales, catalog, management, admin])
    db.commit()
    return {"sales": sales, "catalog": catalog, "management": management, "admin": admin}

def test_sales_rbac(client, users_fixture):
    h = get_auth_headers(client, "t_sales@test.com", "pass")
    assert client.get("/test/sales", headers=h).status_code == 200
    assert client.get("/test/catalog", headers=h).status_code == 403
    assert client.get("/test/cost", headers=h).status_code == 403

def test_catalog_rbac(client, users_fixture):
    h = get_auth_headers(client, "t_cat@test.com", "pass")
    assert client.get("/test/sales", headers=h).status_code == 200
    assert client.get("/test/catalog", headers=h).status_code == 200
    assert client.get("/test/cost", headers=h).status_code == 403

def test_management_rbac(client, users_fixture):
    h = get_auth_headers(client, "t_mgmt@test.com", "pass")
    assert client.get("/test/catalog", headers=h).status_code == 200
    assert client.get("/test/finance", headers=h).status_code == 200
    assert client.get("/test/super", headers=h).status_code == 403

def test_admin_rbac(client, users_fixture):
    h = get_auth_headers(client, "t_admin@test.com", "pass")
    assert client.get("/test/finance", headers=h).status_code == 200
    assert client.get("/test/solution", headers=h).status_code == 200
    assert client.get("/test/super", headers=h).status_code == 200
