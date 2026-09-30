from sqlalchemy import select
from backend.app.models.solution import Solution
from backend.app.models.region import Region
from backend.app.models.user import User
from backend.app.models.catalog import CatalogItem, CatalogItemKind
from backend.seed import seed_solutions, seed_regions, seed_admin_user, seed_catalog_items

def test_seed_solution_data(db):
    """Verify Solution seed data is exactly as expected in Phase 1."""
    solutions = db.execute(select(Solution)).scalars().all()
    assert len(solutions) == 1
    
    sol = solutions[0]
    assert sol.name == "WTVision Graphics"
    assert sol.code is None
    assert sol.default_margin_percent == 15.00
    assert "main" in sol.requirement_schema
    assert sol.business_rules.get("rules") == "See docs/pricing-rules.md for the full logical tree"

def test_seed_region_data(db):
    """Verify Region seed data for Singapore and India."""
    regions = db.execute(select(Region)).scalars().all()
    assert len(regions) == 2
    
    sg = next(r for r in regions if r.country_name == "Singapore")
    assert sg.currency_code == "USD"
    assert sg.fx_rate_to_usd == 1.000000
    assert sg.tax_enabled is False
    assert sg.legal_entity_name == "Benchmark Broadcast Systems (S) Pte Ltd"
    
    ind = next(r for r in regions if r.country_name == "India")
    assert ind.currency_code == "INR"
    assert ind.legal_entity_name is None
    assert ind.tax_enabled is True
    assert ind.tax_rate_percent is None
    assert ind.fx_rate_to_usd is None

def test_seed_admin_user(db):
    """Verify Admin user is properly seeded without a password."""
    users = db.execute(select(User)).scalars().all()
    assert len(users) == 1
    
    admin = users[0]
    assert admin.email == "admin@benchmark.local"
    assert admin.role_tier.value == "Admin"
    assert admin.account_type.value == "manual"
    assert admin.enabled is True
    assert admin.password_hash is None

def test_seed_catalog_data(db):
    """Verify exactly 44 items, specific BDLKDVQD2 handling, and NULL logic."""
    items = db.execute(select(CatalogItem)).scalars().all()
    assert len(items) == 44
    
    # All belong to WTVision Graphics
    solution = db.execute(select(Solution)).scalars().first()
    assert all(item.solution_id == solution.id for item in items)
    
    # Exactly two BDLKDVQD2 rows
    bdlk = [i for i in items if i.part_number == "BDLKDVQD2"]
    assert len(bdlk) == 2
    
    # NLE115 rule-driven exists
    assert any(i.part_number == "NLE115" and i.kind == CatalogItemKind.RULE_DRIVEN for i in items)
    
    # NLE110 reference exists
    assert any(i.part_number == "NLE110" and i.kind == CatalogItemKind.REFERENCE for i in items)
    
    # PCR-ENGINE reference exists with NULL Part Number
    assert any("PCR-ENGINE" in i.description and i.part_number is None and i.kind == CatalogItemKind.REFERENCE for i in items)
    
    # Support CatalogItem does NOT exist
    assert not any("Support" in i.description for i in items)
    
    # Explicit zero-price items remain zero
    zero_items = [i for i in items if i.sell_price == 0.00]
    assert len(zero_items) > 0  # There should be 9
    
    # Unresolved prices remain NULL
    null_price_items = [i for i in items if i.sell_price is None]
    assert len(null_price_items) > 0  # There should be 35
    
    # Unresolved brands remain NULL
    assert all(item.brand is None for item in items)

def test_seed_idempotency(db):
    """
    Verify running seed functions again inside a transaction 
    updates instead of inserting duplicates.
    """
    # Count rows before
    count_sol_before = db.query(Solution).count()
    count_reg_before = db.query(Region).count()
    count_usr_before = db.query(User).count()
    count_cat_before = db.query(CatalogItem).count()
    
    # Re-run seed on existing session (simulates 2nd execution)
    solution = seed_solutions(db)
    seed_regions(db)
    seed_admin_user(db)
    seed_catalog_items(db, solution)
    db.flush()
    
    # Count rows after
    assert db.query(Solution).count() == count_sol_before
    assert db.query(Region).count() == count_reg_before
    assert db.query(User).count() == count_usr_before
    assert db.query(CatalogItem).count() == count_cat_before
    
    # Extra check for BDLKDVQD2 duplication
    items = db.execute(select(CatalogItem).where(CatalogItem.part_number == "BDLKDVQD2")).scalars().all()
    assert len(items) == 2
