from pydantic import BaseModel, ConfigDict, PlainSerializer
from typing_extensions import Annotated
from typing import Optional, Dict, List, Any
from datetime import datetime
from decimal import Decimal
from backend.app.models.quote import QuoteStatus

DecimalStr = Annotated[Decimal, PlainSerializer(lambda x: str(x), return_type=str, when_used='json')]

class QuoteBase(BaseModel):
    client_name: str
    attention: Optional[str] = None
    description: Optional[str] = None

class QuoteCreate(QuoteBase):
    solution_id: int
    region_id: int
    requirement_data: Dict[str, Any]

class QuoteRecalculate(BaseModel):
    requirement_data: Dict[str, Any]
    expected_version: int

class QuoteUpdateHeaders(QuoteBase):
    client_name: Optional[str] = None
    expected_version: int

class QuoteSaveAction(BaseModel):
    expected_version: int

class QuoteDeleteAction(BaseModel):
    expected_version: int

class QuoteLineItemResponse(BaseModel):
    id: int
    quote_id: int
    catalog_item_id: Optional[int] = None
    part_number: Optional[str] = None
    description: str
    brand: Optional[str] = None
    section: Optional[str] = None
    sort_order: int
    quantity: int
    
    # Financial snapshots
    unit_sell_price_snapshot: DecimalStr
    unit_cost_price_snapshot: Optional[DecimalStr] = None
    line_sell_total: DecimalStr
    line_cost_total: Optional[DecimalStr] = None
    margin_percent: Optional[DecimalStr] = None

    model_config = ConfigDict(from_attributes=True)

class QuoteResponse(QuoteBase):
    id: int
    solution_id: int
    region_id: int
    quote_ref_no: str
    date: datetime
    version: int
    requirement_data: Dict[str, Any]
    created_by_user_id: int
    last_edited_by_user_id: int
    created_at: datetime
    updated_at: datetime
    status: QuoteStatus
    currency_code: str
    
    fx_rate_to_usd: DecimalStr
    fx_rate_as_of: Optional[str] = None
    tax_enabled: bool
    tax_rate_percent: Optional[DecimalStr] = None
    
    subtotal_sell_usd: DecimalStr
    subtotal_cost_usd: Optional[DecimalStr] = None
    tax_amount: DecimalStr
    total_sell_local: DecimalStr
    
    legal_entity_name: Optional[str] = None
    legal_entity_registration_number: Optional[str] = None
    legal_entity_address: Optional[str] = None
    legal_entity_contact: Optional[str] = None

    line_items: List[QuoteLineItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

