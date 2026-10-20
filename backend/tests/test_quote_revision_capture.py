import pytest
from decimal import Decimal, ROUND_HALF_UP
import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from backend.app.models.user import User, RoleTier
from backend.app.models.solution import Solution
from backend.app.models.region import Region
from backend.app.models.quote import Quote, QuoteStatus, QuoteRevision, QuoteApprovalLog
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
    user = User(
        email=f"admin_cp15_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.ADMIN,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def sales_user(db):
    user = User(
        email=f"sales_cp15_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def other_sales_user(db):
    user = User(
        email=f"other_sales_cp15_{datetime.datetime.now(datetime.timezone.utc).timestamp()}@test.com",
        role_tier=RoleTier.SALES,
        enabled=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def base_payload(test_context):
    return {
        "client_name": "CP15 Test Broadcaster",
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


# 1. Initial quote creation produces Revision 1 (INITIAL_CREATION)
def test_initial_quote_creation_produces_revision(client, sales_user, base_payload, db):
    headers = get_auth_headers(sales_user.id)
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    quote_id = data["id"]

    # Query quote_revisions for this quote
    revisions = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).all()
    assert len(revisions) == 1
    rev1 = revisions[0]
    assert rev1.revision_number == 1
    assert rev1.action == "INITIAL_CREATION"
    assert rev1.user_id == sales_user.id
    assert rev1.user_email == sales_user.email
    assert rev1.quote_version == 1
    assert rev1.change_reason is None

    # Inspect snapshot content
    snap = rev1.snapshot_data
    assert snap["schema_version"] == "1.0"
    assert snap["quote"]["id"] == quote_id
    assert snap["quote"]["quote_ref_no"] == data["quote_ref_no"]
    assert snap["quote"]["status"] == "draft"
    assert snap["quote"]["client_name"] == "CP15 Test Broadcaster"
    assert len(snap["line_items"]) > 0
    assert snap["financials"]["currency_code"] is not None
    assert snap["financials"]["total_sell_local"] is not None


# 2. Quote edit produces Revision 2 (EDIT) with change_reason
def test_quote_edit_produces_revision_with_change_reason(client, sales_user, base_payload, db):
    headers = get_auth_headers(sales_user.id)
    # Create quote
    resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert resp.status_code == 201
    quote_id = resp.json()["id"]

    # Edit quote
    update_payload = dict(base_payload)
    update_payload["expected_version"] = 1
    update_payload["client_name"] = "CP15 Edited Broadcaster"
    update_payload["change_reason"] = "Customer changed legal entity name"
    update_payload["requirement_data"] = {
        "number_of_studios": 1,
        "studios": [
            {
                "studio_index": 0,
                "studio_type": "Real Set",
                "number_of_engines": 2
            }
        ]
    }

    put_resp = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["version"] == 2

    # Verify revisions
    revisions = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id)
        .order_by(QuoteRevision.revision_number.asc())
        .all()
    )
    assert len(revisions) == 2

    # Revision 1 (initial state) remains unchanged
    assert revisions[0].revision_number == 1
    assert revisions[0].action == "INITIAL_CREATION"
    assert revisions[0].snapshot_data["quote"]["client_name"] == "CP15 Test Broadcaster"

    # Revision 2 (post-edit state)
    assert revisions[1].revision_number == 2
    assert revisions[1].action == "EDIT"
    assert revisions[1].user_id == sales_user.id
    assert revisions[1].change_reason == "Customer changed legal entity name"
    assert revisions[1].quote_version == 2
    assert revisions[1].snapshot_data["quote"]["client_name"] == "CP15 Edited Broadcaster"


# 3. Recalculation records revision (RECALCULATE)
def test_quote_recalculate_produces_revision(client, sales_user, base_payload, db):
    headers = get_auth_headers(sales_user.id)
    create_resp = client.post("/api/quotes", json=base_payload, headers=headers)
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["id"]

    recalc_payload = {
        "expected_version": 1,
        "change_reason": "Recalculating with 3 studios",
        "requirement_data": {
            "number_of_studios": 2,
            "studios": [
                {"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1},
                {"studio_index": 1, "studio_type": "Real Set", "number_of_engines": 1}
            ]
        }
    }

    recalc_resp = client.post(f"/api/quotes/{quote_id}/recalculate", json=recalc_payload, headers=headers)
    assert recalc_resp.status_code == 200, recalc_resp.text
    assert recalc_resp.json()["version"] == 2

    revisions = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id)
        .order_by(QuoteRevision.revision_number.asc())
        .all()
    )
    assert len(revisions) == 2
    assert revisions[1].revision_number == 2
    assert revisions[1].action == "RECALCULATE"
    assert revisions[1].user_id == sales_user.id
    assert revisions[1].change_reason == "Recalculating with 3 studios"
    assert revisions[1].quote_version == 2


