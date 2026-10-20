"""
Quote Revision Service
Handles deterministic serialization and creation of immutable quote revision snapshots.
"""
from typing import Optional, Any, Dict, List
import copy
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from backend.app.models.quote import Quote, QuoteRevision, QuoteLineItem
from backend.app.api.deps import has_permission


SCHEMA_VERSION = "1.0"


def serialize_decimal(val: Any) -> Optional[str]:
    """
    Safely serializes a numeric value to a string, preserving exact decimal precision
    without converting into binary floating-point representation.
    """
    if val is None:
        return None
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, (int,)):
        return str(val)
    if isinstance(val, float):
        # Convert float via its string representation to Decimal
        return str(Decimal(str(val)))
    if isinstance(val, str):
        # Validate that it is a valid decimal string and normalize
        return str(Decimal(val.strip()))
    return str(val)


def serialize_datetime(val: Any) -> Optional[str]:
    """
    Safely serializes datetime/date objects to ISO 8601 formatted strings.
    """
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    return str(val)


def serialize_quote_snapshot(quote: Quote) -> Dict[str, Any]:
    """
    Generates a complete, deterministic, frozen JSON snapshot of a quote and its
    associated line items, financials, and legal entity configuration.

    This snapshot is entirely standalone and does not rely on future live catalog,
    region, or user database queries to reproduce the historical state.
    """
    # 1. Header Information
    status_str = quote.status.value if hasattr(quote.status, "value") else str(quote.status) if quote.status else None
    solution_name = quote.solution.name if getattr(quote, "solution", None) else None
    region_name = quote.region.country_name if getattr(quote, "region", None) else None

    quote_header = {
        "id": quote.id,
        "quote_ref_no": quote.quote_ref_no,
        "version": quote.version,
        "status": status_str,
        "client_name": quote.client_name,
        "attention": quote.attention,
        "description": quote.description,
        "date": serialize_datetime(quote.date),
        "solution_id": quote.solution_id,
        "solution_name": solution_name,
        "region_id": quote.region_id,
        "region_name": region_name,
        "created_by_user_id": quote.created_by_user_id,
        "last_edited_by_user_id": quote.last_edited_by_user_id,
        "created_at": serialize_datetime(quote.created_at),
        "updated_at": serialize_datetime(quote.updated_at),
        "deleted_at": serialize_datetime(quote.deleted_at),
        "is_urgent": bool(quote.is_urgent),
        "requirement_data": dict(quote.requirement_data) if quote.requirement_data is not None else {},
    }

    # 2. Financial Snapshots
    financials = {
        "currency_code": quote.currency_code,
        "fx_rate_to_usd": serialize_decimal(quote.fx_rate_to_usd),
        "fx_rate_as_of": quote.fx_rate_as_of,
        "tax_enabled": bool(quote.tax_enabled),
        "tax_rate_percent": serialize_decimal(quote.tax_rate_percent),
        "subtotal_cost_usd": serialize_decimal(quote.subtotal_cost_usd),
        "subtotal_sell_usd": serialize_decimal(quote.subtotal_sell_usd),
        "tax_amount": serialize_decimal(quote.tax_amount),
        "total_sell_local": serialize_decimal(quote.total_sell_local),
    }

    # 3. Legal Entity Snapshots
    legal_entity = {
        "legal_entity_name": quote.legal_entity_name,
        "legal_entity_registration_number": quote.legal_entity_registration_number,
        "legal_entity_address": quote.legal_entity_address,
        "legal_entity_contact": quote.legal_entity_contact,
    }

    # 4. Bill of Quantities (BOM Line Items) - Deterministic Ordering by sort_order, then id
    raw_items = quote.line_items or []
    sorted_items = sorted(
        raw_items,
        key=lambda item: (
            item.sort_order if getattr(item, "sort_order", None) is not None else 0,
            item.id if getattr(item, "id", None) is not None else 0
        )
    )

    line_items: List[Dict[str, Any]] = []
    for item in sorted_items:
        line_items.append({
            "id": item.id,
            "catalog_item_id": item.catalog_item_id,
            "sort_order": item.sort_order,
            "section": item.section,
            "part_number": item.part_number,
            "brand": item.brand,
            "description": item.description,
            "quantity": item.quantity,
            "unit_cost_price_snapshot": serialize_decimal(item.unit_cost_price_snapshot),
            "unit_sell_price_snapshot": serialize_decimal(item.unit_sell_price_snapshot),
            "line_cost_total": serialize_decimal(item.line_cost_total),
            "line_sell_total": serialize_decimal(item.line_sell_total),
            "margin_percent": serialize_decimal(item.margin_percent),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.datetime.utcnow().isoformat(),
        "quote": quote_header,
        "financials": financials,
        "legal_entity": legal_entity,
        "line_items": line_items,
    }


def create_quote_revision(
    db: Session,
    quote: Quote,
    action: str,
    user_id: int,
    change_reason: Optional[str] = None,
    lock_quote: bool = True
) -> QuoteRevision:
    """
    Constructs a new immutable QuoteRevision for the given quote.

    Concurrency Safety Strategy:
    Acquires a pessimistic row lock (SELECT ... FOR UPDATE) on the parent Quote
    row before calculating the next revision number. This serializes all
    concurrent revision creation requests for the same quote at the database
    level, guaranteeing strictly sequential revision numbering.

    The database unique constraint `uq_quote_revisions_quote_id_revision_number`
    serves as the final integrity safeguard.
    """
    if lock_quote and quote.id is not None:
        # Lock parent quote row to serialize revision generation across concurrent transactions
        db.query(Quote.id).filter(Quote.id == quote.id).with_for_update().scalar()

    max_rev = db.query(func.max(QuoteRevision.revision_number)).filter(
        QuoteRevision.quote_id == quote.id
    ).scalar()
    next_revision_number = 1 if max_rev is None else max_rev + 1

    snapshot = serialize_quote_snapshot(quote)

    revision = QuoteRevision(
        quote_id=quote.id,
        revision_number=next_revision_number,
        quote_version=quote.version if quote.version is not None else 1,
        action=action,
        user_id=user_id,
        change_reason=change_reason,
        created_at=datetime.datetime.utcnow(),
        snapshot_data=snapshot,
    )
    return revision


def mask_revision_snapshot(snapshot: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
    """
    Applies role-based financial confidentiality masking to a quote revision snapshot.
    If the caller lacks 'cost_visibility' permission (e.g. Sales or Catalog Entry),
    sensitive cost and margin fields are masked to None.

    Returns a deep-copied dictionary to guarantee the underlying snapshot data remains intact.
    """
    snap_copy = copy.deepcopy(snapshot)
    if not has_permission("cost_visibility", current_user):
        financials = snap_copy.get("financials")
        if isinstance(financials, dict):
            financials["subtotal_cost_usd"] = None

        line_items = snap_copy.get("line_items")
        if isinstance(line_items, list):
            for item in line_items:
                if isinstance(item, dict):
                    item["unit_cost_price_snapshot"] = None
                    item["line_cost_total"] = None
                    item["margin_percent"] = None
    return snap_copy


def get_quote_revisions(
    db: Session,
    quote_id: int,
    skip: int = 0,
    limit: int = 50,
    order: str = "asc"
) -> List[QuoteRevision]:
    """
    Queries historical revisions for a quote with deterministic ordering and bounded pagination.
    Eager-loads the capturing user to optimize performance.
    """
    query = db.query(QuoteRevision).options(
        joinedload(QuoteRevision.user)
    ).filter(
        QuoteRevision.quote_id == quote_id
    )

    if order.lower() == "desc":
        query = query.order_by(QuoteRevision.revision_number.desc(), QuoteRevision.id.desc())
    else:
        query = query.order_by(QuoteRevision.revision_number.asc(), QuoteRevision.id.asc())

    return query.offset(skip).limit(limit).all()


def get_quote_revision_by_number(
    db: Session,
    quote_id: int,
    revision_number: int
) -> Optional[QuoteRevision]:
    """
    Retrieves a single historical revision by quote ID and revision number.
    Eager-loads the capturing user.
    """
    return db.query(QuoteRevision).options(
        joinedload(QuoteRevision.user),
        joinedload(QuoteRevision.quote)
    ).filter(
        QuoteRevision.quote_id == quote_id,
        QuoteRevision.revision_number == revision_number
    ).first()


def compare_quote_revisions(
    db: Session,
    quote_id: int,
    base_revision_number: int,
    target_revision_number: int,
    current_user: Any
) -> Dict[str, Any]:
    """
    Performs a deterministic, read-only field-level comparison between two historical
    revision snapshots belonging to the same quote.

    Security & Masking:
    Snapshots are masked according to the caller's role before difference calculation,
    ensuring unauthorized users (Sales, Catalog Entry) cannot infer restricted cost
    or margin values from comparison output or field diffs.
    """
    base_rev = get_quote_revision_by_number(db, quote_id=quote_id, revision_number=base_revision_number)
    if not base_rev:
        raise ValueError(f"Revision {base_revision_number} not found for quote {quote_id}")

    target_rev = get_quote_revision_by_number(db, quote_id=quote_id, revision_number=target_revision_number)
    if not target_rev:
        raise ValueError(f"Revision {target_revision_number} not found for quote {quote_id}")

    # Ensure both revisions belong to the requested quote
    if base_rev.quote_id != quote_id or target_rev.quote_id != quote_id:
        raise ValueError("Cannot compare revisions belonging to different quotes.")

    # Apply role-based financial masking before comparison
    snap_a = mask_revision_snapshot(base_rev.snapshot_data, current_user)
    snap_b = mask_revision_snapshot(target_rev.snapshot_data, current_user)

    # 1. Compare Quote Metadata
    metadata_fields = [
        "status", "client_name", "attention", "description",
        "solution_id", "solution_name", "region_id", "region_name", "is_urgent"
    ]
    metadata_changes: Dict[str, Dict[str, Any]] = {}
    quote_a = snap_a.get("quote", {})
    quote_b = snap_b.get("quote", {})
    for f in metadata_fields:
        val_a = quote_a.get(f)
        val_b = quote_b.get(f)
        if val_a != val_b:
            metadata_changes[f] = {"old": val_a, "new": val_b, "changed": True}

    # 2. Compare Requirements
    req_a = quote_a.get("requirement_data") or {}
    req_b = quote_b.get("requirement_data") or {}
    requirement_changes: Dict[str, Dict[str, Any]] = {}
    all_req_keys = sorted(set(req_a.keys()) | set(req_b.keys()))
    for k in all_req_keys:
        val_a = req_a.get(k)
        val_b = req_b.get(k)
        if val_a != val_b:
            requirement_changes[k] = {"old": val_a, "new": val_b, "changed": True}

    # 3. Compare Financials
    financial_fields = [
        "currency_code", "fx_rate_to_usd", "fx_rate_as_of",
        "tax_enabled", "tax_rate_percent", "tax_amount",
        "subtotal_sell_usd", "total_sell_local"
    ]
    if has_permission("cost_visibility", current_user):
        financial_fields.append("subtotal_cost_usd")

    financial_changes: Dict[str, Dict[str, Any]] = {}
    fin_a = snap_a.get("financials", {})
    fin_b = snap_b.get("financials", {})
    for f in financial_fields:
        val_a = fin_a.get(f)
        val_b = fin_b.get(f)
        if val_a != val_b:
            financial_changes[f] = {"old": val_a, "new": val_b, "changed": True}

    # 4. Compare Legal Entity
    legal_fields = [
        "legal_entity_name", "legal_entity_registration_number",
        "legal_entity_address", "legal_entity_contact"
    ]
    legal_entity_changes: Dict[str, Dict[str, Any]] = {}
    le_a = snap_a.get("legal_entity", {})
    le_b = snap_b.get("legal_entity", {})
    for f in legal_fields:
        val_a = le_a.get(f)
        val_b = le_b.get(f)
        if val_a != val_b:
            legal_entity_changes[f] = {"old": val_a, "new": val_b, "changed": True}

    # 5. Compare Line Items
    def _index_items(items: List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
        counts: Dict[Any, int] = {}
        indexed: Dict[Any, Dict[str, Any]] = {}
        for item in items:
            key = (
                item.get("catalog_item_id"),
                item.get("part_number"),
                item.get("section")
            )
            occ = counts.get(key, 0)
            counts[key] = occ + 1
            indexed[(key, occ)] = item
        return indexed

    map_a = _index_items(snap_a.get("line_items", []))
    map_b = _index_items(snap_b.get("line_items", []))

    line_fields_to_compare = [
        "quantity", "unit_sell_price_snapshot", "line_sell_total",
        "description", "brand", "sort_order"
    ]
    if has_permission("cost_visibility", current_user):
        line_fields_to_compare.extend([
            "unit_cost_price_snapshot", "line_cost_total", "margin_percent"
        ])

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    modified: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []

    # Check added
    for key, item_b in map_b.items():
        if key not in map_a:
            added.append({
                "catalog_item_id": item_b.get("catalog_item_id"),
                "part_number": item_b.get("part_number"),
                "brand": item_b.get("brand"),
                "description": item_b.get("description", ""),
                "section": item_b.get("section"),
                "status": "added",
                "quantity_old": None,
                "quantity_new": item_b.get("quantity"),
                "unit_sell_price_old": None,
                "unit_sell_price_new": item_b.get("unit_sell_price_snapshot"),
                "line_sell_total_old": None,
                "line_sell_total_new": item_b.get("line_sell_total"),
                "unit_cost_price_old": None,
                "unit_cost_price_new": item_b.get("unit_cost_price_snapshot"),
                "line_cost_total_old": None,
                "line_cost_total_new": item_b.get("line_cost_total"),
                "margin_percent_old": None,
                "margin_percent_new": item_b.get("margin_percent"),
                "field_changes": {}
            })

    # Check removed
    for key, item_a in map_a.items():
        if key not in map_b:
            removed.append({
                "catalog_item_id": item_a.get("catalog_item_id"),
                "part_number": item_a.get("part_number"),
                "brand": item_a.get("brand"),
                "description": item_a.get("description", ""),
                "section": item_a.get("section"),
                "status": "removed",
                "quantity_old": item_a.get("quantity"),
                "quantity_new": None,
                "unit_sell_price_old": item_a.get("unit_sell_price_snapshot"),
                "unit_sell_price_new": None,
                "line_sell_total_old": item_a.get("line_sell_total"),
                "line_sell_total_new": None,
                "unit_cost_price_old": item_a.get("unit_cost_price_snapshot"),
                "unit_cost_price_new": None,
                "line_cost_total_old": item_a.get("line_cost_total"),
                "line_cost_total_new": None,
                "margin_percent_old": item_a.get("margin_percent"),
                "margin_percent_new": None,
                "field_changes": {}
            })

    # Check modified / unchanged
    for key in set(map_a.keys()) & set(map_b.keys()):
        item_a = map_a[key]
        item_b = map_b[key]

        field_diffs: Dict[str, Dict[str, Any]] = {}
        for f in line_fields_to_compare:
            val_a = item_a.get(f)
            val_b = item_b.get(f)
            if val_a != val_b:
                field_diffs[f] = {"old": val_a, "new": val_b, "changed": True}

        entry = {
            "catalog_item_id": item_b.get("catalog_item_id"),
            "part_number": item_b.get("part_number"),
            "brand": item_b.get("brand"),
            "description": item_b.get("description", ""),
            "section": item_b.get("section"),
            "status": "modified" if field_diffs else "unchanged",
            "quantity_old": item_a.get("quantity"),
            "quantity_new": item_b.get("quantity"),
            "unit_sell_price_old": item_a.get("unit_sell_price_snapshot"),
            "unit_sell_price_new": item_b.get("unit_sell_price_snapshot"),
            "line_sell_total_old": item_a.get("line_sell_total"),
            "line_sell_total_new": item_b.get("line_sell_total"),
            "unit_cost_price_old": item_a.get("unit_cost_price_snapshot"),
            "unit_cost_price_new": item_b.get("unit_cost_price_snapshot"),
            "line_cost_total_old": item_a.get("line_cost_total"),
            "line_cost_total_new": item_b.get("line_cost_total"),
            "margin_percent_old": item_a.get("margin_percent"),
            "margin_percent_new": item_b.get("margin_percent"),
            "field_changes": field_diffs
        }

        if field_diffs:
            modified.append(entry)
        else:
            unchanged.append(entry)

    # Sort line item categories deterministically by section, sort_order, catalog_item_id, description
    def _sort_key(it):
        return (
            it.get("section") or "",
            it.get("catalog_item_id") or 0,
            it.get("part_number") or "",
            it.get("description") or ""
        )

    added.sort(key=_sort_key)
    removed.sort(key=_sort_key)
    modified.sort(key=_sort_key)
    unchanged.sort(key=_sort_key)

    has_changes = bool(
        metadata_changes
        or requirement_changes
        or financial_changes
        or legal_entity_changes
        or added
        or removed
        or modified
    )

    base_summary = {
        "revision_number": base_rev.revision_number,
        "quote_version": base_rev.quote_version,
        "action": base_rev.action,
        "user_id": base_rev.user_id,
        "user_email": base_rev.user_email,
        "user_role": base_rev.user_role,
        "change_reason": base_rev.change_reason,
        "created_at": base_rev.created_at,
    }

    target_summary = {
        "revision_number": target_rev.revision_number,
        "quote_version": target_rev.quote_version,
        "action": target_rev.action,
        "user_id": target_rev.user_id,
        "user_email": target_rev.user_email,
        "user_role": target_rev.user_role,
        "change_reason": target_rev.change_reason,
        "created_at": target_rev.created_at,
    }

    quote_ref_no = base_rev.quote.quote_ref_no if base_rev.quote else snap_a.get("quote", {}).get("quote_ref_no", "")

    return {
        "quote_id": quote_id,
        "quote_ref_no": quote_ref_no,
        "base_revision": base_summary,
        "target_revision": target_summary,
        "has_changes": has_changes,
        "metadata_changes": metadata_changes,
        "requirement_changes": requirement_changes,
        "financial_changes": financial_changes,
        "legal_entity_changes": legal_entity_changes,
        "line_items": {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
            "total_added": len(added),
            "total_removed": len(removed),
            "total_modified": len(modified),
            "total_unchanged": len(unchanged),
        }
    }



