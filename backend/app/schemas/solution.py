from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from decimal import Decimal

class SolutionBase(BaseModel):
    name: str = Field(..., min_length=1)
    code: Optional[str] = None
    requirement_schema: Dict[str, Any] = Field(default_factory=dict)
    business_rules: Dict[str, Any] = Field(default_factory=dict)
    default_margin_percent: Decimal = Field(..., ge=0, le=100)

class SolutionCreate(SolutionBase):
    pass

class SolutionUpdate(SolutionBase):
    pass

class SolutionMarginUpdate(BaseModel):
    default_margin_percent: Decimal = Field(..., ge=0, le=100)

class SolutionResponse(SolutionBase):
    id: int
    default_margin_percent: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)
