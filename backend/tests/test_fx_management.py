import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.models.quote import Quote, QuoteStatus, QuoteLineItem, QuoteApprovalLog
from backend.app.core.security import get_password_hash

def get_auth_headers(client: TestClient, email: str, password: str = "pass"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
def fx_test_users(db):
    users = [
        ("sales_fx@test.com", RoleTier.SALES),
        ("sales_other@test.com", RoleTier.SALES),
        ("catalog_fx@test.com", RoleTier.CATALOG_ENTRY),
        ("mgmt_fx@test.com", RoleTier.MANAGEMENT),
        ("admin_fx@test.com", RoleTier.ADMIN),
    ]
    created = {}
    for email, role in users:
        db.execute(User.__table__.delete().where(User.email == email))
        user = User(
            email=email,
            role_tier=role,
            account_type=AccountType.MANUAL,
            password_hash=get_password_hash("pass"),
            enabled=True
        )
        db.add(user)
        created[email] = user
        if role not in created:
            created[role] = user
    db.commit()
    return created

@pytest.fixture
def fx_quote_fixture(db, fx_test_users):
    solution = db.query(Solution).filter(Solution.name == "WTVision Graphics").first()
    if not solution:
        solution = db.query(Solution).first()

    # Create a non-USD region with an initial rate of 0.012000
    db.execute(Region.__table__.delete().where(Region.country_name == "FX Test India"))
    region = Region(
        country_name="FX Test India",
        currency_code="INR",
        tax_enabled=True,
        tax_rate_percent=Decimal("18.00"),
        fx_rate_to_usd=Decimal("0.012000"),
        fx_rate_as_of="2026-10-01 00:00:00 UTC",
        legal_entity_name="Benchmark Broadcast Systems India"
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    sales_user = fx_test_users["sales_fx@test.com"]

    # Create draft quote
    quote = Quote(
        solution_id=solution.id,
        region_id=region.id,
        client_name="FX Test Client",
        quote_ref_no="FX-TEST-0001",
        version=1,
        status=QuoteStatus.DRAFT,
        currency_code="INR",
        fx_rate_to_usd=Decimal("0.012000"),
        fx_rate_as_of="2026-10-01 00:00:00 UTC",
        tax_enabled=True,
        tax_rate_percent=Decimal("18.00"),
        subtotal_sell_usd=Decimal("1000.00"),
        subtotal_cost_usd=Decimal("800.00"),
        tax_amount=Decimal("15000.00"),
        total_sell_local=Decimal("98333.33"),
        created_by_user_id=sales_user.id,
        last_edited_by_user_id=sales_user.id,
        requirement_data={"number_of_studios": 1, "studios": []}
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)

    line = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        part_number="PART-01",
        description="Test Item Description",
        brand="wTVision",
        section="Graphics",
        sort_order=0,
        quantity=2,
        unit_sell_price_snapshot=Decimal("500.00"),
        unit_cost_price_snapshot=Decimal("400.00"),
        line_sell_total=Decimal("1000.00"),
        line_cost_total=Decimal("800.00"),
        margin_percent=Decimal("20.00")
    )
    db.add(line)
    db.commit()

    return {"region": region, "solution": solution, "quote": quote, "line": line}

def test_regional_fx_update_does_not_affect_existing_drafts(client: TestClient, fx_test_users, fx_quote_fixture, db):
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]

    # Update regional FX rate to 0.013000
    update_payload = {
        "fx_rate_to_usd": 0.013000,
        "currency_code": "INR",
        "fx_rate_as_of": "2026-10-16 10:00:00 UTC"
    }
    resp = client.put(f"/api/regions/{region.id}/fx-rate", json=update_payload, headers=admin_headers)
    assert resp.status_code == 200

    # Verify existing draft quote remains 100% UNCHANGED
    db.refresh(quote)
    assert Decimal(str(quote.fx_rate_to_usd)) == Decimal("0.012000")
    assert Decimal(str(quote.total_sell_local)) == Decimal("98333.33")
    assert quote.fx_rate_as_of == "2026-10-01 00:00:00 UTC"

