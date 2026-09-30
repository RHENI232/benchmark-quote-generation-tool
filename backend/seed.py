import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.models.catalog import CatalogItem, CatalogItemKind

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: Requirement schema and business rules are populated as basic placeholders or full structures
# as per documentation. We use structured dicts mirroring the rules.
WTVISION_SCHEMA = {
    "main": [
        {"name": "Number of Studios", "type": "number", "min": 1, "max": 12},
        {"name": "Number of Designers", "type": "number", "min": 0},
        {"name": "News Production", "type": "boolean"},
        {"name": "Journalists", "type": "enum", "options": [10, 25, 50], "depends_on": "News Production"},
        {"name": "MOS Redundancy", "type": "boolean"},
        {"name": "Avid/Adobe NLE Plugin", "type": "boolean"},
        {"name": "NLE Seats", "type": "enum", "options": [5, 10, 15], "depends_on": "Avid/Adobe NLE Plugin"},
        {"name": "NRCS Graphics Preview", "type": "boolean"},
        {"name": "SDI Production Ingest", "type": "boolean"},
        {"name": "Ingest Channels", "type": "number", "min": 0, "depends_on": "SDI Production Ingest"},
        {"name": "Production Playout", "type": "boolean"},
        {"name": "MAM", "type": "boolean"},
        {"name": "3 Years Standard Support", "type": "boolean"}
    ],
    "per_studio": [
        {"name": "Studio Type", "type": "enum", "options": ["Real Set", "VR-AR (R3 Engine)", "VR-AR (Unreal)"]},
        {"name": "Number of Cameras", "type": "enum", "options": [1, 2, 3], "depends_on_value": {"Studio Type": "VR-AR (Unreal)"}},
        {"name": "LED Video Wall", "type": "boolean"},
        {"name": "LED Outputs", "type": "enum", "options": [4, 8], "depends_on": "LED Video Wall"},
        {"name": "Number of Engines", "type": "number", "min": 0},
        {"name": "Dual Channel", "type": "boolean"},
        {"name": "Extra Live Input", "type": "boolean"},
        {"name": "Number of Control Clients", "type": "number", "min": 0}
    ]
}

WTVISION_RULES = {
    # This JSON represents the mapping logic from docs/pricing-rules.md
    "rules": "See docs/pricing-rules.md for the full logical tree"
}

def seed_solutions(db: Session):
    solution_data = {
        "name": "WTVision Graphics",
        "code": None,
        "default_margin_percent": 15.00,
        "requirement_schema": WTVISION_SCHEMA,
        "business_rules": WTVISION_RULES
    }

    solution = db.execute(select(Solution).where(Solution.name == solution_data["name"])).scalar_one_or_none()
    if not solution:
        solution = Solution(**solution_data)
        db.add(solution)
        db.flush()
        logger.info(f"Inserted Solution: {solution_data['name']}")
    else:
        for key, value in solution_data.items():
            setattr(solution, key, value)
        db.flush()
        logger.info(f"Updated Solution: {solution_data['name']}")
    return solution

def seed_regions(db: Session):
    regions_data = [
        {
            "country_name": "Singapore",
            "currency_code": "USD",
            "legal_entity_name": "Benchmark Broadcast Systems (S) Pte Ltd",
            "tax_enabled": False,
            "tax_rate_percent": None,
            "fx_rate_to_usd": 1.000000,
            "fx_rate_as_of": None
        },
        {
            "country_name": "India",
            "currency_code": "INR",
            "legal_entity_name": None,
            "tax_enabled": True,
            "tax_rate_percent": None,
            "fx_rate_to_usd": None,
            "fx_rate_as_of": None
        }
    ]

    for r_data in regions_data:
        region = db.execute(select(Region).where(Region.country_name == r_data["country_name"])).scalar_one_or_none()
        if not region:
            region = Region(**r_data)
            db.add(region)
            logger.info(f"Inserted Region: {r_data['country_name']}")
        else:
            for key, value in r_data.items():
                setattr(region, key, value)
            logger.info(f"Updated Region: {r_data['country_name']}")

def seed_admin_user(db: Session):
    user_data = {
        "email": "admin@benchmark.local",
        "role_tier": RoleTier.ADMIN,
        "account_type": AccountType.MANUAL,
        "enabled": True,
        "password_hash": None  # Nullable because of Phase 1 manual invite flow / TBC hash
    }

    user = db.execute(select(User).where(User.email == user_data["email"])).scalar_one_or_none()
    if not user:
        user = User(**user_data)
        db.add(user)
        logger.info(f"Inserted User: {user_data['email']}")
    else:
        for key, value in user_data.items():
            setattr(user, key, value)
        logger.info(f"Updated User: {user_data['email']}")