# 4. Approval workflow lifecycle records revisions (SUBMIT, REQUEST_CHANGES, APPROVE)
def test_approval_workflow_lifecycle_records_revisions(client, sales_user, admin_user, base_payload, db):
    sales_headers = get_auth_headers(sales_user.id)
    admin_headers = get_auth_headers(admin_user.id)

    # 1. Create quote (Rev 1)
    create_resp = client.post("/api/quotes", json=base_payload, headers=sales_headers)
    quote_id = create_resp.json()["id"]

    # 2. Submit quote (Rev 2)
    submit_resp = client.post(
        f"/api/quotes/{quote_id}/submit",
        json={"expected_version": 1, "comment": "Ready for financial approval"},
        headers=sales_headers
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "pending_approval"

    # 3. Request changes (Rev 3)
    changes_resp = client.post(
        f"/api/quotes/{quote_id}/request-changes",
        json={"expected_version": 1, "comment": "Discount required on support"},
        headers=admin_headers
    )
    assert changes_resp.status_code == 200
    assert changes_resp.json()["status"] == "changes_requested"

    # 4. Re-submit quote (Rev 4)
    submit_resp2 = client.post(
        f"/api/quotes/{quote_id}/submit",
        json={"expected_version": 1, "comment": "Discount applied as requested"},
        headers=sales_headers
    )
    assert submit_resp2.status_code == 200
    assert submit_resp2.json()["status"] == "pending_approval"

    # 5. Approve quote (Rev 5)
    approve_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"expected_version": 1, "comment": "Approved for commercial distribution"},
        headers=admin_headers
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Verify all revisions
    revisions = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id)
        .order_by(QuoteRevision.revision_number.asc())
        .all()
    )
    assert len(revisions) == 5
    expected_actions = ["INITIAL_CREATION", "SUBMIT", "REQUEST_CHANGES", "SUBMIT", "APPROVE"]
    expected_actors = [sales_user.id, sales_user.id, admin_user.id, sales_user.id, admin_user.id]

    for idx, rev in enumerate(revisions):
        assert rev.revision_number == idx + 1
        assert rev.action == expected_actions[idx]
        assert rev.user_id == expected_actors[idx]

    # Verify QuoteApprovalLog also remains intact
    approval_logs = (
        db.query(QuoteApprovalLog)
        .filter(QuoteApprovalLog.quote_id == quote_id)
        .order_by(QuoteApprovalLog.created_at.asc())
        .all()
    )
    assert len(approval_logs) == 4
    assert [log.action for log in approval_logs] == ["SUBMIT", "REQUEST_CHANGES", "SUBMIT", "APPROVE"]


# 5. Override approve records revision (OVERRIDE_APPROVE)
def test_override_approve_records_revision(client, sales_user, admin_user, base_payload, db):
    sales_headers = get_auth_headers(sales_user.id)
    admin_headers = get_auth_headers(admin_user.id)

    # Create quote
    create_resp = client.post("/api/quotes", json=base_payload, headers=sales_headers)
    quote_id = create_resp.json()["id"]

    # Override approve directly from draft
    override_resp = client.post(
        f"/api/quotes/{quote_id}/override-approve",
        json={"expected_version": 1, "comment": "Executive urgent sign-off"},
        headers=admin_headers
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["status"] == "approved"

    revisions = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id)
        .order_by(QuoteRevision.revision_number.asc())
        .all()
    )
    assert len(revisions) == 2
    assert revisions[1].revision_number == 2
    assert revisions[1].action == "OVERRIDE_APPROVE"
    assert revisions[1].user_id == admin_user.id
    assert revisions[1].change_reason == "Executive urgent sign-off"
    assert revisions[1].snapshot_data["quote"]["status"] == "approved"