def test_draft_recalculation_preserves_saved_fx_rate_by_default(client: TestClient, fx_test_users, fx_quote_fixture, db):
    sales_headers = get_auth_headers(client, "sales_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]

    # 1. Update region rate to 0.015000
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.015000, "currency_code": "INR"}, headers=admin_headers)

    # 2. Sales user triggers ordinary quote recalculation
    recalc_payload = {
        "expected_version": quote.version,
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    resp = client.post(f"/api/quotes/{quote.id}/recalculate", json=recalc_payload, headers=sales_headers)
    assert resp.status_code == 200
    data = resp.json()

    # The recalculation MUST PRESERVE the quote's saved FX rate (0.012000), NOT 0.015000!
    assert Decimal(str(data["fx_rate_to_usd"])) == Decimal("0.012000")
    db.refresh(quote)
    assert Decimal(str(quote.fx_rate_to_usd)) == Decimal("0.012000")

def test_draft_edit_preserves_saved_fx_rate_by_default(client: TestClient, fx_test_users, fx_quote_fixture, db):
    sales_headers = get_auth_headers(client, "sales_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]
    solution = fx_quote_fixture["solution"]

    # Update region rate to 0.016000
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.016000, "currency_code": "INR"}, headers=admin_headers)

    # Sales user updates quote client_name and description
    update_payload = {
        "client_name": "Updated Client Name",
        "solution_id": solution.id,
        "region_id": region.id,
        "expected_version": quote.version,
        "description": "Updated Description",
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    resp = client.put(f"/api/quotes/{quote.id}", json=update_payload, headers=sales_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Must preserve saved rate 0.012000
    assert Decimal(str(data["fx_rate_to_usd"])) == Decimal("0.012000")
    db.refresh(quote)
    assert Decimal(str(quote.fx_rate_to_usd)) == Decimal("0.012000")

def test_explicit_fx_refresh_forbidden_for_sales(client: TestClient, fx_test_users, fx_quote_fixture):
    sales_headers = get_auth_headers(client, "sales_fx@test.com")
    quote = fx_quote_fixture["quote"]

    payload = {"expected_version": quote.version, "comment": "Sales attempting refresh"}
    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json=payload, headers=sales_headers)
    assert resp.status_code == 403

def test_explicit_fx_refresh_forbidden_for_catalog_entry(client: TestClient, fx_test_users, fx_quote_fixture):
    cat_headers = get_auth_headers(client, "catalog_fx@test.com")
    quote = fx_quote_fixture["quote"]

    payload = {"expected_version": quote.version}
    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json=payload, headers=cat_headers)
    assert resp.status_code == 403

def test_explicit_fx_refresh_by_management_and_admin_success(client: TestClient, fx_test_users, fx_quote_fixture, db):
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]
    original_line_id = fx_quote_fixture["line"].id

    # 1. Update region rate to 0.012500
    client.put(f"/api/regions/{region.id}/fx-rate", json={
        "fx_rate_to_usd": 0.012500,
        "currency_code": "INR",
        "fx_rate_as_of": "2026-10-16 11:00:00 UTC"
    }, headers=admin_headers)

    initial_version = quote.version

    # 2. Call explicit refresh endpoint as Admin (or Management)
    mgmt_headers = get_auth_headers(client, "mgmt_fx@test.com")
    refresh_payload = {
        "expected_version": initial_version,
        "comment": "Scheduled quarterly rate refresh"
    }
    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json=refresh_payload, headers=mgmt_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify rate was updated
    assert Decimal(str(data["fx_rate_to_usd"])) == Decimal("0.012500")
    assert data["fx_rate_as_of"] == "2026-10-16 11:00:00 UTC"
    assert data["version"] == initial_version + 1

    # Verify BoQ items and quantities are 100% UNTOUCHED (Rule 5)
    db.refresh(quote)
    assert len(quote.line_items) == 1
    assert quote.line_items[0].id == original_line_id
    assert quote.line_items[0].quantity == 2
    assert quote.line_items[0].part_number == "PART-01"
    assert Decimal(str(quote.subtotal_sell_usd)) == Decimal("1000.00")

    # Verify mathematical calculation:
    # subtotal_sell_usd = 1000.00
    # local_sell = 1000 / 0.012500 = 80000.00
    # tax = 80000.00 * 18% = 14400.00
    # total_local = 94400.00
    expected_local = Decimal("94400.00")
    assert abs(Decimal(str(quote.total_sell_local)) - expected_local) < Decimal("0.05")

    # Verify audit log (Rule 6)
    log = db.query(QuoteApprovalLog).filter(
        QuoteApprovalLog.quote_id == quote.id,
        QuoteApprovalLog.action == "REFRESH_FX_RATE"
    ).first()
    assert log is not None
    assert log.quote_version == initial_version + 1
    assert "0.012000" in log.comment
    assert "0.012500" in log.comment
    assert "Scheduled quarterly rate refresh" in log.comment

