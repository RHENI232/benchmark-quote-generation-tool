from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import List, Optional
from decimal import Decimal, InvalidOperation
import openpyxl
from io import BytesIO

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.solution import Solution
from backend.app.models.catalog import CatalogItem, CatalogItemKind
from backend.app.api.deps import get_current_user, require_permission, get_db, has_permission
from backend.app.schemas.catalog import CatalogItemResponse, CatalogItemCreate, CatalogItemUpdate

router = APIRouter()

def mask_cost_price(item: CatalogItem, user: User) -> CatalogItemResponse:
    resp = CatalogItemResponse.model_validate(item)
    if not has_permission("cost_visibility", user):
        resp.cost_price = None
    return resp

@router.get("/", response_model=List[CatalogItemResponse])
def search_catalog(
    solution_id: int,
    q: Optional[str] = None,
    part_number: Optional[str] = None,
    description: Optional[str] = None,
    brand: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales_user"))
):
    query = select(CatalogItem).where(CatalogItem.solution_id == solution_id)
    
    if q:
        query = query.where(
            or_(
                CatalogItem.part_number.ilike(f"%{q}%"),
                CatalogItem.description.ilike(f"%{q}%"),
                CatalogItem.brand.ilike(f"%{q}%")
            )
        )
    
    if part_number:
        query = query.where(CatalogItem.part_number.ilike(f"%{part_number}%"))
    if description:
        query = query.where(CatalogItem.description.ilike(f"%{description}%"))
    if brand:
        query = query.where(CatalogItem.brand.ilike(f"%{brand}%"))
        
    items = db.execute(query).scalars().all()
    return [mask_cost_price(item, current_user) for item in items]