# 6. FX refresh records revision and preserves prior financial snapshot
def test_fx_refresh_records_revision_and_preserves_prior_financial_snapshot(client, admin_user, test_context, db):
    admin_headers = get_auth_headers(admin_user.id)

    # Set up non-USD region with initial FX rate
    region = db.query(Region).filter(Region.id == test_context["region_id"]).first()
    region.currency_code = "INR"
    region.fx_rate_to_usd = Decimal("80.000000")
    region.fx_rate_as_of = "2026-09-01 00:00:00 UTC"
    region.tax_enabled = True
    region.tax_rate_percent = Decimal("18.00")
    db.commit()

    # Create quote with initial FX rate (80.00)
    quote_payload = {
        "client_name": "Indian Broadcaster Ltd",
        "solution_id": test_context["solution_id"],
        "region_id": region.id,
        "requirement_data": {
            "number_of_studios": 1,
            "studios": [{"studio_index": 0, "studio_type": "Real Set", "number_of_engines": 1}]
        }
    }
    create_resp = client.post("/api/quotes", json=quote_payload, headers=admin_headers)
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["id"]
    initial_fx = create_resp.json()["fx_rate_to_usd"]
    initial_total_local = Decimal(create_resp.json()["total_sell_local"])
    assert Decimal(initial_fx) == Decimal("80.000000")

    # Update regional FX rate to 85.00
    region.fx_rate_to_usd = Decimal("85.000000")
    region.fx_rate_as_of = "2026-10-01 00:00:00 UTC"
    db.commit()

    # Refresh quote FX rate
    refresh_resp = client.post(
        f"/api/quotes/{quote_id}/refresh-fx",
        json={"expected_version": 1, "comment": "Q4 rate adjustment"},
        headers=admin_headers
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    refreshed_data = refresh_resp.json()
    assert Decimal(refreshed_data["fx_rate_to_usd"]) == Decimal("85.000000")
    assert refreshed_data["version"] == 2

    # Verify revisions
    revisions = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id)
        .order_by(QuoteRevision.revision_number.asc())
        .all()
    )
    assert len(revisions) == 2

    # Revision 1 preserves initial rate and totals
    rev1 = revisions[0]
    assert rev1.revision_number == 1
    assert rev1.action == "INITIAL_CREATION"
    assert Decimal(rev1.snapshot_data["financials"]["fx_rate_to_usd"]) == Decimal("80.000000")
    assert Decimal(rev1.snapshot_data["financials"]["total_sell_local"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == initial_total_local

    # Revision 2 has new rate and new totals
    rev2 = revisions[1]
    assert rev2.revision_number == 2
    assert rev2.action == "FX_REFRESH"
    assert rev2.user_id == admin_user.id
    assert rev2.change_reason == "Q4 rate adjustment"
    assert Decimal(rev2.snapshot_data["financials"]["fx_rate_to_usd"]) == Decimal("85.000000")
    assert Decimal(rev2.snapshot_data["financials"]["total_sell_local"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal(refreshed_data["total_sell_local"])


# 7. Change reason whitespace validation and length enforcement
def test_change_reason_whitespace_and_length_validation(client, sales_user, base_payload, db):
    headers = get_auth_headers(sales_user.id)
    create_resp = client.post("/api/quotes", json=base_payload, headers=headers)
    quote_id = create_resp.json()["id"]

    # Test whitespace stripping
    update_payload = dict(base_payload)
    update_payload["expected_version"] = 1
    update_payload["change_reason"] = "   Padded reason with spaces   "
    put_resp = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    rev2 = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id, QuoteRevision.revision_number == 2)
        .first()
    )
    assert rev2.change_reason == "Padded reason with spaces"

    # Test whitespace-only string converts to None
    update_payload["expected_version"] = 2
    update_payload["change_reason"] = "     "
    put_resp2 = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp2.status_code == 200
    rev3 = (
        db.query(QuoteRevision)
        .filter(QuoteRevision.quote_id == quote_id, QuoteRevision.revision_number == 3)
        .first()
    )
    assert rev3.change_reason is None

    # Test max length enforcement (> 1000 chars rejected with 422)
    update_payload["expected_version"] = 3
    update_payload["change_reason"] = "A" * 1001
    put_resp3 = client.put(f"/api/quotes/{quote_id}", json=update_payload, headers=headers)
    assert put_resp3.status_code == 422


# 8. Failed quote mutation leaves no partial revision (Atomicity)
def test_failed_quote_mutation_leaves_no_partial_revision(client, sales_user, base_payload, db):
    headers = get_auth_headers(sales_user.id)
    create_resp = client.post("/api/quotes", json=base_payload, headers=headers)
    quote_id = create_resp.json()["id"]
    assert db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).count() == 1

    # Attempt edit with mismatched expected_version (fails with 409)
    bad_update = dict(base_payload)
    bad_update["expected_version"] = 999
    bad_update["change_reason"] = "Should never be recorded"
    resp = client.put(f"/api/quotes/{quote_id}", json=bad_update, headers=headers)
    assert resp.status_code == 409

    # Confirm revision count is STILL exactly 1
    assert db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).count() == 1

    # Attempt invalid approval transition (draft cannot be directly approved without submit)
    bad_approve = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"expected_version": 1, "comment": "Invalid approval"},
        headers=headers  # sales user also lacks permission
    )
    assert bad_approve.status_code == 403
    assert db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote_id).count() == 1


