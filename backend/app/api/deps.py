from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.models.user import User, RoleTier
from backend.app.core.security import ALGORITHM

security = HTTPBearer()

ROLE_PERMISSIONS = {
    RoleTier.SALES: {"sales_user"},
    RoleTier.CATALOG_ENTRY: {"sales_user", "catalog_edit"},
    RoleTier.MANAGEMENT: {"sales_user", "catalog_edit", "cost_visibility", "finance_tax_admin"},
    RoleTier.ADMIN: {"sales_user", "catalog_edit", "cost_visibility", "finance_tax_admin", "solution_admin", "super_admin"}
}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject format")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    if not user.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        
    return user

def has_permission(required_permission: str, user: User) -> bool:
    permissions = ROLE_PERMISSIONS.get(user.role_tier, set())
    return required_permission in permissions

def require_permission(required_permission: str):
    def permission_checker(current_user: User = Depends(get_current_user)):
        if not has_permission(required_permission, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough permissions"
            )
        return current_user
    return permission_checker
