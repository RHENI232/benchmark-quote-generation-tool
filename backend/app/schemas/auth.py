from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

class MessageResponse(BaseModel):
    message: str
    # token is only populated in development environments
    token: Optional[str] = None
