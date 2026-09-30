from pydantic import BaseModel, ConfigDict
from typing import Optional
from backend.app.models.user import RoleTier, AccountType

class UserBase(BaseModel):
    email: str
    role_tier: RoleTier
    enabled: bool

class UserResponse(UserBase):
    id: int
    account_type: AccountType

    model_config = ConfigDict(from_attributes=True)

class InviteUserRequest(BaseModel):
    email: str
    role_tier: RoleTier

class UpdateUserRoleRequest(BaseModel):
    role_tier: RoleTier

class UpdateUserStatusRequest(BaseModel):
    enabled: bool
