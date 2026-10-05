from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
import logging

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.quote import Quote, QuoteStatus
from backend.app.models.user import User, RoleTier
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.schemas.quote import QuoteCreate, QuoteResponse, QuoteUpdateHeaders, QuoteSaveAction, QuoteDeleteAction, QuoteRecalculate, QuoteSummary
from backend.app.schemas.requirement import RequirementPayload
from backend.app.services.engines.requirement_engine import parse_and_evaluate_requirements, RequirementEngineError
from backend.app.services.engines.pricing_engine import PricingEngine, PricingEngineError
from backend.app.services.export_service import generate_customer_copy, generate_internal_copy, generate_tracking_sheet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quotes")

def mask_quote_financials_for_sales(quote_data: dict, current_user: User) -> dict:
    if current_user.role_tier == RoleTier.SALES:
        quote_data["subtotal_cost_usd"] = None
        for item in quote_data.get("line_items", []):
            item["unit_cost_price_snapshot"] = None
            item["line_cost_total"] = None
            item["margin_percent"] = None
    return quote_data

@router.get("", response_model=List[QuoteSummary])
def list_quotes(
    skip: int = 0,
    limit: int = 50,
    client_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if limit > 100:
        limit = 100

    query = db.query(Quote).filter(Quote.deleted_at.is_(None), Quote.status == QuoteStatus.SAVED)

    if current_user.role_tier == RoleTier.SALES:
        query = query.filter(Quote.created_by_user_id == current_user.id)

    if client_name:
        query = query.filter(Quote.client_name.ilike(f"%{client_name}%"))

    quotes = query.order_by(Quote.created_at.desc()).offset(skip).limit(limit).all()
    return quotes

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

@router.get("/{quote_id}/export/customer")
def export_customer_copy(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    buf = generate_customer_copy(quote)
    filename = f"{quote.quote_ref_no}_Customer_Copy.xlsx"
    return StreamingResponse(
        buf,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{quote_id}/export/internal")
def export_internal_copy(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role_tier in (RoleTier.SALES, RoleTier.CATALOG_ENTRY):
        raise HTTPException(status_code=403, detail="Forbidden: Insufficient permissions")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    buf = generate_internal_copy(quote)
    filename = f"{quote.quote_ref_no}_Internal.xlsx"
    return StreamingResponse(
        buf,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{quote_id}/export/tracking")
def export_tracking_sheet(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role_tier in (RoleTier.SALES, RoleTier.CATALOG_ENTRY):
        raise HTTPException(status_code=403, detail="Forbidden: Insufficient permissions")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    buf = generate_tracking_sheet(quote)
    filename = f"{quote.quote_ref_no}_Tracking.xlsx"
    return StreamingResponse(
        buf,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/preview", response_model=QuoteResponse)
def preview_quote(payload: QuoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        region = db.query(Region).filter(Region.id == payload.region_id).first()
        solution = db.query(Solution).filter(Solution.id == payload.solution_id).first()
        if not region or not solution:
            raise HTTPException(status_code=404, detail="Region or Solution not found.")

        req_payload = RequirementPayload(**payload.requirement_data)
        bom = parse_and_evaluate_requirements(solution, payload.requirement_data)

        quote = Quote(
            solution_id=payload.solution_id,
            region_id=payload.region_id,
            client_name=payload.client_name,
            attention=payload.attention,
            description=payload.description,
            created_by_user_id=current_user.id,
            last_edited_by_user_id=current_user.id,
            quote_ref_no="PREVIEW"
        )
        db.add(quote)
        db.flush()

        quote.region = region
        quote.solution = solution

        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)
        db.flush()

        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        db.rollback()
        return mask_quote_financials_for_sales(resp, current_user)

    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error previewing quote: {e}")
        raise HTTPException(status_code=400, detail="Error generating quote preview.")

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        region = db.query(Region).filter(
            Region.id == payload.region_id
        ).first()

        solution = db.query(Solution).filter(
            Solution.id == payload.solution_id
        ).first()

        if not region or not solution:
            raise HTTPException(
                status_code=404,
                detail="Region or Solution not found."
            )

        req_payload = RequirementPayload(**payload.requirement_data)

        bom = parse_and_evaluate_requirements(
            solution,
            payload.requirement_data
        )

        seq_val = db.execute(
            text("SELECT nextval('quote_ref_seq')")
        ).scalar()

        current_year = datetime.utcnow().year
        quote_ref_no = f"BBS-{current_year}-{seq_val:06d}"

        quote = Quote(
            solution_id=payload.solution_id,
            region_id=payload.region_id,
            client_name=payload.client_name,
            attention=payload.attention,
            description=payload.description,
            created_by_user_id=current_user.id,
            last_edited_by_user_id=current_user.id,
            quote_ref_no=quote_ref_no,
            version=0,
            status=QuoteStatus.DRAFT
        )

        db.add(quote)
        db.flush()

        quote.region = region
        quote.solution = solution

        PricingEngine.calculate_and_save_quote(
            db,
            quote,
            req_payload,
            bom
        )

        db.commit()
        db.refresh(quote)

        resp = QuoteResponse.model_validate(
            quote,
            from_attributes=True
        ).model_dump()

        return mask_quote_financials_for_sales(
            resp,
            current_user
        )

    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )

    except IntegrityError as e:
        db.rollback()
        orig = getattr(e, "orig", None)
        diag = getattr(orig, "diag", None)
        logger.error(f"INTEGRITY ERROR: {repr(e)}")
        logger.error(f"ORIGINAL: {repr(orig)}")
        logger.error(f"DETAIL: {diag}")

        detail_msg = "Database integrity error. Quote reference collision possible."
        if diag:
            detail_msg = f"Constraint: {getattr(diag, 'constraint_name', None)}, Msg: {getattr(diag, 'message_primary', None)}"

        raise HTTPException(
            status_code=409,
            detail=detail_msg
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating quote: {e}")
        raise HTTPException(
            status_code=400,
            detail="Error generating quote."
        )

@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")

    resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
    return mask_quote_financials_for_sales(resp, current_user)

@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(quote_id: int, payload: QuoteUpdateHeaders, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only DRAFT quotes can be edited")

    if payload.expected_version != quote.version:
        raise HTTPException(status_code=409, detail="Version mismatch (optimistic concurrency)")

    if payload.client_name is not None:
        quote.client_name = payload.client_name
    if payload.attention is not None:
        quote.attention = payload.attention
    if payload.description is not None:
        quote.description = payload.description

    quote.last_edited_by_user_id = current_user.id
    quote.version += 1
    db.commit()
    db.refresh(quote)

    resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
    return mask_quote_financials_for_sales(resp, current_user)

@router.post("/{quote_id}/recalculate", response_model=QuoteResponse)
def recalculate_quote(quote_id: int, payload: QuoteRecalculate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only DRAFT quotes can be recalculated")

    if payload.expected_version != quote.version:
        raise HTTPException(status_code=409, detail="Version mismatch")

    try:
        req_payload = RequirementPayload(**payload.requirement_data)
        bom = parse_and_evaluate_requirements(quote.solution, payload.requirement_data)
        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)

        quote.last_edited_by_user_id = current_user.id
        db.commit()
        db.refresh(quote)

        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials_for_sales(resp, current_user)
    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error recalculating")

@router.post("/{quote_id}/save", response_model=QuoteResponse)
def save_quote(quote_id: int, payload: QuoteSaveAction, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if payload.expected_version != quote.version:
        raise HTTPException(status_code=409, detail="Version mismatch")

    quote.status = QuoteStatus.SAVED
    quote.version += 1
    quote.last_edited_by_user_id = current_user.id
    db.commit()
    db.refresh(quote)

    resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
    return mask_quote_financials_for_sales(resp, current_user)

@router.delete("/{quote_id}", response_model=dict)
def delete_quote(quote_id: int, expected_version: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if expected_version != quote.version:
        raise HTTPException(status_code=409, detail="Version mismatch")

    quote.deleted_at = datetime.utcnow()
    quote.last_edited_by_user_id = current_user.id
    quote.version += 1
    db.commit()

    return {"status": "deleted"}
