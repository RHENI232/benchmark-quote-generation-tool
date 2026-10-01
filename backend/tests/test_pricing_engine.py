import pytest
from sqlalchemy.orm import Session
from backend.app.models.quote import Quote, QuoteStatus
from backend.app.models.catalog import CatalogItem, CatalogItemKind
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.schemas.requirement import RequirementPayload, StudioRequirement
from backend.app.schemas.bom import BOMLineSpec
from backend.app.services.engines.pricing_engine import PricingEngine, PricingEngineError
from decimal import Decimal

@pytest.fixture
def base_data(db: Session):
    user = User(email="pricing@example.com", role_tier=RoleTier.ADMIN, account_type=AccountType.MANUAL)
    solution = Solution(name="Pricing Test Solution")
    
    # USD Region
    region_usd = Region(
        country_name="Test USA", currency_code="USD",
        tax_enabled=True, tax_rate_percent=Decimal("10.0"),
        fx_rate_to_usd=Decimal("1.0"),
        legal_entity_name="Benchmark US"
    )
    
    # Non-USD Region
    region_in = Region(
        country_name="Test India", currency_code="INR",
        tax_enabled=True, tax_rate_percent=Decimal("18.0"),
        fx_rate_to_usd=Decimal("83.5"),
        legal_entity_name="Benchmark India"
    )
    
    # Bad Region (Missing FX)
    region_bad = Region(
        country_name="Test Unknown", currency_code="EUR",
        tax_enabled=False,
        fx_rate_to_usd=Decimal("0.0")
    )
    
    db.add_all([user, solution, region_usd, region_in, region_bad])
    db.flush()
    
    cat1 = CatalogItem(
        solution_id=solution.id, lookup_key="cat_test_p1",
        kind=CatalogItemKind.RULE_DRIVEN, description="Item 1", brand="wTVision",
        sell_price=Decimal("1000.0"), cost_price=Decimal("800.0")
    )
    cat2 = CatalogItem(
        solution_id=solution.id, lookup_key="cat_test_p2",
        kind=CatalogItemKind.RULE_DRIVEN, description="Item 2", brand="wTVision",
        sell_price=Decimal("0.0"), cost_price=Decimal("0.0") # Zero price check
    )
    cat3 = CatalogItem(
        solution_id=solution.id, lookup_key="cat_test_p3",
        kind=CatalogItemKind.REFERENCE, description="Item 3", brand="Other",
        sell_price=Decimal("500.0"), cost_price=Decimal("600.0") # Negative margin check
    )
    
    db.add_all([cat1, cat2, cat3])
    db.flush()
    
    return {
        "user": user,
        "solution": solution,
        "region_usd": region_usd,
        "region_in": region_in,
        "region_bad": region_bad,
        "cat1": cat1, "cat2": cat2, "cat3": cat3
    }

def create_quote(db, base_data, region_key="region_usd", status=QuoteStatus.DRAFT, version=1):
    quote = Quote(
        solution_id=base_data["solution"].id,
        region_id=base_data[region_key].id,
        client_name="Test Client",
        quote_ref_no=f"REF-{db.query(Quote).count()+1}",
        created_by_user_id=base_data["user"].id,
        last_edited_by_user_id=base_data["user"].id,
        status=status,
        version=version,
        requirement_data={}
    )
    db.add(quote)
    db.flush()
    return quote

