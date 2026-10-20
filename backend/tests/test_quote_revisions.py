import pytest
import datetime
from decimal import Decimal
import json
import importlib
from sqlalchemy.exc import IntegrityError, DatabaseError, OperationalError
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.app.models.solution import Solution
from backend.app.models.region import Region
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.catalog import CatalogItem, CatalogItemKind
from backend.app.models.quote import Quote, QuoteLineItem, QuoteStatus, QuoteRevision
from backend.app.services.revision_service import (
    serialize_quote_snapshot,
    create_quote_revision,
    serialize_decimal,
    serialize_datetime,
    SCHEMA_VERSION
)


def _create_base_entities(db):
    solution = db.query(Solution).first()
    if not solution:
        solution = Solution(name="Test Solution")
        db.add(solution)
        db.flush()

    region = db.query(Region).filter_by(country_name="Singapore").first()
    if not region:
        region = db.query(Region).first()
    if not region:
        region = Region(
            country_name="Test Country Unique CP14",
            currency_code="SGD",
            fx_rate_to_usd=Decimal("1.345678"),
            fx_rate_as_of="2026-10-15",
            tax_enabled=True,
            tax_rate_percent=Decimal("9.00"),
            legal_entity_name="Benchmark Singapore",
            legal_entity_registration_number="REG-12345",
            legal_entity_address="123 Media Park",
            legal_entity_contact="+65 1234 5678"
        )
        db.add(region)
        db.flush()

    # Ensure region has all test fields populated for assertion stability
    if not region.fx_rate_to_usd:
        region.fx_rate_to_usd = Decimal("1.345678")
    if not region.fx_rate_as_of:
        region.fx_rate_as_of = "2026-10-15"
    if not region.tax_rate_percent:
        region.tax_rate_percent = Decimal("9.00")
    if not region.legal_entity_name:
        region.legal_entity_name = "Benchmark Singapore"
    if not region.legal_entity_registration_number:
        region.legal_entity_registration_number = "REG-12345"
    if not region.legal_entity_address:
        region.legal_entity_address = "123 Media Park"
    if not region.legal_entity_contact:
        region.legal_entity_contact = "+65 1234 5678"
    db.flush()

    user_email = f"author_cp14_{datetime.datetime.utcnow().timestamp()}@example.com"
    user = User(email=user_email, role_tier=RoleTier.SALES, account_type=AccountType.MANUAL)
    db.add(user)
    db.flush()
    return solution, region, user


def _create_sample_quote(db, solution, region, user, quote_ref_no="REF-CP14-001"):
    quote = Quote(
        solution_id=solution.id,
        region_id=region.id,
        client_name="Mediacorp Pte Ltd",
        quote_ref_no=quote_ref_no,
        date=datetime.datetime(2026, 10, 20, 10, 0, 0),
        attention="Engineering Dept",
        description="Playout Automation Rig",
        version=1,
        requirement_data={"channel_count": 2, "redundancy": True},
        created_by_user_id=user.id,
        last_edited_by_user_id=user.id,
        status=QuoteStatus.DRAFT,
        is_urgent=False,
        currency_code="SGD",
        fx_rate_to_usd=Decimal("1.345678"),
        fx_rate_as_of="2026-10-15",
        tax_enabled=True,
        tax_rate_percent=Decimal("9.00"),
        subtotal_cost_usd=Decimal("10000.00"),
        subtotal_sell_usd=Decimal("15000.00"),
        tax_amount=Decimal("1003.54"),
        total_sell_local=Decimal("12151.78"),
        legal_entity_name="Benchmark Singapore",
        legal_entity_registration_number="REG-12345",
        legal_entity_address="123 Media Park",
        legal_entity_contact="+65 1234 5678"
    )
    db.add(quote)
    db.flush()
    return quote


