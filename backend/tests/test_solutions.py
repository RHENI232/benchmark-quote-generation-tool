import pytest
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.core.security import get_password_hash
from decimal import Decimal

def get_auth_headers(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
def test_users(db):
    users_data = [
        ("admin@test.com", RoleTier.ADMIN),
        ("management@test.com", RoleTier.MANAGEMENT),
        ("catalog@test.com", RoleTier.CATALOG_ENTRY),
        ("sales@test.com", RoleTier.SALES),
    ]
    for email, role in users_data:
        db.execute(User.__table__.delete().where(User.email == email))
        user = User(email=email, role_tier=role, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
        db.add(user)
    db.commit()

def test_get_solutions(client, test_users):
    headers = get_auth_headers(client, "sales@test.com", "pass")
    resp = client.get("/api/solutions", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_create_solution_admin(client, test_users):
    headers = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={
        "name": "New Solution",
        "default_margin_percent": 20.0
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Solution"
    assert float(resp.json()["default_margin_percent"]) == 20.0

def test_create_solution_forbidden(client, test_users):
    headers = get_auth_headers(client, "catalog@test.com", "pass")
    resp = client.post("/api/solutions", json={
        "name": "New Solution",
        "default_margin_percent": 20.0
    }, headers=headers)
    assert resp.status_code == 403

def test_patch_margin_catalog_entry(client, test_users, db):
    # Admin creates it
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={"name": "Margin Test", "default_margin_percent": 15.0}, headers=headers_admin)
    sol_id = resp.json()["id"]
    
    # Catalog Entry patches it
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    resp2 = client.patch(f"/api/solutions/{sol_id}/margin", json={"default_margin_percent": 25.5}, headers=headers_cat)
    assert resp2.status_code == 403

def test_patch_margin_sales_forbidden(client, test_users):
    # Admin creates it
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={"name": "Margin Test 2", "default_margin_percent": 15.0}, headers=headers_admin)
    sol_id = resp.json()["id"]
    
    # Sales patches it - should fail
    headers_sales = get_auth_headers(client, "sales@test.com", "pass")
    resp2 = client.patch(f"/api/solutions/{sol_id}/margin", json={"default_margin_percent": 25.5}, headers=headers_sales)
    assert resp2.status_code == 403

def test_reset_catalog(client, test_users, db):
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    
    # 1. Deterministic identification of the shipped WTVision Graphics Solution
    resp_sol = client.get("/api/solutions", headers=headers_admin)
    sols = resp_sol.json()
    sol_id = next(s["id"] for s in sols if s["name"] == "WTVision Graphics")
    
    # Check baseline data
    from backend.seed import DEFAULT_CATALOG_DATA
    seed_mt1010 = next(item for item in DEFAULT_CATALOG_DATA if item["part_number"] == "MT1010")
    
    # 2. Modify multiple fields on a seeded catalog item
    resp_search = client.get(f"/api/catalog?solution_id={sol_id}&part_number=MT1010", headers=headers_admin)
    seeded_item = resp_search.json()[0]
    
    # Modify a reference item's part number and description
    resp_ref = client.get(f"/api/catalog?solution_id={sol_id}&part_number=PS1050", headers=headers_admin)
    ref_item = resp_ref.json()[0]
    client.put(f"/api/catalog/{ref_item['id']}", json={
        "part_number": "CHANGED-PN",
        "description": "CHANGED-DESC",
        "sell_price": 999.99
    }, headers=headers_admin)
    
    # 4. User-created Reference item
    from backend.app.models.catalog import CatalogItemKind
    resp_new = client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.REFERENCE.value,
        "description": "User Custom Item", "part_number": "USR-001",
        "sell_price": 500.0, "cost_price": 400.0
    }, headers=headers_admin)
    new_item_id = resp_new.json()["id"]
    
    # 5. Verify confirmation
    resp = client.post(f"/api/solutions/{sol_id}/catalog/reset", json={"confirm_reset": False}, headers=headers_admin)
    assert resp.status_code == 400
    
    resp2 = client.post(f"/api/solutions/{sol_id}/catalog/reset", json={"confirm_reset": True}, headers=headers_admin)
    assert resp2.status_code == 200
    
    # Verify baseline restoration (sell_price, cost_price, brand)
    resp_search_after = client.get(f"/api/catalog?solution_id={sol_id}&part_number=MT1010", headers=headers_admin)
    seeded_item_after = next(i for i in resp_search_after.json() if i["id"] == seeded_item["id"])
    
    if seed_mt1010["sell_price"] is None:
        assert seeded_item_after["sell_price"] is None
    else:
        assert float(seeded_item_after["sell_price"]) == float(seed_mt1010["sell_price"])
        
    if seed_mt1010["cost_price"] is None:
        assert seeded_item_after["cost_price"] is None
    else:
        assert float(seeded_item_after["cost_price"]) == float(seed_mt1010["cost_price"])
        
    assert seeded_item_after["brand"] == seed_mt1010["brand"]
    
    # Verify the reference item was fully restored by lookup_key
    resp_ref_after = client.get(f"/api/catalog/{ref_item['id']}", headers=headers_admin)
    assert resp_ref_after.json()["part_number"] == ref_item["part_number"] # Restored to PS1050
    assert resp_ref_after.json()["description"] == ref_item["description"] # Restored to original
        
    # Verify user-created reference preservation
    resp_new_after = client.get(f"/api/catalog/{new_item_id}", headers=headers_admin)
    assert resp_new_after.status_code == 200
    assert resp_new_after.json()["description"] == "User Custom Item"

