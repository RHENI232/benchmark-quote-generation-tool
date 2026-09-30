from sqlalchemy.exc import IntegrityError
import pytest
from backend.app.models.catalog import CatalogItem, CatalogItemKind
from backend.app.models.quote import Quote, QuoteLineItem, QuoteStatus
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.models.user import User, RoleTier, AccountType

def test_catalog_part_number_not_unique(db):
    """Verify that multiple CatalogItems can have the same part_number."""
    solution = Solution(name="Test Solution")
    db.add(solution)
    db.flush()

    item1 = CatalogItem(
        solution_id=solution.id,
        lookup_key="cat_test_dup1",
        kind=CatalogItemKind.RULE_DRIVEN,
        part_number="DUPLICATE_123",
        description="First item"
    )
    item2 = CatalogItem(
        solution_id=solution.id,
        lookup_key="cat_test_dup2",
        kind=CatalogItemKind.REFERENCE,
        part_number="DUPLICATE_123",
        description="Second item"
    )
    db.add_all([item1, item2])
    db.flush()  # Should not raise IntegrityError
    assert item1.id != item2.id
    assert item1.part_number == item2.part_number

def test_quote_line_item_catalog_id_nullable(db):
    """Verify QuoteLineItem.catalog_item_id can be NULL."""
    solution = Solution(name="Test Solution")
    region = Region(country_name="Test Country", currency_code="USD")
    user = User(email="test@example.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL)
    db.add_all([solution, region, user])
    db.flush()

    quote = Quote(
        solution_id=solution.id,
        region_id=region.id,
        client_name="Client",
        quote_ref_no="REF-123",
        created_by_user_id=user.id,
        last_edited_by_user_id=user.id
    )
    db.add(quote)
    db.flush()

    line_item = QuoteLineItem(
        quote_id=quote.id,
        catalog_item_id=None,
        description="Custom Item",
        unit_sell_price_snapshot=0.0,
        unit_cost_price_snapshot=0.0
    )
    db.add(line_item)
    db.flush()  # Should not raise
    assert line_item.catalog_item_id is None

def test_nullable_fields_allowed(db):
    """Verify other specified fields can be NULL."""
    region = Region(country_name="Null Region", currency_code="USD")
    db.add(region)
    db.flush()
    assert region.legal_entity_name is None
    assert region.fx_rate_to_usd is None

    solution = Solution(name="Null Solution")
    db.add(solution)
    db.flush()
    assert solution.code is None

    catalog_item = CatalogItem(
        solution_id=solution.id,
        lookup_key="cat_test_nullable",
        kind=CatalogItemKind.REFERENCE,
        description="Null Price Item"
    )
    db.add(catalog_item)
    db.flush()
    assert catalog_item.sell_price is None
    assert catalog_item.cost_price is None
    assert catalog_item.part_number is None

def test_user_email_unique(db):
    """Verify User.email must be unique."""
    user1 = User(email="unique@example.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL)
    user2 = User(email="unique@example.com", role_tier=RoleTier.SALES, account_type=AccountType.MANUAL)
    
    db.add(user1)
    db.flush()
    
    db.add(user2)
    with pytest.raises(IntegrityError):
        db.flush()
