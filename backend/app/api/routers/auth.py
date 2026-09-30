from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from backend.app.api.deps import get_db
from backend.app.models.user import User, AccountType
from backend.app.models.invite import InviteToken, TokenType
from backend.app.schemas.auth import LoginRequest, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest, AcceptInviteRequest, MessageResponse
from backend.app.core.security import verify_password, get_password_hash, create_access_token, generate_raw_token, hash_token
from backend.app.core.config import settings

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    
    # Generic error logic
    generic_err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    if not user:
        raise generic_err
    if not user.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    if user.account_type != AccountType.MANUAL:
        raise generic_err
    if not user.password_hash:
        raise generic_err
        
    if not verify_password(request.password, user.password_hash):
        raise generic_err
        
    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)

@router.post("/password/forgot", response_model=MessageResponse)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    
    raw_token = None
    if user and user.enabled and user.account_type == AccountType.MANUAL:
        raw_token = generate_raw_token()
        hashed_token = hash_token(raw_token)
        
        invite = InviteToken(
            user_id=user.id,
            token_hash=hashed_token,
            token_type=TokenType.RESET,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        )
        db.add(invite)
        db.commit()
    
    # Anti-enumeration
    response_msg = "If your email is registered, you will receive a reset link shortly."
    if settings.ENVIRONMENT == "development" and raw_token:
        return MessageResponse(message=response_msg, token=raw_token)
    return MessageResponse(message=response_msg)

@router.post("/password/reset", response_model=MessageResponse)
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    hashed_token = hash_token(request.token)
    invite = db.query(InviteToken).filter(
        InviteToken.token_hash == hashed_token,
        InviteToken.token_type == TokenType.RESET,
        InviteToken.used_at == None
    ).first()
    
    if not invite or invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
        
    user = db.query(User).filter(User.id == invite.user_id).first()
    if not user or not user.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user")
        
    user.password_hash = get_password_hash(request.new_password)
    invite.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    
    return MessageResponse(message="Password reset successfully")

@router.post("/invite/accept", response_model=MessageResponse)
def accept_invite(request: AcceptInviteRequest, db: Session = Depends(get_db)):
    hashed_token = hash_token(request.token)
    invite = db.query(InviteToken).filter(
        InviteToken.token_hash == hashed_token,
        InviteToken.token_type == TokenType.INVITE,
        InviteToken.used_at == None
    ).first()
    
    if not invite or invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invitation token")
        
    user = db.query(User).filter(User.id == invite.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user")
        
    user.password_hash = get_password_hash(request.new_password)
    user.enabled = True
    invite.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    
    return MessageResponse(message="Account activated successfully")