# 9. Revision history remains immutable
def test_revision_immutability_enforced(db, admin_user, base_payload):
    from backend.app.services.revision_service import create_quote_revision
    from backend.app.services.engines.pricing_engine import PricingEngine
    from backend.app.services.engines.requirement_engine import parse_and_evaluate_requirements
    from backend.app.schemas.requirement import RequirementPayload

    solution = db.query(Solution).first()
    region = db.query(Region).first()
    bom = parse_and_evaluate_requirements(solution, base_payload["requirement_data"])
    req_payload = RequirementPayload(**base_payload["requirement_data"])

    quote = Quote(
        solution_id=solution.id,
        region_id=region.id,
        client_name="Immutability Test",
        quote_ref_no="BBS-IMMUT-001",
        version=1,
        status=QuoteStatus.DRAFT,
        created_by_user_id=admin_user.id,
        last_edited_by_user_id=admin_user.id,
    )
    quote.region = region
    quote.solution = solution
    db.add(quote)
    db.flush()
    PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)

    rev = create_quote_revision(db=db, quote=quote, action="INITIAL_CREATION", user_id=admin_user.id)
    db.add(rev)
    db.commit()

    # 1. Attempt ORM modification -> raises RuntimeError
    with pytest.raises(RuntimeError, match="QuoteRevision instances are immutable and cannot be updated"):
        rev.action = "MUTATED"
        db.commit()
    db.rollback()

    # 2. Attempt ORM deletion -> raises RuntimeError
    with pytest.raises(RuntimeError, match="QuoteRevision instances are immutable and cannot be deleted"):
        db.delete(rev)
        db.commit()
    db.rollback()


# 10. Approved and pending-approval protections still work
def test_approved_and_pending_approval_protections_still_enforced(client, sales_user, admin_user, base_payload, db):
    sales_headers = get_auth_headers(sales_user.id)
    admin_headers = get_auth_headers(admin_user.id)

    # Create quote
    create_resp = client.post("/api/quotes", json=base_payload, headers=sales_headers)
    quote_id = create_resp.json()["id"]

    # Submit to pending approval
    submit_resp = client.post(
        f"/api/quotes/{quote_id}/submit",
        json={"expected_version": 1, "comment": "Submitted for approval"},
        headers=sales_headers
    )
    assert submit_resp.status_code == 200

    # Try to edit pending-approval quote -> 409 Conflict
    edit_payload = dict(base_payload)
    edit_payload["expected_version"] = 1
    edit_resp = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=sales_headers)
    assert edit_resp.status_code == 409
    assert "Only DRAFT or CHANGES_REQUESTED" in edit_resp.json()["detail"]

    # Try to recalculate pending-approval quote -> 409 Conflict
    recalc_resp = client.post(
        f"/api/quotes/{quote_id}/recalculate",
        json={"expected_version": 1, "requirement_data": base_payload["requirement_data"]},
        headers=sales_headers
    )
    assert recalc_resp.status_code == 409

    # Approve quote
    approve_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"expected_version": 1, "comment": "Approved"},
        headers=admin_headers
    )
    assert approve_resp.status_code == 200

    # Try to edit approved quote -> 409 Conflict
    edit_resp2 = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=sales_headers)
    assert edit_resp2.status_code == 409

    # Try to refresh FX on approved quote -> 409 Conflict
    refresh_resp = client.post(
        f"/api/quotes/{quote_id}/refresh-fx",
        json={"expected_version": 1, "comment": "Attempted FX refresh on approved"},
        headers=admin_headers
    )
    assert refresh_resp.status_code == 409
    assert "Historical quotes are immutable" in refresh_resp.json()["detail"]