DEFAULT_CATALOG_DATA = [
    # Ingest
    {"lookup_key": "cat_wtv_000001", "part_number": "MT1010", "description": "Ingest – base unit, 1 per box", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000002", "part_number": "MT1011", "description": "Each extra channel beyond the first in its box", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000003", "part_number": "MT1020", "description": "Trimmer, one per channel", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000004", "part_number": "BDLKDVQD2", "description": "Ingest Capture Card (4-channel)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000005", "part_number": "INGSVR101", "description": "Ingest Server hardware, one per box", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},

    # MAM
    {"lookup_key": "cat_wtv_000006", "part_number": "MM1000", "description": "wTVision Media Manager, includes 1 Media Agent", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000007", "part_number": "MA1001", "description": "Extra Locations/Media Agents, one per studio", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000008", "part_number": "MAMSVR101", "description": "MAM Server hardware", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},

    # Production Playout
    {"lookup_key": "cat_wtv_000009", "part_number": "MP0001", "description": "wTVision Media Server, Single Channel FHD", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000010", "part_number": "MP0012", "description": "First Input Manager", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},

    # Playout Controller
    {"lookup_key": "cat_wtv_000011", "part_number": "SC1000", "description": "Studio CG — central control app", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000012", "part_number": "STDCG101", "description": "Studio CG Control PC hardware", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},
    {"lookup_key": "cat_wtv_000013", "part_number": "PL1001", "description": "R³ Engine Plugin for Studio CG", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000014", "part_number": "PL1004", "description": "Media Server Controller Plugin", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},

    # Graphics Engine
    {"lookup_key": "cat_wtv_000015", "part_number": "R30001", "description": "Graphics Engine (Base)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000016", "part_number": "R3ENG101", "description": "Graphics Engine Companion Hardware", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000017", "part_number": "BDLKDVQD2", "description": "Graphics IO card", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},
    {"lookup_key": "cat_wtv_000018", "part_number": "R30010", "description": "Dual Channel", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000019", "part_number": "R30020", "description": "Extra Live Input", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000020", "part_number": "wG4000", "description": "LED Video Wall (4 outputs)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000021", "part_number": "wG8000", "description": "LED Video Wall (8 outputs)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000022", "part_number": "vWALLENG101", "description": "LED Video Wall Engine", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},
    {"lookup_key": "cat_wtv_000023", "part_number": "UE0002", "description": "VR-AR Unreal Engine Base", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000024", "part_number": "ARENG101", "description": "VR-AR Engine Hardware", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},
    {"lookup_key": "cat_wtv_000025", "part_number": "wV3000", "description": "VR-AR Unreal Bundle", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000026", "part_number": "IMMVRENG101", "description": "VR-AR Unreal Engine Companion", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},
    {"lookup_key": "cat_wtv_000027", "part_number": "BDLKHCPRO8K12GG2", "description": "Capture Card — spec TBC", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},

    # Designer Tools
    {"lookup_key": "cat_wtv_000028", "part_number": "DE1001", "description": "R³ Designer", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000029", "part_number": "R3DES101", "description": "R³ Designer Workstation hardware", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": 0.00, "cost_price": 0.00},

    # NRCS Integration
    {"lookup_key": "cat_wtv_000030", "part_number": "MG1000", "description": "NRCS Integration Base", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000031", "part_number": "NP1010", "description": "NRCS Integration (10 Journalists)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000032", "part_number": "NP1025", "description": "NRCS Integration (25 Journalists)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000033", "part_number": "NP1050", "description": "NRCS Integration (50 Journalists)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000034", "part_number": "MG1001", "description": "MOS Redundancy", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000035", "part_number": "PW1000", "description": "NRCS Graphics Preview", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},

    # NLE Plugin
    {"lookup_key": "cat_wtv_000036", "part_number": "NLE105", "description": "NLE Plugin (5 Seats)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000037", "part_number": "NLE110", "description": "NLE Plugin (10 Seats)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000038", "part_number": "NLE115", "description": "NLE Plugin (15 Seats)", "brand": None, "kind": CatalogItemKind.RULE_DRIVEN, "sell_price": None, "cost_price": None},

    # Reference items and documented duplicates
    {"lookup_key": "cat_wtv_000039", "part_number": "PS1050", "description": "Professional Services (Variant A)", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000040", "part_number": "PS1050", "description": "Professional Services (Variant B)", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000041", "part_number": "R31050", "description": "Render Engine Option A", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000042", "part_number": "R31050", "description": "Render Engine Option B", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000043", "part_number": "NLE110", "description": "NLE Plugin (15 Seats variant)", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
    {"lookup_key": "cat_wtv_000044", "part_number": None, "description": "PCR-ENGINE concept (Part Number TBC)", "brand": None, "kind": CatalogItemKind.REFERENCE, "sell_price": None, "cost_price": None},
]

def seed_catalog_items(db: Session, solution: Solution):
    for item_data in DEFAULT_CATALOG_DATA:
        # Idempotency lookup uses stable lookup_key to ensure
        # identical items are explicitly preserved.
        item = db.execute(
            select(CatalogItem).where(
                CatalogItem.lookup_key == item_data["lookup_key"]
            )
        ).scalar_one_or_none()

        if not item:
            item = CatalogItem(solution_id=solution.id, **item_data)
            db.add(item)
            logger.info(f"Inserted Catalog Item: {item_data['part_number']} - {item_data['description']}")
        else:
            for key, value in item_data.items():
                setattr(item, key, value)
            logger.info(f"Updated Catalog Item: {item_data['part_number']} - {item_data['description']}")

def run_seed():
    db = SessionLocal()
    try:
        solution = seed_solutions(db)
        seed_regions(db)
        seed_admin_user(db)
        seed_catalog_items(db, solution)
        db.commit()
        logger.info("Seed data applied successfully.")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database seed failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
