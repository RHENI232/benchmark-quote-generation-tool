import pytest
import io
import openpyxl
from decimal import Decimal
from sqlalchemy import select
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.core.security import get_password_hash
from backend.app.models.catalog import CatalogItemKind

def get_auth_headers(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
def setup_data(client, db):
    # Setup users
    users_data = [
        ("admin@test.com", RoleTier.ADMIN),
        ("mgmt@test.com", RoleTier.MANAGEMENT),
        ("catalog@test.com", RoleTier.CATALOG_ENTRY),
        ("sales@test.com", RoleTier.SALES),
    ]
    for email, role in users_data:
        db.execute(User.__table__.delete().where(User.email == email))
        user = User(email=email, role_tier=role, account_type=AccountType.MANUAL, password_hash=get_password_hash("pass"), enabled=True)
        db.add(user)
    db.commit()
    
    headers_admin = get_auth_headers(client, "admin@test.com", "pass")
    
    # Create solution
    resp = client.post("/api/solutions", json={"name": "Catalog Test Sol", "default_margin_percent": 15.0}, headers=headers_admin)
    sol_id = resp.json()["id"]
    
    return {"sol_id": sol_id, "admin": headers_admin}

def test_cost_visibility_masking(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    # Catalog Entry creates item
    resp_create = client.post("/api/catalog", json={
        "solution_id": sol_id,
        "kind": CatalogItemKind.REFERENCE.value,
        "description": "Test Cost Visibility",
        "sell_price": 100.0,
        "cost_price": 80.0
    }, headers=headers_cat)
    assert resp_create.status_code == 201
    # Mutation response MUST mask cost price
    assert resp_create.json()["cost_price"] is None
    item_id = resp_create.json()["id"]
    
    # Sales fetches
    headers_sales = get_auth_headers(client, "sales@test.com", "pass")
    resp_sales = client.get(f"/api/catalog/{item_id}", headers=headers_sales)
    assert resp_sales.json()["cost_price"] is None
    
    # Catalog Entry fetches
    resp_cat_get = client.get(f"/api/catalog/{item_id}", headers=headers_cat)
    assert resp_cat_get.json()["cost_price"] is None
    
    # Management fetches (sees cost)
    headers_mgmt = get_auth_headers(client, "mgmt@test.com", "pass")
    resp_mgmt = client.get(f"/api/catalog/{item_id}", headers=headers_mgmt)
    assert float(resp_mgmt.json()["cost_price"]) == 80.0

    # Admin fetches (sees cost)
    resp_admin = client.get(f"/api/catalog/{item_id}", headers=setup_data["admin"])
    assert float(resp_admin.json()["cost_price"]) == 80.0

def test_default_margin_auto_calculation(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    # Catalog Entry creates item with omitted cost
    resp_create = client.post("/api/catalog", json={
        "solution_id": sol_id,
        "kind": CatalogItemKind.REFERENCE.value,
        "description": "Auto Margin Test",
        "sell_price": 100.0
    }, headers=headers_cat)
    assert resp_create.status_code == 201
    item_id = resp_create.json()["id"]
    
    # Admin checks the DB cost
    resp_admin = client.get(f"/api/catalog/{item_id}", headers=setup_data["admin"])
    # 100 * (1 - 0.15) = 85
    assert float(resp_admin.json()["cost_price"]) == 85.0

def test_catalog_search(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.REFERENCE.value,
        "description": "UniqueMonitor 4K", "brand": "Sony", "part_number": "SN-4K-01"
    }, headers=headers_cat)
    
    client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.REFERENCE.value,
        "description": "Audio Mixer Unique", "brand": "Yamaha", "part_number": "YM-01"
    }, headers=headers_cat)
    
    # Global search
    headers_sales = get_auth_headers(client, "sales@test.com", "pass")
    r1 = client.get(f"/api/catalog?solution_id={sol_id}&q=Unique", headers=headers_sales)
    assert len(r1.json()) == 2
    
    # Field specific
    r2 = client.get(f"/api/catalog?solution_id={sol_id}&brand=Sony", headers=headers_sales)
    assert len(r2.json()) == 1
    assert r2.json()[0]["description"] == "UniqueMonitor 4K"
    
    r3 = client.get(f"/api/catalog?solution_id={sol_id}&part_number=YM", headers=headers_sales)
    assert len(r3.json()) == 1
    assert r3.json()[0]["part_number"] == "YM-01"

def test_rule_driven_protection(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_admin = setup_data["admin"]
    
    # Create rule driven
    resp = client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.RULE_DRIVEN.value,
        "description": "Engine Core", "part_number": "ENG-001"
    }, headers=headers_admin)
    item_id = resp.json()["id"]
    
    # Try deleting it
    r_del = client.delete(f"/api/catalog/{item_id}", headers=headers_admin)
    assert r_del.status_code == 400
    assert "Implementation safety rule" in r_del.json()["detail"]
    
    # Try modifying part number
    r_update = client.put(f"/api/catalog/{item_id}", json={
        "description": "Updated", "part_number": "ENG-002"
    }, headers=headers_admin)
    assert r_update.status_code == 400

    # Updating description is allowed
    r_update2 = client.put(f"/api/catalog/{item_id}", json={
        "description": "Updated", "part_number": "ENG-001"
    }, headers=headers_admin)
    assert r_update2.status_code == 200

