from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from decimal import Decimal

class RegionBase(BaseModel):
    country_name: str
    currency_code: str
    legal_entity_name: Optional[str] = None
    legal_entity_registration_number: Optional[str] = None
    legal_entity_address: Optional[str] = None
    legal_entity_contact: Optional[str] = None

    tax_enabled: bool = False
    tax_rate_percent: Optional[Decimal] = None

    fx_rate_to_usd: Optional[Decimal] = None
    fx_rate_as_of: Optional[str] = None

class RegionResponse(RegionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