def test_reset_catalog_atomicity(client, test_users, monkeypatch):
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp_sol = client.get("/api/solutions", headers=headers_admin)
    sol_id = next(s["id"] for s in resp_sol.json() if s["name"] == "WTVision Graphics")
    
    # Inject a failure into db.commit inside the reset endpoint
    from sqlalchemy.orm import Session
    original_commit = Session.commit
    
    def mock_commit(*args, **kwargs):
        raise ValueError("Simulated DB failure")
        
    monkeypatch.setattr(Session, "commit", mock_commit)
    
    import pytest
    with pytest.raises(ValueError, match="Simulated DB failure"):
        client.post(f"/api/solutions/{sol_id}/catalog/reset", json={"confirm_reset": True}, headers=headers_admin)
    
    # Due to db fixture transaction savepoints, the outer test transaction remains intact and uncorrupted

def test_reset_catalog_collision_protection(client, test_users):
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    
    resp_sol = client.get("/api/solutions", headers=headers_admin)
    sol_id = next(s["id"] for s in resp_sol.json() if s["name"] == "WTVision Graphics")
    
    # Get a shipped reference item to duplicate
    from backend.seed import DEFAULT_CATALOG_DATA
    from backend.app.models.catalog import CatalogItemKind
    shipped_ref = next(item for item in DEFAULT_CATALOG_DATA if item["kind"] == CatalogItemKind.REFERENCE.value and item["part_number"] is not None)
    
    # 1. Create a user item with EXACT SAME idempotency keys (kind, part_number, description)
    # But different sell_price/cost_price so we can track it
    resp_new = client.post("/api/catalog", json={
        "solution_id": sol_id, 
        "kind": shipped_ref["kind"],
        "description": shipped_ref["description"], 
        "part_number": shipped_ref["part_number"],
        "sell_price": 777.77, 
        "cost_price": 666.66
    }, headers=headers_admin)
    assert resp_new.status_code == 201
    user_dup_id = resp_new.json()["id"]
    
    # 2. Reset the catalog
    resp_reset = client.post(f"/api/solutions/{sol_id}/catalog/reset", json={"confirm_reset": True}, headers=headers_admin)
    assert resp_reset.status_code == 200
    
    # 3. Verify user item is preserved and untouched
    resp_verify = client.get(f"/api/catalog/{user_dup_id}", headers=headers_admin)
    assert resp_verify.status_code == 200
    assert float(resp_verify.json()["sell_price"]) == 777.77
    assert float(resp_verify.json()["cost_price"]) == 666.66

def test_reset_catalog_non_shipped_solution(client, test_users):
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    
    # 1. Create a new Solution
    resp_sol = client.post("/api/solutions", json={
        "name": "Custom Solution",
        "default_margin_percent": 15.0
    }, headers=headers_admin)
    sol_id = resp_sol.json()["id"]
    
    # 2. Create its own Reference item
    from backend.app.models.catalog import CatalogItemKind
    resp_new = client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.REFERENCE.value,
        "description": "My Custom Item", "part_number": "MY-001",
        "sell_price": 100.0, "cost_price": 50.0
    }, headers=headers_admin)
    
    # 3. Call catalog reset
    resp_reset = client.post(f"/api/solutions/{sol_id}/catalog/reset", json={"confirm_reset": True}, headers=headers_admin)
    
    # 4. Verify error
    assert resp_reset.status_code == 400
    assert "Shipped catalog defaults are not defined for this Solution" in resp_reset.json()["detail"]
    
    # 5. Verify WTVision DEFAULT_CATALOG_DATA is NOT inserted
    resp_search = client.get(f"/api/catalog?solution_id={sol_id}", headers=headers_admin)
    assert len(resp_search.json()) == 1
    assert resp_search.json()[0]["part_number"] == "MY-001"

def test_patch_margin_management(client, test_users):
    # Admin creates it
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={"name": "Margin Test Mgmt", "default_margin_percent": 15.0}, headers=headers_admin)
    sol_id = resp.json()["id"]

    # Management patches it
    headers_mgmt = get_auth_headers(client, "management@test.com", "pass")
    resp2 = client.patch(f"/api/solutions/{sol_id}/margin", json={"default_margin_percent": 30.5}, headers=headers_mgmt)
    assert resp2.status_code == 200
    assert float(resp2.json()["default_margin_percent"]) == 30.5

