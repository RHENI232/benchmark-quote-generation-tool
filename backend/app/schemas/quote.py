from pydantic import BaseModel, ConfigDict, PlainSerializer, Field, field_validator
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
    change_reason: Optional[str] = Field(None, max_length=1000, description="Optional reason explaining why the quote was recalculated.")

    @field_validator("change_reason")
    @classmethod
    def validate_change_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) > 1000:
                raise ValueError("change_reason cannot exceed 1000 characters.")
        return v

class QuoteUpdate(QuoteCreate):
    expected_version: int
    change_reason: Optional[str] = Field(None, max_length=1000, description="Optional reason explaining why the quote was edited.")

    @field_validator("change_reason")
    @classmethod
    def validate_change_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) > 1000:
                raise ValueError("change_reason cannot exceed 1000 characters.")
        return v

class QuoteSubmitAction(BaseModel):
    expected_version: int
    comment: Optional[str] = None

class QuoteApproveAction(BaseModel):
    expected_version: int
    comment: Optional[str] = None

class QuoteRequestChangesAction(BaseModel):
    expected_version: int
    comment: str

class QuoteOverrideApproveAction(BaseModel):
    expected_version: int
    comment: str

class QuoteUrgentAction(BaseModel):
    expected_version: int
    is_urgent: bool
    comment: Optional[str] = None

class QuoteDeleteAction(BaseModel):
    expected_version: int

class QuoteRefreshFXAction(BaseModel):
    expected_version: int
    comment: Optional[str] = None

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

class QuoteApprovalLogResponse(BaseModel):
    id: int
    quote_id: int
    quote_version: int
    action: str
    from_status: QuoteStatus
    to_status: QuoteStatus
    user_id: int
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuoteRevisionResponse(BaseModel):
    id: int
    quote_id: int
    revision_number: int
    quote_version: int
    action: str
    user_id: int
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: datetime
    snapshot_data: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)

class RevisionSummary(BaseModel):
    revision_number: int
    quote_version: int
    action: str
    user_id: int
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    change_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FieldDifference(BaseModel):
    old: Any = None
    new: Any = None
    changed: bool = False

class LineItemDifference(BaseModel):
    catalog_item_id: Optional[int] = None
    part_number: Optional[str] = None
    brand: Optional[str] = None
    description: str
    section: Optional[str] = None
    status: str  # "added", "removed", "modified", "unchanged"
    quantity_old: Optional[int] = None
    quantity_new: Optional[int] = None
    unit_sell_price_old: Optional[str] = None
    unit_sell_price_new: Optional[str] = None
    line_sell_total_old: Optional[str] = None
    line_sell_total_new: Optional[str] = None
    unit_cost_price_old: Optional[str] = None
    unit_cost_price_new: Optional[str] = None
    line_cost_total_old: Optional[str] = None
    line_cost_total_new: Optional[str] = None
    margin_percent_old: Optional[str] = None
    margin_percent_new: Optional[str] = None
    field_changes: Dict[str, Dict[str, Any]] = {}

class LineItemsComparison(BaseModel):
    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    modified: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0
    total_unchanged: int = 0

class QuoteRevisionComparisonResponse(BaseModel):
    quote_id: int
    quote_ref_no: str
    base_revision: RevisionSummary
    target_revision: RevisionSummary
    has_changes: bool
    metadata_changes: Dict[str, Dict[str, Any]] = {}
    requirement_changes: Dict[str, Dict[str, Any]] = {}
    financial_changes: Dict[str, Dict[str, Any]] = {}
    legal_entity_changes: Dict[str, Dict[str, Any]] = {}
    line_items: LineItemsComparison


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
    is_urgent: bool = False
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
    approval_logs: List[QuoteApprovalLogResponse] = []

    model_config = ConfigDict(from_attributes=True)

class QuoteSummary(BaseModel):
    id: int
    quote_ref_no: str
    client_name: str
    region_id: int
    created_at: datetime
    date: datetime
    status: QuoteStatus
    version: int
    created_by_user_id: int

    model_config = ConfigDict(from_attributes=True)

class QuoteQueueItem(QuoteSummary):
    is_urgent: bool
    total_sell_local: DecimalStr
    subtotal_cost_usd: Optional[DecimalStr] = None
    currency_code: str
