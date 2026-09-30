from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.solution import Solution
from backend.app.models.catalog import CatalogItem
from backend.app.api.deps import get_current_user, require_permission, get_db
from backend.app.schemas.solution import SolutionResponse, SolutionCreate, SolutionUpdate, SolutionMarginUpdate
from backend.seed import DEFAULT_CATALOG_DATA
from backend.app.schemas.catalog import CatalogImportResetConfirm

router = APIRouter()

@router.get("/", response_model=List[SolutionResponse])
def get_solutions(db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    return db.execute(select(Solution)).scalars().all()

@router.get("/{solution_id}", response_model=SolutionResponse)
def get_solution(solution_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    solution = db.execute(select(Solution).where(Solution.id == solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution

@router.post("/", response_model=SolutionResponse, status_code=status.HTTP_201_CREATED)
def create_solution(solution_in: SolutionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("solution_admin"))):
    existing = db.execute(select(Solution).where(Solution.name == solution_in.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solution with this name already exists")
    
    solution = Solution(**solution_in.model_dump())
    db.add(solution)
    db.commit()
    db.refresh(solution)
    return solution

@router.put("/{solution_id}", response_model=SolutionResponse)
def update_solution(solution_id: int, solution_in: SolutionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("solution_admin"))):
    solution = db.execute(select(Solution).where(Solution.id == solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        
    for key, value in solution_in.model_dump().items():
        setattr(solution, key, value)
    
    db.commit()
    db.refresh(solution)
    return solution

@router.patch("/{solution_id}/margin", response_model=SolutionResponse)
def update_solution_margin(solution_id: int, margin_in: SolutionMarginUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("catalog_edit"))):
    solution = db.execute(select(Solution).where(Solution.id == solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        
    solution.default_margin_percent = margin_in.default_margin_percent
    db.commit()
    db.refresh(solution)
    return solution

@router.post("/{solution_id}/catalog/reset", response_model=dict)
def reset_catalog_to_defaults(
    solution_id: int,
    confirm: CatalogImportResetConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("catalog_edit"))
):
    if not confirm.confirm_reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must confirm reset")
        
    solution = db.execute(select(Solution).where(Solution.id == solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        
    if solution.name != "WTVision Graphics":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shipped catalog defaults are not defined for this Solution.")
    
    # Run idempotent UPSERT of DEFAULT_CATALOG_DATA
    for item_data in DEFAULT_CATALOG_DATA:
        item = db.execute(
            select(CatalogItem).where(
                CatalogItem.lookup_key == item_data["lookup_key"]
            )
        ).scalars().first()

        if not item:
            item = CatalogItem(solution_id=solution.id, **item_data)
            db.add(item)
        else:
            for key, value in item_data.items():
                setattr(item, key, value)

    db.commit()
    return {"message": "Catalog reset to defaults successfully"}