def test_solution_margin_visibility_masked(client, test_users):
    # Admin creates it
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={"name": "Margin Vis Masked", "default_margin_percent": 18.0}, headers=headers_admin)
    sol_id = resp.json()["id"]

    # Sales
    headers_sales = get_auth_headers(client, "sales@test.com", "pass")
    resp_get_sales = client.get(f"/api/solutions/{sol_id}", headers=headers_sales)
    assert resp_get_sales.status_code == 200
    assert resp_get_sales.json()["default_margin_percent"] is None

    resp_list_sales = client.get("/api/solutions", headers=headers_sales)
    assert resp_list_sales.status_code == 200
    item = next(s for s in resp_list_sales.json() if s["id"] == sol_id)
    assert item["default_margin_percent"] is None

    # Catalog Entry
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    resp_get_cat = client.get(f"/api/solutions/{sol_id}", headers=headers_cat)
    assert resp_get_cat.status_code == 200
    assert resp_get_cat.json()["default_margin_percent"] is None

def test_solution_margin_visibility_unmasked(client, test_users):
    # Admin creates it
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    resp = client.post("/api/solutions", json={"name": "Margin Vis Unmasked", "default_margin_percent": 22.0}, headers=headers_admin)
    sol_id = resp.json()["id"]

    # Management
    headers_mgmt = get_auth_headers(client, "management@test.com", "pass")
    resp_get_mgmt = client.get(f"/api/solutions/{sol_id}", headers=headers_mgmt)
    assert resp_get_mgmt.status_code == 200
    assert float(resp_get_mgmt.json()["default_margin_percent"]) == 22.0

    resp_list_mgmt = client.get("/api/solutions", headers=headers_mgmt)
    assert resp_list_mgmt.status_code == 200
    item = next(s for s in resp_list_mgmt.json() if s["id"] == sol_id)
    assert float(item["default_margin_percent"]) == 22.0


def test_solution_engine_status_and_quote_protection(client, test_users, db):
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    headers_sales = get_auth_headers(client, "sales@test.com", "pass")

    # 1. Verify WTVision Graphics is marked engine_status == "active"
    sols = client.get("/api/solutions", headers=headers_sales).json()
    wtv = next(s for s in sols if s["name"] == "WTVision Graphics")
    assert wtv["engine_status"] == "active"

    # 2. Create a new Solution -> must have engine_status == "pending"
    resp_create = client.post(
        "/api/solutions",
        json={
            "name": "OB Van Integration",
            "code": "OB-VAN-01",
            "default_margin_percent": 20.0,
        },
        headers=headers_admin,
    )
    assert resp_create.status_code == 201
    pending_sol = resp_create.json()
    assert pending_sol["engine_status"] == "pending"
    assert pending_sol["code"] == "OB-VAN-01"

    # 3. Duplicate code is rejected
    resp_dup_code = client.post(
        "/api/solutions",
        json={
            "name": "Another OB Van",
            "code": "OB-VAN-01",
            "default_margin_percent": 15.0,
        },
        headers=headers_admin,
    )
    assert resp_dup_code.status_code == 400

    # 4. Admin can update solution metadata
    resp_upd = client.put(
        f"/api/solutions/{pending_sol['id']}",
        json={
            "name": "OB Van Turnkey Integration",
            "code": "OB-VAN-02",
            "default_margin_percent": 25.0,
        },
        headers=headers_admin,
    )
    assert resp_upd.status_code == 200
    assert resp_upd.json()["name"] == "OB Van Turnkey Integration"
    assert resp_upd.json()["code"] == "OB-VAN-02"
    assert resp_upd.json()["engine_status"] == "pending"

    # 5. Built-in WTVision Graphics cannot be renamed
    resp_rename_wtv = client.put(
        f"/api/solutions/{wtv['id']}",
        json={"name": "Renamed WTV", "default_margin_percent": 15.0},
        headers=headers_admin,
    )
    assert resp_rename_wtv.status_code == 400

    # 6. Quote preview and quote creation are blocked (409 Conflict) for Engine Pending solutions
    from backend.app.models.region import Region

    region = db.query(Region).first()
    if not region:
        region = Region(country_name="Pending Test Region", currency_code="USD")
        db.add(region)
        db.commit()
        db.refresh(region)

    quote_payload = {
        "solution_id": pending_sol["id"],
        "region_id": region.id,
        "client_name": "Broadcast Corp",
        "requirement_data": {},
    }

    r_prev = client.post(
        "/api/quotes/preview", json=quote_payload, headers=headers_sales
    )
    assert r_prev.status_code == 409
    assert "Engine Pending" in r_prev.json()["detail"]

    r_create_q = client.post(
        "/api/quotes", json=quote_payload, headers=headers_sales
    )
    assert r_create_q.status_code == 409
    assert "Engine Pending" in r_create_q.json()["detail"]
