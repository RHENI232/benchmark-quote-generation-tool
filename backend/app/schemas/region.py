from pydantic import BaseModel, Field, ConfigDict, field_validator
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

class RegionFXRateUpdate(BaseModel):
    fx_rate_to_usd: Decimal = Field(..., gt=0, description="USD value of 1 unit of local currency. Must be > 0.")
    currency_code: str = Field(..., min_length=3, max_length=5, description="Currency code matching the region.")
    fx_rate_as_of: Optional[str] = Field(None, description="ISO-8601 or date string for effective rate date.")
    notes: Optional[str] = Field(None, max_length=255, description="Optional administrative notes.")

    @field_validator("fx_rate_to_usd")
    @classmethod
    def validate_fx_rate(cls, v: Decimal) -> Decimal:
        if v.is_nan() or v.is_infinite() or v <= 0:
            raise ValueError("FX rate must be a finite, positive number greater than 0.")
        return v