def test_explicit_fx_refresh_rejected_on_approved_quote(client: TestClient, fx_test_users, fx_quote_fixture, db):
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    quote = fx_quote_fixture["quote"]
    quote.status = QuoteStatus.APPROVED
    db.commit()

    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": quote.version}, headers=admin_headers)
    assert resp.status_code == 409
    assert "immutable" in resp.json()["detail"].lower()

def test_explicit_fx_refresh_rejected_on_pending_approval_quote(client: TestClient, fx_test_users, fx_quote_fixture, db):
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    quote = fx_quote_fixture["quote"]
    quote.status = QuoteStatus.PENDING_APPROVAL
    db.commit()

    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": quote.version}, headers=admin_headers)
    assert resp.status_code == 409
    assert "immutable" in resp.json()["detail"].lower()

def test_explicit_fx_refresh_stale_version_rejected(client: TestClient, fx_test_users, fx_quote_fixture):
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    quote = fx_quote_fixture["quote"]

    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": quote.version + 99}, headers=admin_headers)
    assert resp.status_code == 409
    assert "version mismatch" in resp.json()["detail"].lower()

def test_fx_refresh_numerical_accuracy_and_no_double_tax(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify numerical conversion:
    total_sell_local = (subtotal_sell_usd / fx_rate_to_usd) + tax_amount
    tax_amount = (subtotal_sell_usd / fx_rate_to_usd) * (tax_rate / 100)
    Verify consecutive refreshes never double-apply or compound tax.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]

    # Base USD values:
    # subtotal_sell_usd = 1000.00
    # tax_rate_percent = 18.00%
    assert Decimal(str(quote.subtotal_sell_usd)) == Decimal("1000.00")
    assert Decimal(str(quote.tax_rate_percent)) == Decimal("18.00")

    # Step 1: Set regional FX to 0.010000 (1 USD = 100 INR)
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.010000, "currency_code": "INR"}, headers=admin_headers)
    resp1 = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": quote.version}, headers=admin_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Pre-tax local: 1000.00 / 0.010000 = 100,000.00
    # Tax amount: 100,000.00 * 0.18 = 18,000.00
    # Total local: 100,000.00 + 18,000.00 = 118,000.00
    expected_pretax_1 = Decimal("100000.00")
    expected_tax_1 = Decimal("18000.00")
    expected_total_1 = Decimal("118000.00")
    assert abs(Decimal(str(data1["tax_amount"])) - expected_tax_1) < Decimal("0.01")
    assert abs(Decimal(str(data1["total_sell_local"])) - expected_total_1) < Decimal("0.01")

    # Step 2: Set regional FX to 0.020000 (1 USD = 50 INR)
    # Consecutive refresh: must compute cleanly from subtotal_sell_usd, NEVER compound prior tax!
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.020000, "currency_code": "INR"}, headers=admin_headers)
    resp2 = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": data1["version"]}, headers=admin_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Pre-tax local: 1000.00 / 0.020000 = 50,000.00
    # Tax amount: 50,000.00 * 0.18 = 9,000.00
    # Total local: 50,000.00 + 9,000.00 = 59,000.00
    expected_pretax_2 = Decimal("50000.00")
    expected_tax_2 = Decimal("9000.00")
    expected_total_2 = Decimal("59000.00")
    assert abs(Decimal(str(data2["tax_amount"])) - expected_tax_2) < Decimal("0.01")
    assert abs(Decimal(str(data2["total_sell_local"])) - expected_total_2) < Decimal("0.01")

    # Step 3: Test quote with tax disabled
    db.refresh(quote)
    quote.tax_enabled = False
    db.commit()

    resp3 = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": quote.version}, headers=admin_headers)
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert Decimal(str(data3["tax_amount"])) == Decimal("0.0")
    assert abs(Decimal(str(data3["total_sell_local"])) - expected_pretax_2) < Decimal("0.01")