# 1. A quote with multiple line items can be represented in a snapshot
def test_quote_snapshot_multiple_line_items(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    item1 = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        part_number="PN-001",
        description="Main Playout Server",
        brand="wTVision",
        section="Playout",
        sort_order=0,
        quantity=2,
        unit_sell_price_snapshot=Decimal("5000.00"),
        unit_cost_price_snapshot=Decimal("3500.00"),
        line_sell_total=Decimal("10000.00"),
        line_cost_total=Decimal("7000.00"),
        margin_percent=Decimal("30.00")
    )
    item2 = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        part_number="PN-002",
        description="Backup Playout Server",
        brand="wTVision",
        section="Playout",
        sort_order=1,
        quantity=1,
        unit_sell_price_snapshot=Decimal("5000.00"),
        unit_cost_price_snapshot=Decimal("3000.00"),
        line_sell_total=Decimal("5000.00"),
        line_cost_total=Decimal("3000.00"),
        margin_percent=Decimal("40.00")
    )
    db.add_all([item1, item2])
    db.flush()

    snapshot = serialize_quote_snapshot(quote)

    assert snapshot["schema_version"] == SCHEMA_VERSION
    assert len(snapshot["line_items"]) == 2
    assert snapshot["line_items"][0]["part_number"] == "PN-001"
    assert snapshot["line_items"][0]["quantity"] == 2
    assert snapshot["line_items"][1]["part_number"] == "PN-002"
    assert snapshot["line_items"][1]["quantity"] == 1


# 2. All required header, BoQ, pricing, FX, and tax fields are preserved
def test_quote_snapshot_preserves_all_required_fields(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    item = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        part_number="PN-TEST",
        description="Test Item",
        brand="BrandX",
        section="Core",
        sort_order=0,
        quantity=3,
        unit_sell_price_snapshot=Decimal("100.00"),
        unit_cost_price_snapshot=Decimal("75.00"),
        line_sell_total=Decimal("300.00"),
        line_cost_total=Decimal("225.00"),
        margin_percent=Decimal("25.00")
    )
    db.add(item)
    db.flush()

    snapshot = serialize_quote_snapshot(quote)

    # Header fields
    q = snapshot["quote"]
    assert q["id"] == quote.id
    assert q["quote_ref_no"] == "REF-CP14-001"
    assert q["version"] == 1
    assert q["status"] == "draft"
    assert q["client_name"] == "Mediacorp Pte Ltd"
    assert q["attention"] == "Engineering Dept"
    assert q["description"] == "Playout Automation Rig"
    assert q["date"] == "2026-10-20T10:00:00"
    assert q["solution_id"] == solution.id
    assert q["solution_name"] == solution.name
    assert q["region_id"] == region.id
    assert q["region_name"] == region.country_name
    assert q["created_by_user_id"] == user.id
    assert q["last_edited_by_user_id"] == user.id
    assert q["is_urgent"] is False
    assert q["requirement_data"] == {"channel_count": 2, "redundancy": True}

    # Financial fields
    fin = snapshot["financials"]
    assert fin["currency_code"] == "SGD"
    assert fin["fx_rate_to_usd"] == "1.345678"
    assert fin["fx_rate_as_of"] == "2026-10-15"
    assert fin["tax_enabled"] is True
    assert fin["tax_rate_percent"] == "9.00"
    assert fin["subtotal_cost_usd"] == "10000.00"
    assert fin["subtotal_sell_usd"] == "15000.00"
    assert fin["tax_amount"] == "1003.54"
    assert fin["total_sell_local"] == "12151.78"

    # Legal entity fields
    legal = snapshot["legal_entity"]
    assert legal["legal_entity_name"] == "Benchmark Singapore"
    assert legal["legal_entity_registration_number"] == "REG-12345"
    assert legal["legal_entity_address"] == "123 Media Park"
    assert legal["legal_entity_contact"] == "+65 1234 5678"

    # Line item fields
    li = snapshot["line_items"][0]
    assert li["id"] == item.id
    assert li["part_number"] == "PN-TEST"
    assert li["description"] == "Test Item"
    assert li["brand"] == "BrandX"
    assert li["section"] == "Core"
    assert li["sort_order"] == 0
    assert li["quantity"] == 3
    assert li["unit_sell_price_snapshot"] == "100.00"
    assert li["unit_cost_price_snapshot"] == "75.00"
    assert li["line_sell_total"] == "300.00"
    assert li["line_cost_total"] == "225.00"
    assert li["margin_percent"] == "25.00"


