from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from datetime import datetime, timezone, timedelta
from backend.app.api.deps import get_db, require_permission, get_current_user
from backend.app.models.user import User, RoleTier, AccountType
from backend.app.models.invite import InviteToken, TokenType
from backend.app.models.quote import Quote
from backend.app.schemas.user import UserResponse, InviteUserRequest, UpdateUserRoleRequest, UpdateUserStatusRequest
from backend.app.schemas.auth import MessageResponse
from backend.app.core.security import generate_raw_token, hash_token
from backend.app.core.config import settings

router = APIRouter()

def check_admin_invariant(db: Session, msg="Cannot remove the last enabled Admin account"):
    admin_count = db.execute(
        select(func.count())
        .select_from(User)
        .filter(User.role_tier == RoleTier.ADMIN, User.enabled == True)
    ).scalar()
    if admin_count == 0:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

def lock_admins_if_needed(db: Session, user_id: int):
    """
    To prevent concurrent race conditions where two admins disable each other,
    we must lock all admin rows BEFORE locking the target user.
    This serializes any transaction that attempts to modify an existing enabled admin.
    """
    user_info = db.query(User.role_tier, User.enabled).filter(User.id == user_id).first()
    if user_info and user_info.role_tier == RoleTier.ADMIN and user_info.enabled:
        # Lock all enabled admins in a consistent order (by id) to avoid deadlocks
        db.execute(
            select(User.id)
            .filter(User.role_tier == RoleTier.ADMIN, User.enabled == True)
            .order_by(User.id)
            .with_for_update()
        ).fetchall()

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_permission("super_admin"))
):
    return db.query(User).all()

@router.post("/invite", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
def invite_user(
    request: InviteUserRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("super_admin"))
):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        
    user = User(
        email=request.email,
        role_tier=request.role_tier,
        account_type=AccountType.MANUAL,
        enabled=False,
        password_hash=None
    )
    db.add(user)
    db.flush()
    
    raw_token = generate_raw_token()
    invite = InviteToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        token_type=TokenType.INVITE,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=72)
    )
    db.add(invite)
    db.commit()
    
    msg = "Invitation created."
    if settings.ENVIRONMENT == "development":
        return MessageResponse(message=msg, token=raw_token)
    return MessageResponse(message=msg)

@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    request: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("super_admin"))
):
    lock_admins_if_needed(db, user_id)
    user = db.execute(select(User).filter(User.id == user_id).with_for_update()).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    user.role_tier = request.role_tier
    db.flush()
    check_admin_invariant(db)
    db.commit()
    return user

@router.put("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("super_admin"))
):
    lock_admins_if_needed(db, user_id)
    user = db.execute(select(User).filter(User.id == user_id).with_for_update()).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    user.enabled = request.enabled
    db.flush()
    check_admin_invariant(db)
    db.commit()
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("super_admin"))
):
    lock_admins_if_needed(db, user_id)
    user = db.execute(select(User).filter(User.id == user_id).with_for_update()).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    # Check quote references
    has_quotes = db.query(Quote).filter(
        (Quote.created_by_user_id == user_id) | (Quote.last_edited_by_user_id == user_id)
    ).first()
    
    if has_quotes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User has quote history and cannot be deleted. Please disable the account instead."
        )
        
    # Also delete invite tokens to satisfy foreign key constraints before deleting user
    db.query(InviteToken).filter(InviteToken.user_id == user_id).delete()
    
    db.delete(user)
    db.flush()
    check_admin_invariant(db)
    db.commit()
    return None