def test_import_catalog(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    # Create an excel file in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Part Number", "Description", "Brand", "Sell Price", "Cost Price"])
    ws.append(["", "NEW-01", "Imported Ref", "TestBrand", 500, 400])
    
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    
    resp = client.post(
        f"/api/catalog/import?solution_id={sol_id}",
        files={"file": ("import.xlsx", out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers_cat
    )
    assert resp.status_code == 200
    
    # Verify it was added
    r_get = client.get(f"/api/catalog?solution_id={sol_id}&part_number=NEW-01", headers=headers_cat)
    items = r_get.json()
    assert len(items) == 1
    assert items[0]["description"] == "Imported Ref"
    assert items[0]["kind"] == CatalogItemKind.REFERENCE.value

def test_import_catalog_rollback_on_invalid(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Part Number", "Description", "Brand", "Sell Price", "Cost Price"])
    ws.append(["", "FAIL-01", "Good Desc", "B", 100, 80])
    ws.append(["", "FAIL-02", "", "B", -10, 80]) # Invalid: No desc, negative price
    
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    
    resp = client.post(
        f"/api/catalog/import?solution_id={sol_id}",
        files={"file": ("import.xlsx", out, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers_cat
    )
    assert resp.status_code == 400
    
    errors = resp.json()["detail"]
    assert len(errors) == 1
    assert errors[0]["row"] == 3
    
    # Verify rollback (FAIL-01 was NOT created)
    r_get = client.get(f"/api/catalog?solution_id={sol_id}&part_number=FAIL-01", headers=headers_cat)
    assert len(r_get.json()) == 0

def test_delete_referenced_catalog_item(client, setup_data, db):
    sol_id = setup_data["sol_id"]
    headers_admin = setup_data["admin"]
    
    # Create catalog item
    resp = client.post("/api/catalog", json={
        "solution_id": sol_id, "kind": CatalogItemKind.REFERENCE.value,
        "description": "Ref Item", "part_number": "REF-001"
    }, headers=headers_admin)
    item_id = resp.json()["id"]
    
    from backend.app.models.quote import Quote, QuoteLineItem
    from backend.app.models.user import User
    from backend.app.models.region import Region
    
    # Create fake region
    region = Region(country_name="Test Region", currency_code="USD")
    db.add(region)
    db.commit()
    db.refresh(region)
    
    user = db.execute(select(User).where(User.email == "admin@test.com")).scalar_one()
    
    # Create Quote
    quote = Quote(
        region_id=region.id, 
        solution_id=sol_id, 
        client_name="Test Client", 
        quote_ref_no="Q-12345", 
        created_by_user_id=user.id, 
        last_edited_by_user_id=user.id
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    # Create QuoteLineItem referencing catalog
    line_item = QuoteLineItem(quote_id=quote.id, catalog_item_id=item_id, description="Ref Item", unit_cost_price_snapshot=0, unit_sell_price_snapshot=0, quantity=1, section="Hardware")
    db.add(line_item)
    db.commit()
    
    # Try deleting it
    r_del = client.delete(f"/api/catalog/{item_id}", headers=headers_admin)
    assert r_del.status_code == 400
    assert "Cannot delete" in r_del.json()["detail"]

def test_catalog_identity_create_update(client, setup_data):
    sol_id = setup_data["sol_id"]
    headers_cat = get_auth_headers(client, "catalog@test.com", "pass")
    
    # 1. Create ignores user-provided lookup_key and generates its own
    resp_create = client.post("/api/catalog", json={
        "solution_id": sol_id,
        "kind": CatalogItemKind.REFERENCE.value,
        "description": "Test Identity",
        "lookup_key": "hacked_key" # Should be ignored
    }, headers=headers_cat)
    assert resp_create.status_code == 201
    
    data = resp_create.json()
    assert "lookup_key" in data
    assert data["lookup_key"] != "hacked_key"
    assert data["lookup_key"].startswith("cat_usr_")
    
    item_id = data["id"]
    original_key = data["lookup_key"]
    
    # 2. Update cannot change lookup_key
    resp_update = client.put(f"/api/catalog/{item_id}", json={
        "description": "Updated Identity",
        "lookup_key": "another_hacked_key" # Should be ignored
    }, headers=headers_cat)
    
    assert resp_update.status_code == 200
    data_up = resp_update.json()
    assert data_up["description"] == "Updated Identity"
    assert data_up["lookup_key"] == original_key # Unchanged