def test_fx_refresh_deep_quote_integrity_and_line_item_immutability(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify quote integrity during FX refresh:
    - Existing line items remain 100% unchanged.
    - Catalog snapshots, unit prices, cost snapshots, brands, descriptions remain intact.
    - Quote metadata, client_name, requirement_data, currency, tax settings remain intact.
    - Only intended FX-related values change.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]
    original_line = fx_quote_fixture["line"]

    # Snapshot pre-refresh state
    pre_line_id = original_line.id
    pre_catalog_item_id = original_line.catalog_item_id
    pre_part_number = original_line.part_number
    pre_description = original_line.description
    pre_brand = original_line.brand
    pre_section = original_line.section
    pre_sort_order = original_line.sort_order
    pre_quantity = original_line.quantity
    pre_unit_sell = original_line.unit_sell_price_snapshot
    pre_unit_cost = original_line.unit_cost_price_snapshot
    pre_line_sell_total = original_line.line_sell_total
    pre_line_cost_total = original_line.line_cost_total
    pre_margin = original_line.margin_percent

    pre_client_name = quote.client_name
    pre_attention = quote.attention
    pre_description_quote = quote.description
    pre_requirement_data = quote.requirement_data
    pre_currency_code = quote.currency_code
    pre_subtotal_sell_usd = quote.subtotal_sell_usd
    pre_subtotal_cost_usd = quote.subtotal_cost_usd
    pre_tax_enabled = quote.tax_enabled
    pre_tax_rate_percent = quote.tax_rate_percent
    pre_status = quote.status
    pre_version = quote.version

    # Update regional FX
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.014000, "currency_code": "INR"}, headers=admin_headers)

    # Refresh quote FX
    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": pre_version}, headers=admin_headers)
    assert resp.status_code == 200

    db.refresh(quote)
    db.refresh(original_line)

    # Line item assertions - ALL fields must match pre-refresh state
    assert len(quote.line_items) == 1
    post_line = quote.line_items[0]
    assert post_line.id == pre_line_id
    assert post_line.catalog_item_id == pre_catalog_item_id
    assert post_line.part_number == pre_part_number
    assert post_line.description == pre_description
    assert post_line.brand == pre_brand
    assert post_line.section == pre_section
    assert post_line.sort_order == pre_sort_order
    assert post_line.quantity == pre_quantity
    assert post_line.unit_sell_price_snapshot == pre_unit_sell
    assert post_line.unit_cost_price_snapshot == pre_unit_cost
    assert post_line.line_sell_total == pre_line_sell_total
    assert post_line.line_cost_total == pre_line_cost_total
    assert post_line.margin_percent == pre_margin

    # Quote header assertions - un-impacted fields must remain identical
    assert quote.client_name == pre_client_name
    assert quote.attention == pre_attention
    assert quote.description == pre_description_quote
    assert quote.requirement_data == pre_requirement_data
    assert quote.currency_code == pre_currency_code
    assert quote.subtotal_sell_usd == pre_subtotal_sell_usd
    assert quote.subtotal_cost_usd == pre_subtotal_cost_usd
    assert quote.tax_enabled == pre_tax_enabled
    assert quote.tax_rate_percent == pre_tax_rate_percent
    assert quote.status == pre_status

    # Only FX-related fields changed
    assert Decimal(str(quote.fx_rate_to_usd)) == Decimal("0.014000")
    assert quote.version == pre_version + 1