@router.get("/{item_id}", response_model=CatalogItemResponse)
def get_catalog_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    item = db.execute(select(CatalogItem).where(CatalogItem.id == item_id)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog Item not found")
    return mask_cost_price(item, current_user)

@router.post("/", response_model=CatalogItemResponse, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    item_in: CatalogItemCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_permission("catalog_edit"))
):
    solution = db.execute(select(Solution).where(Solution.id == item_in.solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        
    # Auto-calculate cost price if omitted and sell_price is present
    if item_in.cost_price is None and item_in.sell_price is not None:
        margin_factor = Decimal("1") - (solution.default_margin_percent / Decimal("100"))
        item_in.cost_price = item_in.sell_price * margin_factor

    import uuid
    dump_data = item_in.model_dump()
    dump_data["lookup_key"] = f"cat_usr_{uuid.uuid4().hex}"

    item = CatalogItem(**dump_data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return mask_cost_price(item, current_user)

@router.put("/{item_id}", response_model=CatalogItemResponse)
def update_catalog_item(
    item_id: int, 
    item_in: CatalogItemUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_permission("catalog_edit"))
):
    item = db.execute(select(CatalogItem).where(CatalogItem.id == item_id)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog Item not found")
        
    update_data = item_in.model_dump(exclude_unset=True)
    
    if item.kind == CatalogItemKind.RULE_DRIVEN:
        if "kind" in update_data and update_data["kind"] != CatalogItemKind.RULE_DRIVEN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change kind of RULE_DRIVEN items")
        if "part_number" in update_data and update_data["part_number"] != item.part_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change part_number of RULE_DRIVEN items")
            
    for key, value in update_data.items():
        setattr(item, key, value)
        
    db.commit()
    db.refresh(item)
    return mask_cost_price(item, current_user)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("catalog_edit"))):
    item = db.execute(select(CatalogItem).where(CatalogItem.id == item_id)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog Item not found")
        
    if item.kind == CatalogItemKind.RULE_DRIVEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Implementation safety rule derived from calculation-engine dependency: Deletion of RULE_DRIVEN items is globally blocked.")
        
    from backend.app.models.quote import QuoteLineItem
    is_referenced = db.execute(select(QuoteLineItem).where(QuoteLineItem.catalog_item_id == item_id)).first()
    if is_referenced:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete Catalog Item referenced by existing quotes")
        
    db.delete(item)
    db.commit()

@router.post("/import")
def import_catalog(
    solution_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_permission("catalog_edit"))
):
    solution = db.execute(select(Solution).where(Solution.id == solution_id)).scalar_one_or_none()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
        
    try:
        contents = file.file.read()
        wb = openpyxl.load_workbook(filename=BytesIO(contents), data_only=True)
        ws = wb.active
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Excel file format")
        
    headers = [cell.value for cell in ws[1]] if ws.max_row > 0 else []
    
    # Map headers to indices
    header_map = {str(h).strip().lower(): idx for idx, h in enumerate(headers) if h}
    
    required_cols = ["description"]
    for col in required_cols:
        if col not in header_map:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing required column: {col}")
            
    errors = []
    
    margin_factor = Decimal("1") - (solution.default_margin_percent / Decimal("100"))

    # Begin nested transaction block so we can rollback everything on error
    try:
        with db.begin_nested():
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                row_errors = []
                
                # Extract values
                def get_val(col_name):
                    idx = header_map.get(col_name)
                    return row[idx] if idx is not None and idx < len(row) else None
                    
                raw_id = get_val("id")
                raw_part = get_val("part number") or get_val("part_number")
                raw_desc = get_val("description")
                raw_brand = get_val("brand")
                raw_sell = get_val("sell price") or get_val("sell_price")
                raw_cost = get_val("cost price") or get_val("cost_price")
                
                if not raw_desc or not str(raw_desc).strip():
                    row_errors.append("Description is required")
                else:
                    desc_str = str(raw_desc).strip()

                def parse_decimal(val, field_name):
                    if val is None or str(val).strip() == "":
                        return None
                    try:
                        dec = Decimal(str(val))
                        if dec < 0:
                            row_errors.append(f"{field_name} must be positive")
                        return dec
                    except InvalidOperation:
                        row_errors.append(f"Invalid decimal format for {field_name}")
                        return None
                        
                sell_price = parse_decimal(raw_sell, "Sell Price")
                cost_price = parse_decimal(raw_cost, "Cost Price")
                
                part_number = str(raw_part).strip() if raw_part else None
                brand = str(raw_brand).strip() if raw_brand else None
                
                item_id = None
                if raw_id:
                    try:
                        item_id = int(raw_id)
                    except ValueError:
                        row_errors.append("ID must be an integer")
                        
                if row_errors:
                    errors.append({"row": row_idx, "errors": row_errors})
                    continue
                    
                # DB Operations
                if item_id:
                    # Update
                    item = db.execute(select(CatalogItem).where(CatalogItem.id == item_id)).scalar_one_or_none()
                    if not item:
                        row_errors.append(f"CatalogItem with ID {item_id} not found")
                        errors.append({"row": row_idx, "errors": row_errors})
                        continue
                        
                    if item.solution_id != solution_id:
                        row_errors.append(f"CatalogItem with ID {item_id} belongs to a different solution")
                        errors.append({"row": row_idx, "errors": row_errors})
                        continue

                    if item.kind == CatalogItemKind.RULE_DRIVEN:
                        if part_number is not None and part_number != item.part_number:
                            row_errors.append("Cannot modify Part Number of RULE_DRIVEN item")
                    else:
                        item.part_number = part_number
                        
                    if row_errors:
                        errors.append({"row": row_idx, "errors": row_errors})
                        continue
                        
                    item.description = desc_str
                    item.brand = brand
                    if raw_sell is not None:
                        item.sell_price = sell_price
                    if raw_cost is not None:
                        item.cost_price = cost_price
                        
                else:
                    # Create
                    if cost_price is None and sell_price is not None:
                        cost_price = sell_price * margin_factor
                        
                    import uuid
                    new_item = CatalogItem(
                        solution_id=solution_id,
                        lookup_key=f"cat_usr_{uuid.uuid4().hex}",
                        kind=CatalogItemKind.REFERENCE,
                        part_number=part_number,
                        description=desc_str,
                        brand=brand,
                        sell_price=sell_price,
                        cost_price=cost_price
                    )
                    db.add(new_item)
            
            if errors:
                raise ValueError("Validation failed")
                
        db.commit()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Import failed")
        
    return {"message": "Import successful"}
