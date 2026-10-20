import pytest
from decimal import Decimal
import datetime
from sqlalchemy.orm import Session

from backend.app.models.user import User, RoleTier
from backend.app.models.solution import Solution
from backend.app.models.region import Region
from backend.app.models.quote import Quote, QuoteStatus, QuoteRevision
from backend.app.core.security import create_access_token


@pytest.fixture(autouse=True)
def verify_test_database(db):
    """Enforce strict safety check: Tests must ONLY run on benchmark_test_db."""
    db_name = db.bind.engine.url.database if hasattr(db.bind, "engine") else db.bind.url.database
    assert db_name == "benchmark_test_db", f"Safety violation: database is {db_name}, not benchmark_test_db"


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
    user = User(
        email=f"admin_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.ADMIN,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def management_user(db):
    user = User(
        email=f"mgmt_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.MANAGEMENT,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def catalog_entry_user(db):
    user = User(
        email=f"cat_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.CATALOG_ENTRY,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def sales_user(db):
    user = User(
        email=f"sales_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_sales_user(db):
    user = User(
        email=f"other_sales_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def disabled_user(db):
    user = User(
        email=f"disabled_cp17_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=False,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def base_payload(test_context):
    return {
        "client_name": "CP17 Initial Client",
        "attention": "Initial Attention",
        "description": "Initial Description",
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


def create_quote_with_modifications(client, user, base_payload):
    """
    Creates a quote and generates revisions:
    Rev 1: INITIAL_CREATION (1 studio, 1 engine, initial client name)
    Rev 2: EDIT (modified client name, 2 engines -> modified quantity/price, added ingest -> added line items)
    Rev 3: SUBMIT
    """
    headers = get_auth_headers(user.id)
    # Rev 1: INITIAL_CREATION
    r1 = client.post("/api/quotes", json=base_payload, headers=headers)
    assert r1.status_code == 201, r1.text
    q_data = r1.json()
    quote_id = q_data["id"]

    # Rev 2: EDIT (Increase engines to 2, add ingest, change client name)
    edit_payload = {
        **base_payload,
        "client_name": "CP17 Modified Client",
        "attention": "Updated Attention",
        "expected_version": q_data["version"],
        "change_reason": "Expanded scope to 2 engines with ingest",
        "requirement_data": {
            "number_of_studios": 1,
            "sdi_production_ingest": True,
            "ingest_channels": 4,
            "studios": [
                {
                    "studio_index": 0,
                    "studio_type": "Real Set",
                    "number_of_engines": 2
                }
            ]
        }
    }
    r2 = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=headers)
    assert r2.status_code == 200, r2.text
    q_data = r2.json()

    # Rev 3: SUBMIT
    submit_payload = {
        "expected_version": q_data["version"],
        "comment": "Submitting for CP17 comparison testing"
    }
    r3 = client.post(f"/api/quotes/{quote_id}/submit", json=submit_payload, headers=headers)
    assert r3.status_code == 200, r3.text

    return quote_id


# =========================================================================
# 1. IDENTICAL REVISION COMPARISON
# =========================================================================

def test_compare_identical_revisions(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Compare Rev 1 with Rev 1
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=1",
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    assert diff["quote_id"] == quote_id
    assert diff["base_revision"]["revision_number"] == 1
    assert diff["target_revision"]["revision_number"] == 1
    assert diff["has_changes"] is False
    assert diff["metadata_changes"] == {}
    assert diff["requirement_changes"] == {}
    assert diff["financial_changes"] == {}
    assert diff["legal_entity_changes"] == {}

    line_items = diff["line_items"]
    assert line_items["total_added"] == 0
    assert line_items["total_removed"] == 0
    assert line_items["total_modified"] == 0
    assert line_items["total_unchanged"] > 0
    assert len(line_items["added"]) == 0
    assert len(line_items["removed"]) == 0
    assert len(line_items["modified"]) == 0
    assert len(line_items["unchanged"]) == line_items["total_unchanged"]


# =========================================================================
# 2. LINE ITEM ADDITIONS, REMOVALS, AND MODIFICATIONS
# =========================================================================

def test_compare_line_items_added_and_modified(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Compare Rev 1 (1 engine, no ingest) to Rev 2 (2 engines, with ingest)
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    assert diff["has_changes"] is True
    line_items = diff["line_items"]

    # 1. Added items: Ingest items should be added
    assert line_items["total_added"] > 0
    added_descriptions = [item["description"] for item in line_items["added"]]
    assert any("Ingest" in desc for desc in added_descriptions)
    for item in line_items["added"]:
        assert item["status"] == "added"
        assert item["quantity_old"] is None
        assert item["quantity_new"] is not None
        assert item["unit_sell_price_old"] is None
        assert item["unit_sell_price_new"] is not None

    # 2. Modified items: Graphics engine quantity was increased from 1 to 2
    assert line_items["total_modified"] > 0
    modified_item = next(
        (it for it in line_items["modified"] if "Graphics Engine" in it["description"]),
        None
    )
    assert modified_item is not None
    assert modified_item["status"] == "modified"
    assert modified_item["quantity_old"] == 1
    assert modified_item["quantity_new"] == 2
    assert "quantity" in modified_item["field_changes"]
    assert modified_item["field_changes"]["quantity"]["old"] == 1
    assert modified_item["field_changes"]["quantity"]["new"] == 2


def test_compare_line_items_removed_in_reverse_comparison(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Compare Rev 2 (with ingest) to Rev 1 (without ingest)
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=2&target_revision=1",
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    assert diff["has_changes"] is True
    line_items = diff["line_items"]

    # Ingest items must now be reported as removed
    assert line_items["total_removed"] > 0
    removed_descriptions = [item["description"] for item in line_items["removed"]]
    assert any("Ingest" in desc for desc in removed_descriptions)
    for item in line_items["removed"]:
        assert item["status"] == "removed"
        assert item["quantity_old"] is not None
        assert item["quantity_new"] is None


# =========================================================================
# 3. METADATA, REQUIREMENTS, AND FINANCIAL CHANGES
# =========================================================================

def test_compare_metadata_and_requirements(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    # Metadata changes
    meta = diff["metadata_changes"]
    assert "client_name" in meta
    assert meta["client_name"]["old"] == "CP17 Initial Client"
    assert meta["client_name"]["new"] == "CP17 Modified Client"
    assert meta["client_name"]["changed"] is True

    assert "attention" in meta
    assert meta["attention"]["old"] == "Initial Attention"
    assert meta["attention"]["new"] == "Updated Attention"

    # Requirement changes
    req = diff["requirement_changes"]
    assert "sdi_production_ingest" in req
    assert req["sdi_production_ingest"]["old"] is None or req["sdi_production_ingest"]["old"] is False
    assert req["sdi_production_ingest"]["new"] is True


def test_compare_status_change_metadata(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Compare Rev 2 (EDIT, status: draft) to Rev 3 (SUBMIT, status: pending_approval)
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=2&target_revision=3",
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    meta = diff["metadata_changes"]
    assert "status" in meta
    assert meta["status"]["old"] == "draft"
    assert meta["status"]["new"] == "pending_approval"


# =========================================================================
# 4. ROLE-BASED FINANCIAL CONFIDENTIALITY AND MASKING
# =========================================================================

def test_cost_masking_for_sales_and_catalog_entry_comparison(
    client, sales_user, catalog_entry_user, base_payload
):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)

    # 1. Sales User comparison
    sales_headers = get_auth_headers(sales_user.id)
    resp_sales = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=sales_headers
    )
    assert resp_sales.status_code == 200
    diff_sales = resp_sales.json()

    # Financials must NOT include subtotal_cost_usd diff
    assert "subtotal_cost_usd" not in diff_sales["financial_changes"]
    # Sell subtotal and local sell total ARE present
    assert "subtotal_sell_usd" in diff_sales["financial_changes"]

    # Line items: added, removed, modified, unchanged MUST have cost fields nulled
    all_line_items = (
        diff_sales["line_items"]["added"]
        + diff_sales["line_items"]["removed"]
        + diff_sales["line_items"]["modified"]
        + diff_sales["line_items"]["unchanged"]
    )
    for it in all_line_items:
        assert it["unit_cost_price_old"] is None
        assert it["unit_cost_price_new"] is None
        assert it["line_cost_total_old"] is None
        assert it["line_cost_total_new"] is None
        assert it["margin_percent_old"] is None
        assert it["margin_percent_new"] is None
        # Sell prices are visible
        if it["status"] != "added":
            assert it["unit_sell_price_old"] is not None
        if it["status"] != "removed":
            assert it["unit_sell_price_new"] is not None

    # In field_changes for modified items, cost/margin changes must NEVER appear
    for it in diff_sales["line_items"]["modified"]:
        assert "unit_cost_price_snapshot" not in it["field_changes"]
        assert "line_cost_total" not in it["field_changes"]
        assert "margin_percent" not in it["field_changes"]

    # 2. Catalog Entry User comparison (Catalog Entry has NO cost visibility on saved quotes)
    cat_headers = get_auth_headers(catalog_entry_user.id)
    resp_cat = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=cat_headers
    )
    assert resp_cat.status_code == 200
    diff_cat = resp_cat.json()
    assert "subtotal_cost_usd" not in diff_cat["financial_changes"]
    for it in diff_cat["line_items"]["modified"]:
        assert "unit_cost_price_snapshot" not in it["field_changes"]


def test_cost_visibility_for_management_and_admin_comparison(
    client, sales_user, management_user, admin_user, base_payload
):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)

    # 1. Management User can see cost differences
    mgmt_headers = get_auth_headers(management_user.id)
    resp_mgmt = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=mgmt_headers
    )
    assert resp_mgmt.status_code == 200
    diff_mgmt = resp_mgmt.json()

    # Cost subtotal change is visible
    assert "subtotal_cost_usd" in diff_mgmt["financial_changes"]
    assert diff_mgmt["financial_changes"]["subtotal_cost_usd"]["old"] is not None
    assert diff_mgmt["financial_changes"]["subtotal_cost_usd"]["new"] is not None

    # Line items have cost prices
    for it in diff_mgmt["line_items"]["added"]:
        assert it["unit_cost_price_new"] is not None
        assert it["line_cost_total_new"] is not None

    # 2. Admin User can see cost differences
    admin_headers = get_auth_headers(admin_user.id)
    resp_admin = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=admin_headers
    )
    assert resp_admin.status_code == 200
    diff_admin = resp_admin.json()
    assert "subtotal_cost_usd" in diff_admin["financial_changes"]


# =========================================================================
# 5. AUTHORIZATION AND OWNERSHIP ENFORCEMENT
# =========================================================================

def test_sales_user_cannot_compare_other_users_quote_revisions(
    client, sales_user, other_sales_user, base_payload
):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    other_headers = get_auth_headers(other_sales_user.id)

    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=other_headers
    )
    assert resp.status_code == 403
    assert "forbidden" in resp.json()["detail"].lower()


def test_non_sales_roles_can_compare_any_quote_revisions(
    client, sales_user, catalog_entry_user, management_user, admin_user, base_payload
):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)

    for role_user in [catalog_entry_user, management_user, admin_user]:
        headers = get_auth_headers(role_user.id)
        resp = client.get(
            f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
            headers=headers
        )
        assert resp.status_code == 200


def test_unauthenticated_and_disabled_users_blocked_from_comparison(
    client, sales_user, disabled_user, base_payload
):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)

    # 1. Unauthenticated request
    resp_unauth = client.get(f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2")
    assert resp_unauth.status_code in (401, 403)

    # 2. Inactive user request
    disabled_headers = get_auth_headers(disabled_user.id)
    resp_disabled = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=disabled_headers
    )
    assert resp_disabled.status_code == 403
    assert resp_disabled.json()["detail"] == "Inactive user"


# =========================================================================
# 6. NONEXISTENT QUOTE, REVISIONS, AND CROSS-QUOTE REJECTIONS
# =========================================================================

def test_nonexistent_quote_returns_404(client, admin_user):
    headers = get_auth_headers(admin_user.id)
    resp = client.get(
        "/api/quotes/999999/revisions/compare?base_revision=1&target_revision=2",
        headers=headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Quote not found"


def test_nonexistent_revision_returns_404(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Target revision 999 does not exist
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=999",
        headers=headers
    )
    assert resp.status_code == 404

    # Base revision 999 does not exist
    resp2 = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=999&target_revision=1",
        headers=headers
    )
    assert resp2.status_code == 404

    # Non-positive revision numbers
    resp_zero = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=0&target_revision=1",
        headers=headers
    )
    assert resp_zero.status_code == 404


def test_missing_query_parameters_returns_400(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Missing target_revision
    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1",
        headers=headers
    )
    assert resp.status_code == 400
    assert "requires two revision numbers" in resp.json()["detail"]

    # Missing all parameters
    resp2 = client.get(
        f"/api/quotes/{quote_id}/revisions/compare",
        headers=headers
    )
    assert resp2.status_code == 400


def test_cross_quote_revision_comparison_rejected(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)

    # Quote A: has 3 revisions (1, 2, 3)
    quote_a_id = create_quote_with_modifications(client, admin_user, base_payload)

    # Quote B: has only 1 revision (1)
    payload_b = {**base_payload, "client_name": "Quote B Client"}
    rb = client.post("/api/quotes", json=payload_b, headers=headers)
    assert rb.status_code == 201
    quote_b_id = rb.json()["id"]

    # Attempt to compare Revision 1 and Revision 2 under Quote B (Revision 2 belongs to Quote A)
    resp = client.get(
        f"/api/quotes/{quote_b_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=headers
    )
    assert resp.status_code == 404


def test_soft_deleted_quote_comparison_returns_404(client, admin_user, base_payload, db):
    quote_id = create_quote_with_modifications(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    quote.deleted_at = datetime.datetime.utcnow()
    db.commit()

    resp = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
        headers=headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Quote not found"


# =========================================================================
# 7. ROUTE COMPATIBILITY: QUERY PARAMS AND PATH ALIAS
# =========================================================================

def test_query_param_aliases_and_path_route(client, sales_user, base_payload):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # 1. from_revision & to_revision alias
    r1 = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?from_revision=1&to_revision=2",
        headers=headers
    )
    assert r1.status_code == 200
    assert r1.json()["base_revision"]["revision_number"] == 1
    assert r1.json()["target_revision"]["revision_number"] == 2

    # 2. rev_a & rev_b alias
    r2 = client.get(
        f"/api/quotes/{quote_id}/revisions/compare?rev_a=1&rev_b=2",
        headers=headers
    )
    assert r2.status_code == 200

    # 3. Path-based route: /revisions/{base}/compare/{target}
    r3 = client.get(
        f"/api/quotes/{quote_id}/revisions/1/compare/2",
        headers=headers
    )
    assert r3.status_code == 200
    assert r3.json()["base_revision"]["revision_number"] == 1
    assert r3.json()["target_revision"]["revision_number"] == 2


# =========================================================================
# 8. READ-ONLY INVARIANT: COMPARISON DOES NOT MUTATE STATE
# =========================================================================

def test_comparison_does_not_mutate_quote_or_revision_records(client, sales_user, base_payload, db):
    quote_id = create_quote_with_modifications(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Record baseline state directly from database
    quote_before = db.query(Quote).filter(Quote.id == quote_id).first()
    revs_before = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).all()

    q_ver_before = quote_before.version
    q_updated_before = quote_before.updated_at
    rev_count_before = len(revs_before)
    rev_snapshots_before = [r.snapshot_data for r in revs_before]

    # Perform repeated comparison calls
    for _ in range(5):
        resp = client.get(
            f"/api/quotes/{quote_id}/revisions/compare?base_revision=1&target_revision=2",
            headers=headers
        )
        assert resp.status_code == 200

    # Refresh quote from DB and verify immutability
    db.expire_all()
    quote_after = db.query(Quote).filter(Quote.id == quote_id).first()
    revs_after = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).all()

    assert quote_after.version == q_ver_before
    assert quote_after.updated_at == q_updated_before
    assert len(revs_after) == rev_count_before
    for i, r in enumerate(revs_after):
        assert r.snapshot_data == rev_snapshots_before[i]

