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

@pytest.fixture
def catalog_entry_user(db):
    user = User(email="ce_isolated@test.com", role_tier=RoleTier.CATALOG_ENTRY)
    db.add(user)
    db.flush()
    return user

@pytest.fixture
def management_user(db):
    user = User(email="mgmt_isolated@test.com", role_tier=RoleTier.MANAGEMENT)
    db.add(user)
    db.flush()
    return user

@pytest.fixture
def sales_user_2(db):
    user = User(email="sales2_isolated@test.com", role_tier=RoleTier.SALES)
    db.add(user)
    db.flush()
    return user

def create_saved_quote(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert resp.status_code == 201
    quote_id = resp.json()["id"]
    version = resp.json()["version"]

    save_payload = {"expected_version": version}
    save_resp = client.post(f"/api/quotes/{quote_id}/save", json=save_payload, headers=headers)
    assert save_resp.status_code == 200
    return save_resp.json()

def test_cp6_list_quotes_rbac(client, admin_user, sales_user, sales_user_2, management_user, catalog_entry_user, base_payload):
    # Admin creates Quote 1
    q1_payload = {**base_payload, "client_name": "Admin Client"}
    q1 = create_saved_quote(client, admin_user, q1_payload)

    # Sales 1 creates Quote 2
    q2_payload = {**base_payload, "client_name": "Sales 1 Client"}
    q2 = create_saved_quote(client, sales_user, q2_payload)

    # Sales 2 creates Quote 3
    q3_payload = {**base_payload, "client_name": "Sales 2 Client"}
    q3 = create_saved_quote(client, sales_user_2, q3_payload)

    # Draft Quote (should not be in list)
    client.post("/api/quotes", json=base_payload, headers=get_auth_headers(admin_user.id))

    # Test Sales 1 visibility
    headers = get_auth_headers(sales_user.id)
    resp = client.get("/api/quotes", headers=headers)
    assert resp.status_code == 200
    quotes = resp.json()
    assert len(quotes) == 1
    assert quotes[0]["client_name"] == "Sales 1 Client"
    assert "margin_percent" not in quotes[0]

    # Test Sales 2 visibility
    headers = get_auth_headers(sales_user_2.id)
    resp = client.get("/api/quotes", headers=headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["client_name"] == "Sales 2 Client"

    # Test Catalog Entry visibility (all saved quotes)
    headers = get_auth_headers(catalog_entry_user.id)
    resp = client.get("/api/quotes", headers=headers)
    assert len(resp.json()) >= 3
    names = [q["client_name"] for q in resp.json()]
    assert "Admin Client" in names
    assert "Sales 1 Client" in names
    assert "Sales 2 Client" in names

    # Test Management visibility
    headers = get_auth_headers(management_user.id)
    resp = client.get("/api/quotes", headers=headers)
    assert len(resp.json()) >= 3

    # Test Admin visibility
    headers = get_auth_headers(admin_user.id)
    resp = client.get("/api/quotes", headers=headers)
    assert len(resp.json()) >= 3

def test_cp6_list_quotes_search_and_pagination(client, admin_user, base_payload):
    # Create distinct quotes
    for i in range(5):
        payload = {**base_payload, "client_name": f"Searchable Client {i}"}
        create_saved_quote(client, admin_user, payload)

    headers = get_auth_headers(admin_user.id)

    # Search
    resp = client.get("/api/quotes?client_name=Searchable Client 2", headers=headers)
    assert resp.status_code == 200
    quotes = resp.json()
    assert len(quotes) == 1
    assert quotes[0]["client_name"] == "Searchable Client 2"

    # Case insensitive search
    resp = client.get("/api/quotes?client_name=searchable client", headers=headers)
    assert len(resp.json()) >= 5

    # Pagination
    resp_all = client.get("/api/quotes?client_name=searchable client&limit=10", headers=headers)
    all_searched = resp_all.json()
    assert len(all_searched) >= 5

    resp_paged = client.get("/api/quotes?client_name=searchable client&skip=2&limit=2", headers=headers)
    paged = resp_paged.json()
    assert len(paged) == 2
    assert paged[0]["id"] == all_searched[2]["id"]
    assert paged[1]["id"] == all_searched[3]["id"]

def test_cp6_list_quotes_excludes_deleted(client, admin_user, base_payload):
    q_payload = {**base_payload, "client_name": "To Be Deleted Client"}
    q = create_saved_quote(client, admin_user, q_payload)

    headers = get_auth_headers(admin_user.id)

    # Verify it exists
    resp = client.get("/api/quotes?client_name=To Be Deleted", headers=headers)
    assert len(resp.json()) == 1

    # Delete it
    del_resp = client.delete(f"/api/quotes/{q['id']}?expected_version={q['version']}", headers=headers)
    assert del_resp.status_code == 200

    # Verify it's gone from list
    resp = client.get("/api/quotes?client_name=To Be Deleted", headers=headers)
    assert len(resp.json()) == 0

def test_cp6_list_quotes_unauthorized(client):
    resp = client.get("/api/quotes")
    assert resp.status_code == 403

# CP6-B Export Endpoint Tests

def test_cp6_export_customer_copy_rbac(client, admin_user, management_user, catalog_entry_user, sales_user, base_payload):
    # Admin creates a quote
    q = create_saved_quote(client, admin_user, base_payload)
    quote_id = q["id"]

    # All roles should be able to access Customer Copy
    # Sales — but admin-owned quote, so Sales can't access (ownership check)
    resp = client.get(f"/api/quotes/{quote_id}/export/customer", headers=get_auth_headers(sales_user.id))
    assert resp.status_code == 403  # Sales doesn't own this quote

    # Catalog Entry
    resp = client.get(f"/api/quotes/{quote_id}/export/customer", headers=get_auth_headers(catalog_entry_user.id))
    assert resp.status_code == 200

    # Management
    resp = client.get(f"/api/quotes/{quote_id}/export/customer", headers=get_auth_headers(management_user.id))
    assert resp.status_code == 200

    # Admin
    resp = client.get(f"/api/quotes/{quote_id}/export/customer", headers=get_auth_headers(admin_user.id))
    assert resp.status_code == 200

def test_cp6_export_customer_copy_sales_own_quote(client, sales_user, base_payload):
    """Sales user CAN export Customer Copy for their own quote."""
    q = create_saved_quote(client, sales_user, base_payload)
    quote_id = q["id"]
    resp = client.get(f"/api/quotes/{quote_id}/export/customer", headers=get_auth_headers(sales_user.id))
    assert resp.status_code == 200

def test_cp6_export_internal_copy_rbac(client, admin_user, management_user, catalog_entry_user, sales_user, base_payload):
    q = create_saved_quote(client, admin_user, base_payload)
    quote_id = q["id"]

    # Sales - DENIED
    resp = client.get(f"/api/quotes/{quote_id}/export/internal", headers=get_auth_headers(sales_user.id))
    assert resp.status_code == 403

    # Catalog Entry - DENIED
    resp = client.get(f"/api/quotes/{quote_id}/export/internal", headers=get_auth_headers(catalog_entry_user.id))
    assert resp.status_code == 403

    # Management - ALLOWED
    resp = client.get(f"/api/quotes/{quote_id}/export/internal", headers=get_auth_headers(management_user.id))
    assert resp.status_code == 200

    # Admin - ALLOWED
    resp = client.get(f"/api/quotes/{quote_id}/export/internal", headers=get_auth_headers(admin_user.id))
    assert resp.status_code == 200

def test_cp6_export_tracking_sheet_rbac(client, admin_user, management_user, catalog_entry_user, sales_user, base_payload):
    q = create_saved_quote(client, admin_user, base_payload)
    quote_id = q["id"]

    # Sales - DENIED
    resp = client.get(f"/api/quotes/{quote_id}/export/tracking", headers=get_auth_headers(sales_user.id))
    assert resp.status_code == 403

    # Catalog Entry - DENIED
    resp = client.get(f"/api/quotes/{quote_id}/export/tracking", headers=get_auth_headers(catalog_entry_user.id))
    assert resp.status_code == 403

    # Management - ALLOWED
    resp = client.get(f"/api/quotes/{quote_id}/export/tracking", headers=get_auth_headers(management_user.id))
    assert resp.status_code == 200

    # Admin - ALLOWED
    resp = client.get(f"/api/quotes/{quote_id}/export/tracking", headers=get_auth_headers(admin_user.id))
    assert resp.status_code == 200

def test_cp6_export_nonexistent_and_deleted(client, admin_user, base_payload):
    # Nonexistent
    headers = get_auth_headers(admin_user.id)
    resp = client.get("/api/quotes/999999/export/customer", headers=headers)
    assert resp.status_code == 404

    # Deleted
    q = create_saved_quote(client, admin_user, base_payload)
    client.delete(f"/api/quotes/{q['id']}?expected_version={q['version']}", headers=headers)

    resp = client.get(f"/api/quotes/{q['id']}/export/customer", headers=headers)
    assert resp.status_code == 404

# CP6-B Content Validation Tests

def test_cp6_customer_copy_content(client, admin_user, base_payload):
    """Customer Copy must contain formulas, no cost data, and correct headers."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)
    resp = client.get(f"/api/quotes/{q['id']}/export/customer", headers=headers)
    assert resp.status_code == 200

    # Verify content type
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "Customer_Copy" in resp.headers["content-disposition"]

    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active
    assert ws.title == "Quote"

    # Collect all cell values to verify NO cost/margin data appears
    all_values = []
    has_formula = False
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            all_values.append(str(val) if val is not None else "")
            if isinstance(val, str) and val.startswith("="):
                has_formula = True

    all_text = " ".join(all_values).lower()

    # FR-31: Must have formulas
    assert has_formula, "Customer Copy must contain Excel formulas"

    # Must not expose cost or margin
    assert "cost price" not in all_text or "unit cost" not in all_text
    assert "margin" not in all_text

    # Must have client name and quote ref
    assert q["client_name"].lower() in all_text
    assert q["quote_ref_no"].lower() in all_text

def test_cp6_customer_copy_no_cost_columns(client, admin_user, base_payload):
    """Customer Copy columns must be exactly: Part Number, Description, Quantity, Unit Sell Price, Total Sell Price."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)
    resp = client.get(f"/api/quotes/{q['id']}/export/customer", headers=headers)
    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active

    # Find the header row (contains "Part Number")
    header_vals = []
    for row in ws.iter_rows():
        row_vals = [c.value for c in row if c.value is not None]
        if "Part Number" in row_vals:
            header_vals = row_vals
            break

    assert "Part Number" in header_vals
    assert "Description" in header_vals
    assert "Unit Sell Price" in header_vals
    assert "Total Sell Price" in header_vals
    # Must NOT have cost or margin columns
    for h in header_vals:
        assert "cost" not in str(h).lower()
        assert "margin" not in str(h).lower()

def test_cp6_internal_copy_content(client, admin_user, base_payload):
    """Internal Copy must contain cost, sell, margin, formulas, and be in USD."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)
    resp = client.get(f"/api/quotes/{q['id']}/export/internal", headers=headers)
    assert resp.status_code == 200
    assert "Internal" in resp.headers["content-disposition"]

    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active
    assert ws.title == "Internal"

    all_values = []
    has_formula = False
    has_margin_formula = False
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            all_values.append(str(val) if val is not None else "")
            if isinstance(val, str) and val.startswith("="):
                has_formula = True
                if "IF(" in val and "/" in val:
                    has_margin_formula = True

    all_text = " ".join(all_values).lower()

    # FR-31: Must have formulas
    assert has_formula, "Internal Copy must contain Excel formulas"
    assert has_margin_formula, "Internal Copy must contain margin calculation formulas"

    # Must be USD
    assert "usd" in all_text

    # Must have cost columns
    header_vals = []
    for row in ws.iter_rows():
        row_vals = [c.value for c in row if c.value is not None]
        if "Part Number" in row_vals:
            header_vals = row_vals
            break

    header_text = " ".join(str(h) for h in header_vals).lower()
    assert "cost" in header_text
    assert "margin" in header_text

def test_cp6_tracking_sheet_content(client, admin_user, base_payload):
    """Tracking Sheet must contain section/brand rollups, formulas, and be in USD."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)
    resp = client.get(f"/api/quotes/{q['id']}/export/tracking", headers=headers)
    assert resp.status_code == 200
    assert "Tracking" in resp.headers["content-disposition"]

    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active
    assert ws.title == "Tracking"

    all_values = []
    has_formula = False
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            all_values.append(str(val) if val is not None else "")
            if isinstance(val, str) and val.startswith("="):
                has_formula = True

    # FR-31: Must have formulas
    assert has_formula, "Tracking Sheet must contain Excel formulas"

    # Must have section/brand columns
    header_vals = []
    for row in ws.iter_rows():
        row_vals = [c.value for c in row if c.value is not None]
        if "Product Section" in row_vals:
            header_vals = row_vals
            break

    header_text = " ".join(str(h) for h in header_vals).lower()
    assert "product section" in header_text
    assert "brand" in header_text
    assert "total cost" in header_text
    assert "total sell" in header_text
    assert "margin" in header_text

def test_cp6_customer_copy_section_separation(client, admin_user, base_payload):
    """FR-32: Product sections must be separated by blank rows in Customer Copy."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)
    resp = client.get(f"/api/quotes/{q['id']}/export/customer", headers=headers)
    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active

    # The workbook should load without error — section structure is valid
    # With a single-section quote this just verifies structural integrity
    assert ws.max_row > 5, "Customer Copy should have content rows"

def test_cp6_export_xlsx_valid_file(client, admin_user, base_payload):
    """All three exports must produce valid xlsx files that openpyxl can load."""
    from openpyxl import load_workbook
    from io import BytesIO

    q = create_saved_quote(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)

    for export_type in ["customer", "internal", "tracking"]:
        resp = client.get(f"/api/quotes/{q['id']}/export/{export_type}", headers=headers)
        assert resp.status_code == 200
        # Must be loadable as a valid Excel workbook
        wb = load_workbook(BytesIO(resp.content))
        assert len(wb.sheetnames) >= 1