# 3. Decimal values survive serialization without precision loss
def test_decimal_values_survive_serialization_without_precision_loss(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    # Use high-precision decimals
    quote.fx_rate_to_usd = Decimal("1.234567")
    quote.tax_rate_percent = Decimal("18.75")
    quote.subtotal_cost_usd = Decimal("999999.99")
    quote.total_sell_local = Decimal("1234567.89")

    item = QuoteLineItem(
        quote_id=quote.id,
        description="High precision item",
        sort_order=0,
        quantity=7,
        unit_sell_price_snapshot=Decimal("12345.67"),
        unit_cost_price_snapshot=Decimal("8910.11"),
        line_sell_total=Decimal("86419.69"),
        line_cost_total=Decimal("62370.77"),
        margin_percent=Decimal("27.82")
    )
    db.add(item)
    db.flush()

    snapshot = serialize_quote_snapshot(quote)

    # Verify values survive as exact strings without floating-point artifacts
    assert snapshot["financials"]["fx_rate_to_usd"] == "1.234567"
    assert snapshot["financials"]["tax_rate_percent"] == "18.75"
    assert snapshot["financials"]["subtotal_cost_usd"] == "999999.99"
    assert snapshot["financials"]["total_sell_local"] == "1234567.89"

    li = snapshot["line_items"][0]
    assert li["unit_sell_price_snapshot"] == "12345.67"
    assert li["unit_cost_price_snapshot"] == "8910.11"
    assert li["line_sell_total"] == "86419.69"
    assert li["line_cost_total"] == "62370.77"
    assert li["margin_percent"] == "27.82"

    # Verify they parse back to identical Decimal objects
    assert Decimal(snapshot["financials"]["fx_rate_to_usd"]) == Decimal("1.234567")
    assert Decimal(li["line_sell_total"]) == Decimal("86419.69")


# 4. Null values are handled correctly
def test_null_values_handled_correctly(db):
    solution, region, user = _create_base_entities(db)
    quote = Quote(
        solution_id=solution.id,
        region_id=region.id,
        client_name="Minimal Client",
        quote_ref_no="REF-NULL-TEST",
        attention=None,
        description=None,
        created_by_user_id=user.id,
        last_edited_by_user_id=user.id,
        status=QuoteStatus.DRAFT,
        tax_enabled=False,
        tax_rate_percent=None,
        fx_rate_as_of=None,
        legal_entity_name=None,
        legal_entity_registration_number=None,
        legal_entity_address=None,
        legal_entity_contact=None,
        subtotal_sell_usd=Decimal("0.00"),
        subtotal_cost_usd=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_sell_local=Decimal("0.00")
    )
    db.add(quote)
    db.flush()

    item = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        part_number=None,
        description="Custom Service",
        brand=None,
        section=None,
        sort_order=0,
        quantity=1,
        unit_sell_price_snapshot=Decimal("500.00"),
        unit_cost_price_snapshot=Decimal("0.00"),
        line_sell_total=Decimal("500.00"),
        line_cost_total=Decimal("0.00"),
        margin_percent=Decimal("100.00")
    )
    db.add(item)
    db.flush()

    snapshot = serialize_quote_snapshot(quote)

    q = snapshot["quote"]
    assert q["attention"] is None
    assert q["description"] is None
    assert q["deleted_at"] is None

    fin = snapshot["financials"]
    assert fin["fx_rate_as_of"] is None
    assert fin["tax_rate_percent"] is None

    legal = snapshot["legal_entity"]
    assert legal["legal_entity_name"] is None
    assert legal["legal_entity_registration_number"] is None

    li = snapshot["line_items"][0]
    assert li["catalog_item_id"] is None
    assert li["part_number"] is None
    assert li["brand"] is None
    assert li["section"] is None


