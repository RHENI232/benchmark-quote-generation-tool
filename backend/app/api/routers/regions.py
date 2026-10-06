from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.region import Region
from backend.app.schemas.region import RegionResponse
from backend.app.api.deps import get_db, require_permission

router = APIRouter()

@router.get("/", response_model=List[RegionResponse])
def get_regions(db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    return db.execute(select(Region)).scalars().all()