def test_fx_refresh_atomicity_and_failure_rollback(client: TestClient, fx_test_users, fx_quote_fixture, db, monkeypatch):
    """
    Verify atomicity:
    Simulate a failure during refresh after changes have been staged.
    Confirm quote values, version, and audit log all roll back completely.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]

    pre_version = quote.version
    pre_fx_rate = quote.fx_rate_to_usd
    pre_total_sell_local = quote.total_sell_local
    pre_tax_amount = quote.tax_amount

    # Update regional FX to 0.015000
    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.015000, "currency_code": "INR"}, headers=admin_headers)

    # Monkeypatch _log_approval to simulate an unexpected database error after staging quote modifications
    from backend.app.api.routers import quotes as quotes_router
    def mock_fail_log(*args, **kwargs):
        raise RuntimeError("Simulated database failure during audit log insertion")

    monkeypatch.setattr(quotes_router, "_log_approval", mock_fail_log)

    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": pre_version}, headers=admin_headers)
    assert resp.status_code == 500

    # Verify complete rollback
    db.expire_all()
    quote_after = db.query(Quote).filter(Quote.id == quote.id).first()
    assert quote_after.version == pre_version
    assert quote_after.fx_rate_to_usd == pre_fx_rate
    assert quote_after.total_sell_local == pre_total_sell_local
    assert quote_after.tax_amount == pre_tax_amount

    # Verify no audit log entry was created
    failed_log = db.query(QuoteApprovalLog).filter(
        QuoteApprovalLog.quote_id == quote.id,
        QuoteApprovalLog.action == "REFRESH_FX_RATE"
    ).first()
    assert failed_log is None

def test_stale_version_leaves_quote_and_database_untouched(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify that a stale-version refresh request leaves quote data and version unchanged.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]
    quote = fx_quote_fixture["quote"]

    pre_version = quote.version
    pre_fx_rate = quote.fx_rate_to_usd
    pre_total_local = quote.total_sell_local

    client.put(f"/api/regions/{region.id}/fx-rate", json={"fx_rate_to_usd": 0.018000, "currency_code": "INR"}, headers=admin_headers)

    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json={"expected_version": pre_version + 99}, headers=admin_headers)
    assert resp.status_code == 409

    db.expire_all()
    quote_after = db.query(Quote).filter(Quote.id == quote.id).first()
    assert quote_after.version == pre_version
    assert quote_after.fx_rate_to_usd == pre_fx_rate
    assert quote_after.total_sell_local == pre_total_local

def test_sales_user_permitted_draft_edit_but_isolated(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify authorization boundaries:
    - Sales user can edit their own draft quote normally.
    - Another sales user is forbidden from editing this quote.
    """
    sales_headers = get_auth_headers(client, "sales_fx@test.com")
    other_sales_headers = get_auth_headers(client, "sales_other@test.com")
    quote = fx_quote_fixture["quote"]
    region = fx_quote_fixture["region"]
    solution = fx_quote_fixture["solution"]

    # 1. Other sales user attempts to edit -> 403 Forbidden
    other_payload = {
        "client_name": "Unauthorized Attempt",
        "solution_id": solution.id,
        "region_id": region.id,
        "expected_version": quote.version,
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    resp_other = client.put(f"/api/quotes/{quote.id}", json=other_payload, headers=other_sales_headers)
    assert resp_other.status_code == 403

    # 2. Owner sales user edits own draft -> 200 OK
    own_payload = {
        "client_name": "Authorized Owner Update",
        "solution_id": solution.id,
        "region_id": region.id,
        "expected_version": quote.version,
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    resp_own = client.put(f"/api/quotes/{quote.id}", json=own_payload, headers=sales_headers)
    assert resp_own.status_code == 200
    assert resp_own.json()["client_name"] == "Authorized Owner Update"

def test_newly_created_quote_snapshots_current_regional_fx_rate(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify that a newly created quote via POST /api/quotes snapshots the region's current FX rate.
    """
    sales_headers = get_auth_headers(client, "sales_fx@test.com")
    region = fx_quote_fixture["region"]
    solution = fx_quote_fixture["solution"]

    create_payload = {
        "client_name": "New FX Test Client",
        "solution_id": solution.id,
        "region_id": region.id,
        "attention": "Presales Team",
        "description": "Quote testing snapshot capture",
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    resp = client.post("/api/quotes", json=create_payload, headers=sales_headers)
    assert resp.status_code == 201
    data = resp.json()

    assert Decimal(str(data["fx_rate_to_usd"])) == Decimal(str(region.fx_rate_to_usd))
    assert data["currency_code"] == region.currency_code
    assert data["version"] == 1

def test_explicit_fx_refresh_on_changes_requested_quote_success(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify that an authorized user can refresh FX rate on a quote in CHANGES_REQUESTED status.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    quote = fx_quote_fixture["quote"]
    region = fx_quote_fixture["region"]

    # Transition quote to CHANGES_REQUESTED
    quote.status = QuoteStatus.CHANGES_REQUESTED
    db.commit()

    # Update region FX rate
    client.put(f"/api/regions/{region.id}/fx-rate", json={
        "fx_rate_to_usd": 0.013500,
        "currency_code": "INR",
        "fx_rate_as_of": "2026-10-16 14:00:00 UTC"
    }, headers=admin_headers)

    initial_version = quote.version
    refresh_payload = {
        "expected_version": initial_version,
        "comment": "Updating rate while in changes requested"
    }
    resp = client.post(f"/api/quotes/{quote.id}/refresh-fx", json=refresh_payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert Decimal(str(data["fx_rate_to_usd"])) == Decimal("0.013500")
    assert data["version"] == initial_version + 1
    assert data["status"] == "changes_requested"

def test_region_fx_update_notes_acceptance_and_limitation(client: TestClient, fx_test_users, fx_quote_fixture, db):
    """
    Verify notes parameter behavior:
    PUT /api/regions/{id}/fx-rate accepts notes without validation error,
    but confirms notes is not a persisted column on the regions table.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]

    payload = {
        "fx_rate_to_usd": 0.012800,
        "currency_code": "INR",
        "notes": "Q4 Approved Financial Rate"
    }
    resp = client.put(f"/api/regions/{region.id}/fx-rate", json=payload, headers=admin_headers)
    assert resp.status_code == 200

    from sqlalchemy import inspect
    mapper = inspect(Region)
    column_names = [col.key for col in mapper.columns]
    assert "notes" not in column_names, "Region model should not have a notes column in current schema"

def test_region_fx_update_rejects_nan_and_infinity(client: TestClient, fx_test_users, fx_quote_fixture):
    """
    Verify that NaN and Infinity are rejected with 422 Unprocessable Entity.
    """
    admin_headers = get_auth_headers(client, "admin_fx@test.com")
    region = fx_quote_fixture["region"]

    # String representation of NaN
    resp_nan = client.put(f"/api/regions/{region.id}/fx-rate", json={
        "fx_rate_to_usd": "NaN",
        "currency_code": "INR"
    }, headers=admin_headers)
    assert resp_nan.status_code == 422

    # String representation of Infinity
    resp_inf = client.put(f"/api/regions/{region.id}/fx-rate", json={
        "fx_rate_to_usd": "Infinity",
        "currency_code": "INR"
    }, headers=admin_headers)
    assert resp_inf.status_code == 422
