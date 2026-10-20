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
        email=f"admin_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.ADMIN,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def management_user(db):
    user = User(
        email=f"mgmt_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.MANAGEMENT,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def catalog_entry_user(db):
    user = User(
        email=f"cat_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.CATALOG_ENTRY,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def sales_user(db):
    user = User(
        email=f"sales_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_sales_user(db):
    user = User(
        email=f"other_sales_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def disabled_user(db):
    user = User(
        email=f"disabled_cp16_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=False,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def base_payload(test_context):
    return {
        "client_name": "CP16 Test Broadcaster",
        "attention": "Head of Engineering",
        "description": "Studio Upgrade Project",
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


def create_quote_with_revisions(client, user, base_payload):
    """Creates a quote and generates 3 revisions: INITIAL_CREATION, EDIT, SUBMIT."""
    headers = get_auth_headers(user.id)
    # Rev 1: INITIAL_CREATION
    r1 = client.post("/api/quotes", json=base_payload, headers=headers)
    assert r1.status_code == 201, r1.text
    q_data = r1.json()
    quote_id = q_data["id"]

    # Rev 2: EDIT
    edit_payload = {
        **base_payload,
        "client_name": "CP16 Updated Client Name",
        "expected_version": q_data["version"],
        "change_reason": "Updated client name for procurement"
    }
    r2 = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=headers)
    assert r2.status_code == 200, r2.text
    q_data = r2.json()

    # Rev 3: SUBMIT
    submit_payload = {
        "expected_version": q_data["version"],
        "comment": "Submitting for management approval"
    }
    r3 = client.post(f"/api/quotes/{quote_id}/submit", json=submit_payload, headers=headers)
    assert r3.status_code == 200, r3.text

    return quote_id


# =========================================================================
# 1. REVISION LIST ORDERING TESTS
# =========================================================================

def test_revision_list_default_ordering_asc(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Default ordering should be asc (Revision 1 -> 2 -> 3)
    resp = client.get(f"/api/quotes/{quote_id}/revisions", headers=headers)
    assert resp.status_code == 200, resp.text
    revisions = resp.json()
    assert len(revisions) == 3

    assert [r["revision_number"] for r in revisions] == [1, 2, 3]
    assert [r["action"] for r in revisions] == ["INITIAL_CREATION", "EDIT", "SUBMIT"]
    assert revisions[0]["change_reason"] is None
    assert revisions[1]["change_reason"] == "Updated client name for procurement"
    assert revisions[2]["change_reason"] == "Submitting for management approval"


def test_revision_list_explicit_ordering_desc(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    resp = client.get(f"/api/quotes/{quote_id}/revisions?order=desc", headers=headers)
    assert resp.status_code == 200, resp.text
    revisions = resp.json()
    assert len(revisions) == 3

    assert [r["revision_number"] for r in revisions] == [3, 2, 1]
    assert [r["action"] for r in revisions] == ["SUBMIT", "EDIT", "INITIAL_CREATION"]


def test_revision_list_invalid_order_param(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    resp = client.get(f"/api/quotes/{quote_id}/revisions?order=invalid", headers=headers)
    assert resp.status_code == 400
    assert "order" in resp.json()["detail"].lower()


# =========================================================================
# 2. PAGINATION LIMITS AND INVALID PAGINATION INPUTS
# =========================================================================

def test_revision_list_pagination_limit(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    resp = client.get(f"/api/quotes/{quote_id}/revisions?limit=1", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0]["revision_number"] == 1


def test_revision_list_pagination_skip_and_limit(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Skip 1, limit 1 -> should return Revision 2
    resp = client.get(f"/api/quotes/{quote_id}/revisions?skip=1&limit=1", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0]["revision_number"] == 2

    # Skip 2, limit 2 -> should return Revision 3
    resp2 = client.get(f"/api/quotes/{quote_id}/revisions?skip=2&limit=2", headers=headers)
    assert resp2.status_code == 200, resp2.text
    items2 = resp2.json()
    assert len(items2) == 1
    assert items2[0]["revision_number"] == 3

    # Skip beyond total revisions -> empty list
    resp3 = client.get(f"/api/quotes/{quote_id}/revisions?skip=10&limit=10", headers=headers)
    assert resp3.status_code == 200
    assert resp3.json() == []


def test_revision_list_pagination_clamping(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # limit > 100 is clamped to 100
    resp = client.get(f"/api/quotes/{quote_id}/revisions?limit=200", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_revision_list_invalid_pagination_inputs(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Negative skip
    resp_neg_skip = client.get(f"/api/quotes/{quote_id}/revisions?skip=-1", headers=headers)
    assert resp_neg_skip.status_code in (400, 422)

    # Zero limit
    resp_zero_limit = client.get(f"/api/quotes/{quote_id}/revisions?limit=0", headers=headers)
    assert resp_zero_limit.status_code in (400, 422)

    # Negative limit
    resp_neg_limit = client.get(f"/api/quotes/{quote_id}/revisions?limit=-5", headers=headers)
    assert resp_neg_limit.status_code in (400, 422)

    # Non-integer skip
    resp_str_skip = client.get(f"/api/quotes/{quote_id}/revisions?skip=abc", headers=headers)
    assert resp_str_skip.status_code == 422

    # Non-integer limit
    resp_str_limit = client.get(f"/api/quotes/{quote_id}/revisions?limit=xyz", headers=headers)
    assert resp_str_limit.status_code == 422


# =========================================================================
# 3. SPECIFIC REVISION RETRIEVAL TESTS
# =========================================================================

def test_get_specific_revision(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Fetch Revision 1
    resp = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=headers)
    assert resp.status_code == 200, resp.text
    rev1 = resp.json()

    assert rev1["quote_id"] == quote_id
    assert rev1["revision_number"] == 1
    assert rev1["action"] == "INITIAL_CREATION"
    assert rev1["user_id"] == sales_user.id
    assert rev1["user_email"] == sales_user.email
    assert rev1["user_role"] == sales_user.role_tier.value
    assert rev1["change_reason"] is None

    # Check snapshot data
    snap = rev1["snapshot_data"]
    assert snap["schema_version"] == "1.0"
    assert snap["quote"]["client_name"] == "CP16 Test Broadcaster"
    assert "financials" in snap
    assert "line_items" in snap
    assert len(snap["line_items"]) > 0

    # Fetch Revision 2
    resp2 = client.get(f"/api/quotes/{quote_id}/revisions/2", headers=headers)
    assert resp2.status_code == 200, resp2.text
    rev2 = resp2.json()
    assert rev2["revision_number"] == 2
    assert rev2["action"] == "EDIT"
    assert rev2["change_reason"] == "Updated client name for procurement"
    assert rev2["snapshot_data"]["quote"]["client_name"] == "CP16 Updated Client Name"

    # Fetch Revision 3
    resp3 = client.get(f"/api/quotes/{quote_id}/revisions/3", headers=headers)
    assert resp3.status_code == 200, resp3.text
    rev3 = resp3.json()
    assert rev3["revision_number"] == 3
    assert rev3["action"] == "SUBMIT"
    assert rev3["change_reason"] == "Submitting for management approval"


# =========================================================================
# 4. NONEXISTENT QUOTE AND NONEXISTENT REVISION TESTS
# =========================================================================

def test_nonexistent_quote_returns_404(client, sales_user):
    headers = get_auth_headers(sales_user.id)

    # List revisions for nonexistent quote
    resp_list = client.get("/api/quotes/999999/revisions", headers=headers)
    assert resp_list.status_code == 404
    assert resp_list.json()["detail"] == "Quote not found"

    # Specific revision for nonexistent quote
    resp_item = client.get("/api/quotes/999999/revisions/1", headers=headers)
    assert resp_item.status_code == 404
    assert resp_item.json()["detail"] == "Quote not found"


def test_nonexistent_revision_returns_404(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Revision 999 does not exist
    resp = client.get(f"/api/quotes/{quote_id}/revisions/999", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Revision not found"

    # Revision 0 does not exist
    resp_zero = client.get(f"/api/quotes/{quote_id}/revisions/0", headers=headers)
    assert resp_zero.status_code == 404
    assert resp_zero.json()["detail"] == "Revision not found"

    # Negative revision number
    resp_neg = client.get(f"/api/quotes/{quote_id}/revisions/-1", headers=headers)
    assert resp_neg.status_code == 404
    assert resp_neg.json()["detail"] == "Revision not found"


def test_soft_deleted_quote_returns_404(client, admin_user, base_payload, db):
    quote_id = create_quote_with_revisions(client, admin_user, base_payload)
    headers = get_auth_headers(admin_user.id)

    # Soft-delete the quote directly in DB
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    quote.deleted_at = datetime.datetime.utcnow()
    db.commit()

    # Revisions list should return 404
    resp_list = client.get(f"/api/quotes/{quote_id}/revisions", headers=headers)
    assert resp_list.status_code == 404
    assert resp_list.json()["detail"] == "Quote not found"

    # Specific revision should return 404
    resp_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=headers)
    assert resp_item.status_code == 404
    assert resp_item.json()["detail"] == "Quote not found"


# =========================================================================
# 5. UNAUTHORIZED AND INSUFFICIENT-PERMISSION CALLERS
# =========================================================================

def test_unauthenticated_requests_blocked(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)

    # No Authorization header
    resp_list = client.get(f"/api/quotes/{quote_id}/revisions")
    assert resp_list.status_code in (401, 403)

    resp_item = client.get(f"/api/quotes/{quote_id}/revisions/1")
    assert resp_item.status_code in (401, 403)


def test_disabled_user_blocked(client, sales_user, disabled_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    disabled_headers = get_auth_headers(disabled_user.id)

    resp_list = client.get(f"/api/quotes/{quote_id}/revisions", headers=disabled_headers)
    assert resp_list.status_code == 403
    assert resp_list.json()["detail"] == "Inactive user"

    resp_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=disabled_headers)
    assert resp_item.status_code == 403
    assert resp_item.json()["detail"] == "Inactive user"


def test_sales_user_cannot_access_other_users_quote_revisions(client, sales_user, other_sales_user, base_payload):
    # Quote created by sales_user
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)

    # other_sales_user attempts to access
    other_headers = get_auth_headers(other_sales_user.id)

    resp_list = client.get(f"/api/quotes/{quote_id}/revisions", headers=other_headers)
    assert resp_list.status_code == 403
    assert "forbidden" in resp_list.json()["detail"].lower()

    resp_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=other_headers)
    assert resp_item.status_code == 403
    assert "forbidden" in resp_item.json()["detail"].lower()


def test_non_sales_roles_can_access_any_quote_revisions(
    client, sales_user, catalog_entry_user, management_user, admin_user, base_payload
):
    # Quote created by sales_user
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)

    # Catalog Entry tier
    cat_headers = get_auth_headers(catalog_entry_user.id)
    resp_cat = client.get(f"/api/quotes/{quote_id}/revisions", headers=cat_headers)
    assert resp_cat.status_code == 200

    # Management tier
    mgmt_headers = get_auth_headers(management_user.id)
    resp_mgmt = client.get(f"/api/quotes/{quote_id}/revisions", headers=mgmt_headers)
    assert resp_mgmt.status_code == 200

    # Admin tier
    admin_headers = get_auth_headers(admin_user.id)
    resp_admin = client.get(f"/api/quotes/{quote_id}/revisions", headers=admin_headers)
    assert resp_admin.status_code == 200


# =========================================================================
# 6. COST VISIBILITY BEHAVIOR (COST MASKING)
# =========================================================================

def test_cost_masking_for_sales_and_catalog_entry(client, sales_user, catalog_entry_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)

    # 1. Sales User accessing their own quote revisions list
    sales_headers = get_auth_headers(sales_user.id)
    resp_sales_list = client.get(f"/api/quotes/{quote_id}/revisions", headers=sales_headers)
    assert resp_sales_list.status_code == 200
    for rev in resp_sales_list.json():
        snap = rev["snapshot_data"]
        # Subtotal cost must be masked
        assert snap["financials"]["subtotal_cost_usd"] is None
        # Subtotal sell must remain visible
        assert snap["financials"]["subtotal_sell_usd"] is not None
        assert snap["financials"]["total_sell_local"] is not None
        # Line item cost and margin must be masked
        for item in snap["line_items"]:
            assert item["unit_cost_price_snapshot"] is None
            assert item["line_cost_total"] is None
            assert item["margin_percent"] is None
            # Sell prices remain visible
            assert item["unit_sell_price_snapshot"] is not None
            assert item["line_sell_total"] is not None

    # 2. Sales User accessing specific revision
    resp_sales_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=sales_headers)
    assert resp_sales_item.status_code == 200
    snap = resp_sales_item.json()["snapshot_data"]
    assert snap["financials"]["subtotal_cost_usd"] is None
    for item in snap["line_items"]:
        assert item["unit_cost_price_snapshot"] is None
        assert item["line_cost_total"] is None
        assert item["margin_percent"] is None
        assert item["unit_sell_price_snapshot"] is not None

    # 3. Catalog Entry User accessing revision (Catalog Entry has NO cost visibility on saved quotes)
    cat_headers = get_auth_headers(catalog_entry_user.id)
    resp_cat_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=cat_headers)
    assert resp_cat_item.status_code == 200
    cat_snap = resp_cat_item.json()["snapshot_data"]
    assert cat_snap["financials"]["subtotal_cost_usd"] is None
    for item in cat_snap["line_items"]:
        assert item["unit_cost_price_snapshot"] is None
        assert item["line_cost_total"] is None
        assert item["margin_percent"] is None
        assert item["unit_sell_price_snapshot"] is not None


def test_cost_visibility_for_management_and_admin(client, sales_user, management_user, admin_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)

    # 1. Management User can see all cost and margin fields
    mgmt_headers = get_auth_headers(management_user.id)
    resp_mgmt = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=mgmt_headers)
    assert resp_mgmt.status_code == 200
    mgmt_snap = resp_mgmt.json()["snapshot_data"]
    assert mgmt_snap["financials"]["subtotal_cost_usd"] is not None
    assert Decimal(mgmt_snap["financials"]["subtotal_cost_usd"]) > 0
    for item in mgmt_snap["line_items"]:
        assert item["unit_cost_price_snapshot"] is not None
        assert item["line_cost_total"] is not None
        assert item["margin_percent"] is not None

    # 2. Admin User can see all cost and margin fields
    admin_headers = get_auth_headers(admin_user.id)
    resp_admin = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=admin_headers)
    assert resp_admin.status_code == 200
    admin_snap = resp_admin.json()["snapshot_data"]
    assert admin_snap["financials"]["subtotal_cost_usd"] is not None
    for item in admin_snap["line_items"]:
        assert item["unit_cost_price_snapshot"] is not None
        assert item["line_cost_total"] is not None
        assert item["margin_percent"] is not None


# =========================================================================
# 7. CROSS-QUOTE REVISION ACCESS ATTEMPTS
# =========================================================================

def test_cross_quote_revision_access_prevented(client, admin_user, base_payload):
    headers = get_auth_headers(admin_user.id)

    # Quote A: has 3 revisions (1, 2, 3)
    quote_a_id = create_quote_with_revisions(client, admin_user, base_payload)

    # Quote B: has only 1 revision (1)
    payload_b = {**base_payload, "client_name": "Quote B Client"}
    rb = client.post("/api/quotes", json=payload_b, headers=headers)
    assert rb.status_code == 201
    quote_b_id = rb.json()["id"]

    # Request Revision 2 under Quote B (Revision 2 exists on Quote A, but NOT on Quote B)
    resp = client.get(f"/api/quotes/{quote_b_id}/revisions/2", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Revision not found"


# =========================================================================
# 8. HISTORICAL SNAPSHOT VALUES REMAINING UNCHANGED
# =========================================================================

def test_historical_snapshot_values_unaffected_by_subsequent_quote_edits(
    client, admin_user, base_payload
):
    headers = get_auth_headers(admin_user.id)

    # Create Initial Quote (Rev 1)
    initial_payload = {**base_payload, "client_name": "Initial Client 123", "attention": "First Contact"}
    r1 = client.post("/api/quotes", json=initial_payload, headers=headers)
    assert r1.status_code == 201
    q1_data = r1.json()
    quote_id = q1_data["id"]

    # Edit Quote (Rev 2)
    edit_payload = {
        **base_payload,
        "client_name": "Brand New Client 456",
        "attention": "Second Contact",
        "expected_version": q1_data["version"],
        "change_reason": "Renamed for contract"
    }
    r2 = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=headers)
    assert r2.status_code == 200

    # Retrieve Revision 1 again
    resp_rev1 = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=headers)
    assert resp_rev1.status_code == 200
    snap1 = resp_rev1.json()["snapshot_data"]

    # Revision 1 MUST maintain original values
    assert snap1["quote"]["client_name"] == "Initial Client 123"
    assert snap1["quote"]["attention"] == "First Contact"
    assert snap1["quote"]["version"] == 1

    # Retrieve Revision 2
    resp_rev2 = client.get(f"/api/quotes/{quote_id}/revisions/2", headers=headers)
    assert resp_rev2.status_code == 200
    snap2 = resp_rev2.json()["snapshot_data"]

    # Revision 2 reflects updated values
    assert snap2["quote"]["client_name"] == "Brand New Client 456"
    assert snap2["quote"]["attention"] == "Second Contact"
    assert snap2["quote"]["version"] == 2


# =========================================================================
# 9. READ-ONLY BEHAVIOR: RETRIEVAL CALLS DO NOT MUTATE STATE
# =========================================================================

def test_retrieval_does_not_mutate_quote_or_revision_records(client, sales_user, base_payload, db):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # Record baseline state directly from database
    quote_before = db.query(Quote).filter(Quote.id == quote_id).first()
    revs_before = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).all()

    q_ver_before = quote_before.version
    q_updated_before = quote_before.updated_at
    rev_count_before = len(revs_before)
    rev_snapshots_before = [r.snapshot_data for r in revs_before]

    # Perform repeated read operations
    for _ in range(5):
        resp_list = client.get(f"/api/quotes/{quote_id}/revisions", headers=headers)
        assert resp_list.status_code == 200

        resp_item = client.get(f"/api/quotes/{quote_id}/revisions/1", headers=headers)
        assert resp_item.status_code == 200

    # Refresh quote from DB and verify immutability
    db.expire_all()
    quote_after = db.query(Quote).filter(Quote.id == quote_id).first()
    revs_after = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).all()

    assert quote_after.version == q_ver_before
    assert quote_after.updated_at == q_updated_before
    assert len(revs_after) == rev_count_before
    for i, r in enumerate(revs_after):
        assert r.snapshot_data == rev_snapshots_before[i]


# =========================================================================
# 10. COMPATIBILITY WITH EXISTING QUOTE ENDPOINTS
# =========================================================================

def test_compatibility_with_existing_quote_endpoints(client, sales_user, base_payload):
    quote_id = create_quote_with_revisions(client, sales_user, base_payload)
    headers = get_auth_headers(sales_user.id)

    # 1. GET /api/quotes/{quote_id}
    resp_quote = client.get(f"/api/quotes/{quote_id}", headers=headers)
    assert resp_quote.status_code == 200
    assert resp_quote.json()["id"] == quote_id

    # 2. GET /api/quotes (list)
    resp_list = client.get("/api/quotes", headers=headers)
    assert resp_list.status_code == 200
    assert any(q["id"] == quote_id for q in resp_list.json())

    # 3. GET /api/quotes/{quote_id}/history (approval logs)
    resp_history = client.get(f"/api/quotes/{quote_id}/history", headers=headers)
    assert resp_history.status_code == 200
    assert len(resp_history.json()) >= 1  # Has SUBMIT log from create_quote_with_revisions

    # 4. GET /api/quotes/{quote_id}/revisions
    resp_revs = client.get(f"/api/quotes/{quote_id}/revisions", headers=headers)
    assert resp_revs.status_code == 200
    assert len(resp_revs.json()) == 3