# 5. Dates and timestamps are serializable
def test_dates_and_timestamps_are_serializable(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    snapshot = serialize_quote_snapshot(quote)

    # Must be valid ISO strings
    date_str = snapshot["quote"]["date"]
    created_at_str = snapshot["quote"]["created_at"]
    captured_at_str = snapshot["captured_at"]

    assert datetime.datetime.fromisoformat(date_str) == datetime.datetime(2026, 10, 20, 10, 0, 0)
    assert datetime.datetime.fromisoformat(created_at_str) is not None
    assert datetime.datetime.fromisoformat(captured_at_str) is not None

    # Entire snapshot must serialize cleanly through standard json.dumps
    json_bytes = json.dumps(snapshot).encode("utf-8")
    assert len(json_bytes) > 0


# 6. Line-item ordering is deterministic
def test_line_item_ordering_deterministic(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    # Insert items with non-sequential sort orders
    item_c = QuoteLineItem(quote_id=quote.id, description="Item C", sort_order=2, unit_sell_price_snapshot=Decimal("10"), unit_cost_price_snapshot=Decimal("5"))
    item_a = QuoteLineItem(quote_id=quote.id, description="Item A", sort_order=0, unit_sell_price_snapshot=Decimal("10"), unit_cost_price_snapshot=Decimal("5"))
    item_b = QuoteLineItem(quote_id=quote.id, description="Item B", sort_order=1, unit_sell_price_snapshot=Decimal("10"), unit_cost_price_snapshot=Decimal("5"))
    db.add_all([item_c, item_a, item_b])
    db.flush()

    snapshot = serialize_quote_snapshot(quote)

    descriptions = [item["description"] for item in snapshot["line_items"]]
    assert descriptions == ["Item A", "Item B", "Item C"]


# 7. Snapshot JSON can be stored and retrieved correctly
def test_snapshot_db_storage_and_retrieval(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    revision = create_quote_revision(
        db=db,
        quote=quote,
        action="INITIAL_CREATION",
        user_id=user.id,
        change_reason="Baseline revision for customer proposal"
    )
    db.add(revision)
    db.flush()

    retrieved = db.query(QuoteRevision).filter(QuoteRevision.id == revision.id).first()
    assert retrieved is not None
    assert retrieved.quote_id == quote.id
    assert retrieved.revision_number == 1
    assert retrieved.quote_version == quote.version
    assert retrieved.action == "INITIAL_CREATION"
    assert retrieved.user_id == user.id
    assert retrieved.change_reason == "Baseline revision for customer proposal"
    assert retrieved.user_email == user.email
    assert retrieved.user_role == "Sales"
    assert retrieved.snapshot_data["schema_version"] == SCHEMA_VERSION
    assert retrieved.snapshot_data["quote"]["quote_ref_no"] == quote.quote_ref_no


# 8. Revision numbers are unique per quote
def test_revision_numbers_unique_per_quote(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    rev1 = create_quote_revision(db=db, quote=quote, action="CREATE", user_id=user.id)
    db.add(rev1)
    db.flush()

    # Attempt to insert another revision with the same revision_number=1 for the same quote
    rev_duplicate = QuoteRevision(
        quote_id=quote.id,
        revision_number=1,
        quote_version=quote.version,
        action="EDIT",
        user_id=user.id,
        snapshot_data={"test": "duplicate"}
    )
    db.add(rev_duplicate)

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# 9. Different quotes can independently use the same revision number
def test_different_quotes_can_share_revision_numbers(db):
    solution, region, user = _create_base_entities(db)
    quote1 = _create_sample_quote(db, solution, region, user, quote_ref_no="REF-Q1")
    quote2 = _create_sample_quote(db, solution, region, user, quote_ref_no="REF-Q2")

    rev_q1 = create_quote_revision(db=db, quote=quote1, action="CREATE", user_id=user.id)
    rev_q2 = create_quote_revision(db=db, quote=quote2, action="CREATE", user_id=user.id)

    db.add_all([rev_q1, rev_q2])
    db.flush()  # Must not raise IntegrityError

    assert rev_q1.revision_number == 1
    assert rev_q2.revision_number == 1
    assert rev_q1.quote_id != rev_q2.quote_id


# 10. Snapshot serialization does not modify the source quote or its line items
def test_snapshot_serialization_does_not_mutate_source(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)
    item = QuoteLineItem(
        quote_id=quote.id,
        description="Immutable Check Item",
        sort_order=0,
        quantity=5,
        unit_sell_price_snapshot=Decimal("100.00"),
        unit_cost_price_snapshot=Decimal("50.00"),
        line_sell_total=Decimal("500.00"),
        line_cost_total=Decimal("250.00"),
        margin_percent=Decimal("50.00")
    )
    db.add(item)
    db.flush()

    # Capture source state before serialization
    before_status = quote.status
    before_version = quote.version
    before_total = quote.total_sell_local
    before_qty = item.quantity
    before_sell = item.unit_sell_price_snapshot

    snapshot = serialize_quote_snapshot(quote)

    # Verify source objects are completely unchanged
    assert quote.status == before_status
    assert quote.version == before_version
    assert quote.total_sell_local == before_total
    assert item.quantity == before_qty
    assert item.unit_sell_price_snapshot == before_sell


# 11. Existing quote model behavior remains unchanged
def test_existing_quote_model_behavior_unchanged(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    # Verify revisions relationship defaults to empty list
    assert quote.revisions == []

    # Verify standard quote updates work exactly as before
    quote.client_name = "Updated Client Name"
    quote.version += 1
    db.flush()

    refetched = db.query(Quote).filter(Quote.id == quote.id).first()
    assert refetched.client_name == "Updated Client Name"
    assert refetched.version == 2
    assert len(refetched.revisions) == 0


# 12. Immutability: ORM-level update and delete are rejected
def test_revision_orm_update_and_delete_prevented(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    rev = create_quote_revision(db=db, quote=quote, action="CREATE", user_id=user.id)
    db.add(rev)
    db.flush()

    # Attempt ORM update
    rev.change_reason = "Unauthorized modification attempt"
    with pytest.raises(RuntimeError, match="QuoteRevision instances are immutable and cannot be updated"):
        db.flush()

    db.rollback()

    # Re-fetch revision and attempt ORM delete
    rev2 = db.query(QuoteRevision).filter(QuoteRevision.id == rev.id).first()
    if rev2:
        db.delete(rev2)
        with pytest.raises(RuntimeError, match="QuoteRevision instances are immutable and cannot be deleted"):
            db.flush()
        db.rollback()


# 13. Immutability: PostgreSQL database trigger blocks direct SQL update and delete
def test_revision_database_trigger_blocks_raw_sql(db):
    solution1, region1, user1 = _create_base_entities(db)
    quote1 = _create_sample_quote(db, solution1, region1, user1, quote_ref_no="REF-TRIG-001")
    rev1 = create_quote_revision(db=db, quote=quote1, action="CREATE", user_id=user1.id)
    db.add(rev1)
    db.flush()

    # 1. Test Raw SQL UPDATE is blocked by PostgreSQL trigger
    with pytest.raises(DatabaseError, match="quote_revisions records are immutable and cannot be updated or deleted"):
        db.execute(text(f"UPDATE quote_revisions SET action = 'HACKED' WHERE id = {rev1.id}"))
    db.rollback()

    # 2. Test Raw SQL DELETE is blocked by PostgreSQL trigger
    solution2, region2, user2 = _create_base_entities(db)
    quote2 = _create_sample_quote(db, solution2, region2, user2, quote_ref_no="REF-TRIG-002")
    rev2 = create_quote_revision(db=db, quote=quote2, action="CREATE", user_id=user2.id)
    db.add(rev2)
    db.flush()

    with pytest.raises(DatabaseError, match="quote_revisions records are immutable and cannot be updated or deleted"):
        db.execute(text(f"DELETE FROM quote_revisions WHERE id = {rev2.id}"))
    db.rollback()


# 14. Sequential revision numbering on the same quote
def test_sequential_revision_numbering_on_same_quote(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    rev1 = create_quote_revision(db=db, quote=quote, action="INITIAL_CREATION", user_id=user.id)
    db.add(rev1)
    db.flush()

    rev2 = create_quote_revision(db=db, quote=quote, action="EDIT", user_id=user.id, change_reason="Added server")
    db.add(rev2)
    db.flush()

    rev3 = create_quote_revision(db=db, quote=quote, action="SUBMIT", user_id=user.id, change_reason="Ready for review")
    db.add(rev3)
    db.flush()

    revisions = db.query(QuoteRevision).filter(QuoteRevision.quote_id == quote.id).order_by(QuoteRevision.revision_number.asc()).all()
    assert len(revisions) == 3
    assert [r.revision_number for r in revisions] == [1, 2, 3]
    assert [r.action for r in revisions] == ["INITIAL_CREATION", "EDIT", "SUBMIT"]


# 15. Concurrency row-locking strategy holds lock on parent quote
def test_concurrent_locking_strategy_locks_parent_quote(engine):
    from sqlalchemy.orm import Session

    # Setup: create and commit a quote so it is visible to concurrent connections
    with Session(bind=engine) as setup_db:
        solution, region, user = _create_base_entities(setup_db)
        quote = _create_sample_quote(setup_db, solution, region, user, quote_ref_no="REF-LOCK-TEST-001")
        setup_db.commit()
        quote_id = quote.id
        user_id = user.id

    try:
        # Session 1 starts transaction and calls create_quote_revision which locks the quote
        conn_session1 = engine.connect()
        trans1 = conn_session1.begin()
        db_session1 = Session(bind=conn_session1)

        locked_quote = db_session1.query(Quote).filter(Quote.id == quote_id).first()
        rev = create_quote_revision(db=db_session1, quote=locked_quote, action="CREATE", user_id=user_id, lock_quote=True)
        db_session1.add(rev)
        db_session1.flush()

        # Session 2 attempts to lock the same quote NOWAIT - it must fail because Session 1 holds the row lock!
        with engine.connect() as conn2:
            with pytest.raises(OperationalError, match="could not obtain lock on row in relation|lock"):
                conn2.execute(text(f"SELECT id FROM quotes WHERE id = {quote_id} FOR UPDATE NOWAIT"))

        trans1.rollback()
        conn_session1.close()
    finally:
        with engine.connect() as cleanup:
            cleanup.execute(text(f"DELETE FROM quotes WHERE id = {quote_id}"))
            cleanup.commit()


# 16. Downgrade safety: Alembic downgrade refuses to drop quote_revisions when records exist
def test_migration_downgrade_refuses_when_records_exist(db):
    solution, region, user = _create_base_entities(db)
    quote = _create_sample_quote(db, solution, region, user)

    rev = create_quote_revision(db=db, quote=quote, action="CREATE", user_id=user.id)
    db.add(rev)
    db.flush()

    migration_module = importlib.import_module("backend.alembic.versions.e6a7b8c9d0f1_cp14_quote_revisions")
    ctx = MigrationContext.configure(db.connection())
    with Operations.context(ctx):
        with pytest.raises(RuntimeError, match="Cannot downgrade.*quote revision record.*destroy historical audit data"):
            migration_module.downgrade()