def test_pricing_engine_basic_usd_recalculation(db, base_data):
    quote = create_quote(db, base_data, "region_usd", version=1)
    
    payload = RequirementPayload(
        number_of_studios=1,
        studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)],
        three_years_support=True
    )
    
    bom = [
        BOMLineSpec(lookup_key="cat_test_p1", quantity=2, section="Graphics"), # 2 * 1000 = 2000
        BOMLineSpec(lookup_key="cat_test_p2", quantity=1, section="Graphics"), # 1 * 0 = 0
        BOMLineSpec(lookup_key="cat_test_p3", quantity=2, section="Graphics")  # 2 * 500 = 1000
    ]
    
    PricingEngine.calculate_and_save_quote(db, quote, payload, bom)
    
    assert quote.version == 2
    assert quote.currency_code == "USD"
    assert quote.fx_rate_to_usd == Decimal("1.0")
    
    assert len(quote.line_items) == 4
    
    l1 = next(li for li in quote.line_items if li.catalog_item_id == base_data["cat1"].id)
    assert l1.margin_percent == Decimal("20.0")
    assert l1.line_sell_total == Decimal("2000.0")
    
    l2 = next(li for li in quote.line_items if li.catalog_item_id == base_data["cat2"].id)
    assert l2.margin_percent == Decimal("0.0")
    assert l2.line_sell_total == Decimal("0.0")
    
    l3 = next(li for li in quote.line_items if li.catalog_item_id == base_data["cat3"].id)
    assert l3.margin_percent == Decimal("-20.0")
    assert l3.line_sell_total == Decimal("1000.0")
    
    support_line = next(li for li in quote.line_items if li.catalog_item_id is None)
    assert support_line.description == "First 3 Years Support - Standard"
    assert support_line.margin_percent == Decimal("0.0")
    assert support_line.line_sell_total == Decimal("600.0")
    
    assert quote.subtotal_sell_usd == Decimal("3600.0")
    assert quote.total_sell_local == Decimal("3600.0")
    assert quote.tax_amount == Decimal("360.0")

def test_pricing_engine_fx_and_tax(db, base_data):
    quote = create_quote(db, base_data, "region_in")
    
    payload = RequirementPayload(number_of_studios=1, studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)])
    bom = [BOMLineSpec(lookup_key="cat_test_p1", quantity=1, section="A")] # 1000 USD
    
    PricingEngine.calculate_and_save_quote(db, quote, payload, bom)
    
    assert quote.currency_code == "INR"
    assert quote.fx_rate_to_usd == Decimal("83.5")
    
    assert quote.subtotal_sell_usd == Decimal("1000.0")
    assert quote.total_sell_local == Decimal("83500.0")
    assert quote.tax_amount == Decimal("15030.0")

def test_pricing_engine_invalid_fx_blocks(db, base_data):
    quote = create_quote(db, base_data, "region_bad")
    payload = RequirementPayload(number_of_studios=1, studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)])
    bom = []
    
    with pytest.raises(PricingEngineError, match="valid positive fx_rate_to_usd"):
        PricingEngine.calculate_and_save_quote(db, quote, payload, bom)

def test_pricing_engine_saved_quote_immutable(db, base_data):
    quote = create_quote(db, base_data, status=QuoteStatus.SAVED)
    payload = RequirementPayload(number_of_studios=1, studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)])
    bom = []
    
    with pytest.raises(PricingEngineError, match="immutable"):
        PricingEngine.calculate_and_save_quote(db, quote, payload, bom)

def test_pricing_engine_invalid_lookup_key(db, base_data):
    quote = create_quote(db, base_data)
    payload = RequirementPayload(number_of_studios=1, studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)])
    bom = [BOMLineSpec(lookup_key="DOES_NOT_EXIST", quantity=1, section="A")]
    
    with pytest.raises(PricingEngineError, match="not found"):
        PricingEngine.calculate_and_save_quote(db, quote, payload, bom)

def test_pricing_engine_decimal_precision(db, base_data):
    cat_precision = CatalogItem(
        solution_id=base_data["solution"].id, lookup_key="cat_precision_test",
        kind=CatalogItemKind.RULE_DRIVEN, description="Precision Item", brand="wTVision",
        sell_price=Decimal("0.10"), cost_price=Decimal("0.10")
    )
    db.add(cat_precision)
    db.flush()
    
    quote = create_quote(db, base_data, "region_usd", version=1)
    payload = RequirementPayload(number_of_studios=1, studios=[StudioRequirement(studio_index=0, studio_type="Real Set", number_of_engines=0)])
    bom = [BOMLineSpec(lookup_key="cat_precision_test", quantity=3, section="A")]
    
    PricingEngine.calculate_and_save_quote(db, quote, payload, bom)
    
    assert quote.subtotal_sell_usd == Decimal("0.30")
