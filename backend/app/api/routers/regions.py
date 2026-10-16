from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.region import Region
from backend.app.schemas.region import RegionResponse, RegionFXRateUpdate
from backend.app.api.deps import get_db, require_permission

router = APIRouter()

@router.get("", response_model=List[RegionResponse])
@router.get("/", response_model=List[RegionResponse])
def get_regions(db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    return db.execute(select(Region)).scalars().all()

@router.put("/{region_id}/fx-rate", response_model=RegionResponse)
def update_region_fx_rate(
    region_id: int,
    payload: RegionFXRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance_tax_admin"))
):
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    if region.currency_code.upper() != payload.currency_code.upper():
        raise HTTPException(
            status_code=400,
            detail=f"Currency mismatch: Region currency is {region.currency_code}, but payload specified {payload.currency_code}"
        )

    region.fx_rate_to_usd = payload.fx_rate_to_usd
    region.fx_rate_as_of = payload.fx_rate_as_of or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    db.commit()
    db.refresh(region)
    return region
