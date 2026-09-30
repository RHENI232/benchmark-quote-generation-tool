from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any
from decimal import Decimal
from backend.app.models.catalog import CatalogItemKind

class CatalogItemBase(BaseModel):
    solution_id: int
    kind: CatalogItemKind
    part_number: Optional[str] = None
    description: str = Field(..., min_length=1)
    brand: Optional[str] = None
    sell_price: Optional[Decimal] = Field(None, ge=0)
    # cost_price omitted from base so it's not accidentally serialized

class CatalogItemCreate(CatalogItemBase):
    cost_price: Optional[Decimal] = Field(None, ge=0)

class CatalogItemUpdate(BaseModel):
    # Kind cannot be changed if rule_driven
    # Part number cannot be changed if rule_driven
    kind: Optional[CatalogItemKind] = None
    part_number: Optional[str] = None
    description: Optional[str] = Field(None, min_length=1)
    brand: Optional[str] = None
    sell_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)

class CatalogItemResponse(CatalogItemBase):
    id: int
    lookup_key: str
    cost_price: Optional[Decimal] = Field(None)
    
    model_config = ConfigDict(from_attributes=True)

class CatalogImportResetConfirm(BaseModel):
    confirm_reset: bool
