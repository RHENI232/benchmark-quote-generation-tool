from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.models.quote import Quote, QuoteLineItem, QuoteStatus
from backend.app.models.catalog import CatalogItem
from backend.app.schemas.bom import BOMLineSpec
from backend.app.schemas.requirement import RequirementPayload
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class PricingEngineError(Exception):
    pass

class PricingEngine:
    @staticmethod
    def calculate_and_save_quote(db: Session, quote: Quote, payload: RequirementPayload, bom: List[BOMLineSpec]) -> Quote:
        """
        Consumes the RequirementPayload and abstract BOMLineSpec list, 
        fetches actual catalog pricing using lookup_key, computes financials, 
        and updates the Quote.
        """
        if quote.status == QuoteStatus.SAVED:
            raise PricingEngineError("Cannot recalculate a SAVED quote. It is immutable.")

        region = quote.region
        if not region:
            raise PricingEngineError("Quote has no associated region.")

        # FX Validation
        fx_rate = Decimal("1.000000")
        currency_code = "USD"
        if region.currency_code and region.currency_code.upper() != "USD":
            currency_code = region.currency_code.upper()
            if not region.fx_rate_to_usd or region.fx_rate_to_usd <= 0:
                raise PricingEngineError(f"Cannot calculate quote: Region '{region.country_name}' requires a valid positive fx_rate_to_usd.")
            fx_rate = Decimal(str(region.fx_rate_to_usd))

        # Clear existing line items since this is a full recalculation
        for item in list(quote.line_items):
            db.delete(item)
        quote.line_items.clear()
        db.flush()

        # Fetch catalog items efficiently
        lookup_keys = [b.lookup_key for b in bom]
        catalog_items_map = {}
        if lookup_keys:
            items = db.query(CatalogItem).filter(CatalogItem.lookup_key.in_(lookup_keys)).all()
            catalog_items_map = {item.lookup_key: item for item in items}

        wtvision_support_basis = Decimal("0.0")
        subtotal_sell_usd = Decimal("0.0")
        subtotal_cost_usd = Decimal("0.0")

        line_index = 0

        # Process standard BOM lines
        for bom_line in bom:
            catalog_item = catalog_items_map.get(bom_line.lookup_key)
            if not catalog_item:
                raise PricingEngineError(f"Catalog item with lookup_key '{bom_line.lookup_key}' not found.")

            # Missing prices are treated as $0.00
            unit_sell = Decimal(str(catalog_item.sell_price)) if catalog_item.sell_price is not None else Decimal("0.0")
            unit_cost = Decimal(str(catalog_item.cost_price)) if catalog_item.cost_price is not None else Decimal("0.0")
            qty = Decimal(str(bom_line.quantity))

            line_sell_total = unit_sell * qty
            line_cost_total = unit_cost * qty
            
            # Guarded margin %
            margin_percent = Decimal("0.0")
            if unit_sell > Decimal("0.0"):
                margin_percent = ((unit_sell - unit_cost) / unit_sell) * Decimal("100.0")

            line_item = QuoteLineItem(
                quote_id=quote.id,
                catalog_item_id=catalog_item.id,
                part_number=catalog_item.part_number,
                description=catalog_item.description,
                brand=catalog_item.brand,
                section=bom_line.section,
                sort_order=line_index,
                quantity=bom_line.quantity, # keep DB quantity as integer or Decimal, using int is fine but line total used decimal
                unit_sell_price_snapshot=unit_sell,
                unit_cost_price_snapshot=unit_cost,
                line_sell_total=line_sell_total,
                line_cost_total=line_cost_total,
                margin_percent=margin_percent
            )
            db.add(line_item)
            quote.line_items.append(line_item)
            line_index += 1

            subtotal_sell_usd += line_sell_total
            subtotal_cost_usd += line_cost_total

            if catalog_item.brand == "wTVision":
                wtvision_support_basis += line_sell_total

        # Process Section 4.9: Support (Calculated last)
        if payload.three_years_support:
            support_price = wtvision_support_basis * Decimal("0.30")
            
            # 0% margin exception
            support_line = QuoteLineItem(
                quote_id=quote.id,
                catalog_item_id=None,
                part_number=None,
                description="First 3 Years Support - Standard",
                brand=None,
                section="Support",
                sort_order=line_index,
                quantity=1,
                unit_sell_price_snapshot=support_price,
                unit_cost_price_snapshot=support_price,
                line_sell_total=support_price,
                line_cost_total=support_price,
                margin_percent=Decimal("0.0")
            )
            db.add(support_line)
            quote.line_items.append(support_line)
            line_index += 1

            subtotal_sell_usd += support_price
            subtotal_cost_usd += support_price

        # FX and Tax Application
        total_sell_local = subtotal_sell_usd * fx_rate
        
        tax_enabled = region.tax_enabled
        tax_rate = Decimal(str(region.tax_rate_percent)) if region.tax_rate_percent is not None else Decimal("0.0")
        tax_amount = Decimal("0.0")
        
        if tax_enabled:
            tax_amount = total_sell_local * (tax_rate / Decimal("100.0"))

        # Update Quote snapshots and totals
        quote.currency_code = currency_code
        quote.fx_rate_to_usd = fx_rate
        quote.fx_rate_as_of = region.fx_rate_as_of
        quote.tax_enabled = tax_enabled
        quote.tax_rate_percent = tax_rate
        
        quote.legal_entity_name = region.legal_entity_name
        quote.legal_entity_registration_number = region.legal_entity_registration_number
        quote.legal_entity_address = region.legal_entity_address
        quote.legal_entity_contact = region.legal_entity_contact

        quote.subtotal_sell_usd = subtotal_sell_usd
        quote.subtotal_cost_usd = subtotal_cost_usd
        quote.tax_amount = tax_amount
        quote.total_sell_local = total_sell_local
        
        quote.requirement_data = payload.model_dump()
        
        # Increment version on recalculation
        if quote.version is None:
            quote.version = 1
        else:
            quote.version += 1

        db.flush()
        return quote
