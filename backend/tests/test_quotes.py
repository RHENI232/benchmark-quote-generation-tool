import pytest
import re
from httpx import Response
from decimal import Decimal

from backend.app.models.user import User, RoleTier
from backend.app.models.solution import Solution
from backend.app.models.region import Region
from backend.app.models.quote import Quote, QuoteStatus
from backend.app.core.security import create_access_token

@pytest.fixture
def test_context(db):
    solution = db.query(Solution).first()
    region = db.query(Region).first()
    return {"solution_id": solution.id, "region_id": region.id}

def get_auth_headers(user_id: int):
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_user(db):
    admin = User(
        email="admin_isolated@test.com",
        role_tier=RoleTier.ADMIN,
    )
    db.add(admin)
    db.flush()
    return admin

@pytest.fixture
def sales_user(db):
    sales = User(
        email="sales_isolated@test.com",
        role_tier=RoleTier.SALES,
    )
    db.add(sales)
    db.flush()
    return sales

@pytest.fixture
def base_payload(test_context):
    return {
        "client_name": "New Quote Client",
        "solution_id": test_context["solution_id"],
        "region_id": test_context["region_id"],
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [
                {
                    "studio_index": 0,
                    "studio_type": "Real Set",
                    "number_of_engines": 1
                }
            ]
        }
    }

def test_create_quote_success(client, admin_user, base_payload, db):
    headers = get_auth_headers(admin_user.id)
    response = client.post("/api/quotes", json=base_payload, headers=headers)
    assert response.status_code == 201
    
    data = response.json()
    assert re.fullmatch(r"BBS-\d{4}-\d{6}", data["quote_ref_no"])
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["client_name"] == "New Quote Client"
    
    quote_id = data["id"]
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    assert db_quote is not None
    assert db_quote.quote_ref_no == data["quote_ref_no"]
    assert db_quote.status == QuoteStatus.DRAFT

    assert len(data["line_items"]) > 0

def test_decimal_json_string_serialization(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)
    response = client.post("/api/quotes", json=base_payload, headers=headers)
    assert response.status_code == 201
    
    data = response.json()
    assert isinstance(data["subtotal_sell_usd"], str)
    assert isinstance(data["subtotal_cost_usd"], str)
    assert isinstance(data["tax_amount"], str)
    assert isinstance(data["total_sell_local"], str)
    if len(data["line_items"]) > 0:
        assert isinstance(data["line_items"][0]["unit_sell_price_snapshot"], str)

def test_soft_delete_quote(client, admin_user, base_payload, db):
    headers = get_auth_headers(admin_user.id)
    
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert resp.status_code == 201
    quote_id = resp.json()["id"]
    version = resp.json()["version"]
    
    del_resp = client.delete(f"/api/quotes/{quote_id}?expected_version={version}", headers=headers)
    assert del_resp.status_code == 200
    
    get_resp = client.get(f"/api/quotes/{quote_id}", headers=headers)
    assert get_resp.status_code == 404
    
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    assert db_quote is not None
    assert db_quote.deleted_at is not None

def test_concurrency_version_mismatch_409(client, admin_user, base_payload, db):
    headers = get_auth_headers(admin_user.id)
    
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert resp.status_code == 201
    quote_id = resp.json()["id"]
    correct_version = resp.json()["version"]
    
    stale_version = correct_version - 1
    update_payload = {
        "client_name": "Conflict Name",
        "expected_version": stale_version
    }
    
    put_resp = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 409
    
    db_quote = db.query(Quote).filter(Quote.id == quote_id).first()
    assert db_quote.client_name == "New Quote Client"
    assert db_quote.version == correct_version

def test_save_quote_mutates_status(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)
    
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    quote_id = resp.json()["id"]
    version = resp.json()["version"]
    
    save_payload = {"expected_version": version}
    save_resp = client.post(f"/api/quotes/{quote_id}/save", json=save_payload, headers=headers)
    assert save_resp.status_code == 200
    
    assert save_resp.json()["status"] == "saved"
    new_version = save_resp.json()["version"]
    assert new_version == version + 1
    
    recalc_payload = {
        "requirement_data": base_payload["requirement_data"],
        "expected_version": new_version
    }
    recalc_resp = client.post(f"/api/quotes/{quote_id}/recalculate", json=recalc_payload, headers=headers)
    assert recalc_resp.status_code == 409
    assert "DRAFT" in recalc_resp.json()["detail"]

def test_preview_quote_rollback(client, admin_user, base_payload, db):
    headers = get_auth_headers(admin_user.id)
    initial_count = db.query(Quote).count()
    
    response = client.post("/api/quotes/preview", json=base_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["quote_ref_no"] == "PREVIEW"
    
    final_count = db.query(Quote).count()
    assert final_count == initial_count

def test_get_quote_and_idor(client, admin_user, sales_user, base_payload):
    admin_headers = get_auth_headers(admin_user.id)
    resp = client.post("/api/quotes", json=base_payload, headers=admin_headers)
    quote_id = resp.json()["id"]
    
    get_resp = client.get(f"/api/quotes/{quote_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    
    sales_headers = get_auth_headers(sales_user.id)
    get_sales_resp = client.get(f"/api/quotes/{quote_id}", headers=sales_headers)
    assert get_sales_resp.status_code == 403

def test_update_quote_headers(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    quote_id = resp.json()["id"]
    version = resp.json()["version"]
    
    update_payload = {
        "client_name": "Updated Client",
        "description": "Updated Description",
        "expected_version": version
    }
    put_resp = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["client_name"] == "Updated Client"
    assert data["description"] == "Updated Description"
    assert data["version"] == version + 1

def test_recalculate_quote(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    quote_id = resp.json()["id"]
    version = resp.json()["version"]
    
    new_req = base_payload["requirement_data"]
    new_req["number_of_studios"] = 2
    new_req["studios"].append({
        "studio_index": 1,
        "studio_type": "Real Set",
        "number_of_engines": 1
    })
    
    recalc_payload = {
        "requirement_data": new_req,
        "expected_version": version
    }
    
    recalc_resp = client.post(f"/api/quotes/{quote_id}/recalculate", json=recalc_payload, headers=headers)
    assert recalc_resp.status_code == 200
    assert recalc_resp.json()["version"] == version + 1