# 11. Permissions and cost visibility remain enforced
def test_permissions_and_cost_visibility_enforced(client, sales_user, admin_user, other_sales_user, base_payload):
    sales_headers = get_auth_headers(sales_user.id)
    admin_headers = get_auth_headers(admin_user.id)
    other_headers = get_auth_headers(other_sales_user.id)

    # Sales user creates quote -> financials masked
    resp = client.post("/api/quotes", json=base_payload, headers=sales_headers)
    assert resp.status_code == 201
    quote_data = resp.json()
    assert quote_data["subtotal_cost_usd"] is None
    for item in quote_data["line_items"]:
        assert item["unit_cost_price_snapshot"] is None
        assert item["line_cost_total"] is None
        assert item["margin_percent"] is None

    quote_id = quote_data["id"]

    # Admin user reads quote -> financials visible
    admin_resp = client.get(f"/api/quotes/{quote_id}", headers=admin_headers)
    assert admin_resp.status_code == 200
    admin_data = admin_resp.json()
    assert admin_data["subtotal_cost_usd"] is not None

    # Other sales user cannot edit or view this quote
    forbidden_resp = client.get(f"/api/quotes/{quote_id}", headers=other_headers)
    assert forbidden_resp.status_code == 403

    edit_payload = dict(base_payload)
    edit_payload["expected_version"] = 1
    forbidden_edit = client.put(f"/api/quotes/{quote_id}", json=edit_payload, headers=other_headers)
    assert forbidden_edit.status_code == 403

    # Sales user cannot approve quote
    unauth_approve = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"expected_version": 1, "comment": "Unauthorized approve"},
        headers=sales_headers
    )
    assert unauth_approve.status_code == 403


# 12. Concurrency safety: Row locking serializes concurrent transactions
def test_concurrent_mutations_lock_parent_quote_and_serialize(engine):
    with Session(bind=engine) as setup_db:
        solution = setup_db.query(Solution).first()
        region = setup_db.query(Region).first()
        user = setup_db.query(User).filter(User.role_tier == RoleTier.ADMIN).first()
        quote = Quote(
            solution_id=solution.id,
            region_id=region.id,
            client_name="Concurrency Lock Test",
            quote_ref_no="BBS-CONCURR-001",
            version=1,
            status=QuoteStatus.DRAFT,
            created_by_user_id=user.id,
            last_edited_by_user_id=user.id,
            currency_code="USD",
            fx_rate_to_usd=Decimal("1.0"),
            tax_enabled=False,
            subtotal_sell_usd=Decimal("1000.0"),
            subtotal_cost_usd=Decimal("800.0"),
            tax_amount=Decimal("0.0"),
            total_sell_local=Decimal("1000.0"),
        )
        setup_db.add(quote)
        setup_db.commit()
        quote_id = quote.id

    try:
        conn1 = engine.connect()
        trans1 = conn1.begin()
        db_session1 = Session(bind=conn1)

        # Session 1 locks the quote
        locked_quote = db_session1.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        assert locked_quote is not None

        # Session 2 attempts to lock with NOWAIT -> must fail with lock conflict
        with engine.connect() as conn2:
            with pytest.raises(OperationalError, match="could not obtain lock on row in relation|lock"):
                conn2.execute(text(f"SELECT id FROM quotes WHERE id = {quote_id} FOR UPDATE NOWAIT"))

        trans1.rollback()
        conn1.close()
    finally:
        with engine.connect() as cleanup:
            cleanup.execute(text(f"DELETE FROM quotes WHERE id = {quote_id}"))
            cleanup.commit()
