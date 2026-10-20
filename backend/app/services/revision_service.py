"""
Quote Revision Service
Handles deterministic serialization and creation of immutable quote revision snapshots.
"""
from typing import Optional, Any, Dict, List
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.quote import Quote, QuoteRevision, QuoteLineItem


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

