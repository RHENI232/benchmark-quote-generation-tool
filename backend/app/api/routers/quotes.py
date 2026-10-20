from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import logging

from backend.app.api.deps import get_db, get_current_user, require_permission, has_permission
from backend.app.models.quote import Quote, QuoteStatus, QuoteApprovalLog
from backend.app.models.user import User, RoleTier
from backend.app.models.region import Region
from backend.app.models.solution import Solution
from backend.app.schemas.quote import (
    QuoteCreate, QuoteResponse, QuoteUpdate, QuoteDeleteAction, QuoteRecalculate, QuoteSummary,
    QuoteQueueItem, QuoteSubmitAction, QuoteApproveAction, QuoteRequestChangesAction, QuoteOverrideApproveAction,
    QuoteUrgentAction, QuoteApprovalLogResponse, QuoteRefreshFXAction, QuoteRevisionResponse,
    QuoteRevisionComparisonResponse
)
from backend.app.schemas.requirement import RequirementPayload
from backend.app.services.engines.requirement_engine import parse_and_evaluate_requirements, RequirementEngineError
from backend.app.services.engines.pricing_engine import PricingEngine, PricingEngineError
from backend.app.services.export_service import generate_customer_copy, generate_internal_copy, generate_tracking_sheet
from backend.app.services.pdf_service import generate_customer_pdf
from backend.app.services.revision_service import (
    create_quote_revision,
    get_quote_revisions,
    get_quote_revision_by_number,
    mask_revision_snapshot,
    compare_quote_revisions,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quotes")

def mask_quote_financials(quote_data: dict, current_user: User) -> dict:
    if not has_permission("cost_visibility", current_user):
        quote_data["subtotal_cost_usd"] = None
        for item in quote_data.get("line_items", []):
            item["unit_cost_price_snapshot"] = None
            item["line_cost_total"] = None
            item["margin_percent"] = None
    return quote_data

def _clean_reason(reason: Optional[str]) -> Optional[str]:
    if reason is None:
        return None
    cleaned = reason.strip()
    return cleaned if cleaned else None

@router.get("/approval-queue", response_model=List[QuoteQueueItem])
def get_approval_queue(db: Session = Depends(get_db), current_user: User = Depends(require_permission("finance_tax_admin"))):
    quotes = db.query(Quote).filter(
        Quote.deleted_at.is_(None),
        Quote.status == QuoteStatus.PENDING_APPROVAL
    ).order_by(
        Quote.is_urgent.desc(),
        Quote.updated_at.asc(),
        Quote.id.asc()
    ).all()
    
    res = []
    for q in quotes:
        qd = QuoteQueueItem.model_validate(q, from_attributes=True).model_dump()
        if not has_permission("cost_visibility", current_user):
            qd["subtotal_cost_usd"] = None
        res.append(qd)
    return res

@router.get("", response_model=List[QuoteSummary])
def list_quotes(
    skip: int = 0, limit: int = 50, client_name: Optional[str] = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))
):
    if limit > 100: limit = 100
    query = db.query(Quote).filter(Quote.deleted_at.is_(None))
    if current_user.role_tier == RoleTier.SALES:
        query = query.filter(Quote.created_by_user_id == current_user.id)
    if client_name:
        query = query.filter(Quote.client_name.ilike(f"%{client_name}%"))
    quotes = query.order_by(Quote.created_at.desc()).offset(skip).limit(limit).all()
    return quotes

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MEDIA_TYPE = "application/pdf"

@router.get("/{quote_id}/export/customer")
def export_customer_copy(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden")
    if quote.status != QuoteStatus.APPROVED: raise HTTPException(status_code=409, detail="Quote must be APPROVED before generating a customer copy.")
    buf = generate_customer_copy(quote)
    return StreamingResponse(buf, media_type=XLSX_MEDIA_TYPE, headers={"Content-Disposition": f'attachment; filename="{quote.quote_ref_no}_Customer_Copy.xlsx"'})

@router.get("/{quote_id}/export/customer-pdf")
def export_customer_pdf(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if quote.status != QuoteStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Quote must be APPROVED before generating a customer PDF.")
    buf = generate_customer_pdf(quote)
    return StreamingResponse(
        buf,
        media_type=PDF_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{quote.quote_ref_no}_Customer_Quote.pdf"'}
    )

@router.get("/{quote_id}/export/internal")
def export_internal_copy(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("cost_visibility"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
    buf = generate_internal_copy(quote)
    return StreamingResponse(buf, media_type=XLSX_MEDIA_TYPE, headers={"Content-Disposition": f'attachment; filename="{quote.quote_ref_no}_Internal.xlsx"'})

@router.get("/{quote_id}/export/tracking")
def export_tracking_sheet(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("cost_visibility"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
    buf = generate_tracking_sheet(quote)
    return StreamingResponse(buf, media_type=XLSX_MEDIA_TYPE, headers={"Content-Disposition": f'attachment; filename="{quote.quote_ref_no}_Tracking.xlsx"'})

@router.post("/preview", response_model=QuoteResponse)
def preview_quote(payload: QuoteCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    try:
        region = db.query(Region).filter(Region.id == payload.region_id).first()
        solution = db.query(Solution).filter(Solution.id == payload.solution_id).first()
        if not region or not solution: raise HTTPException(status_code=404, detail="Region or Solution not found.")
        bom = parse_and_evaluate_requirements(solution, payload.requirement_data)
        req_payload = RequirementPayload(**payload.requirement_data)
        quote = Quote(solution_id=payload.solution_id, region_id=payload.region_id, client_name=payload.client_name, attention=payload.attention, description=payload.description, created_by_user_id=current_user.id, last_edited_by_user_id=current_user.id, quote_ref_no="PREVIEW")
        db.add(quote)
        db.flush()
        quote.region = region; quote.solution = solution
        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)
        db.flush()
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        db.rollback()
        return mask_quote_financials(resp, current_user)
    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error previewing quote: {e}")
        raise HTTPException(status_code=400, detail="Error generating quote preview.")

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(payload: QuoteCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    try:
        region = db.query(Region).filter(Region.id == payload.region_id).first()
        solution = db.query(Solution).filter(Solution.id == payload.solution_id).first()
        if not region or not solution: raise HTTPException(status_code=404, detail="Region or Solution not found.")
        bom = parse_and_evaluate_requirements(solution, payload.requirement_data)
        req_payload = RequirementPayload(**payload.requirement_data)
        seq_val = db.execute(text("SELECT nextval('quote_ref_seq')")).scalar()
        quote_ref_no = f"BBS-{datetime.utcnow().year}-{seq_val:06d}"
        quote = Quote(solution_id=payload.solution_id, region_id=payload.region_id, client_name=payload.client_name, attention=payload.attention, description=payload.description, created_by_user_id=current_user.id, last_edited_by_user_id=current_user.id, quote_ref_no=quote_ref_no, version=0, status=QuoteStatus.DRAFT)
        db.add(quote)
        db.flush()
        quote.region = region; quote.solution = solution
        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="INITIAL_CREATION",
            user_id=current_user.id,
            change_reason=None,
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Database integrity error.")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating quote: {e}")
        raise HTTPException(status_code=400, detail="Error generating quote.")

@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")
    resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
    return mask_quote_financials(resp, current_user)

@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(quote_id: int, payload: QuoteUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden")
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.CHANGES_REQUESTED): raise HTTPException(status_code=409, detail="Only DRAFT or CHANGES_REQUESTED quotes can be edited")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        region = db.query(Region).filter(Region.id == payload.region_id).first()
        solution = db.query(Solution).filter(Solution.id == payload.solution_id).first()
        if not region or not solution: raise HTTPException(status_code=404, detail="Region or Solution not found.")
        bom = parse_and_evaluate_requirements(solution, payload.requirement_data)
        req_payload = RequirementPayload(**payload.requirement_data)
        quote.region = region; quote.solution = solution
        quote.client_name = payload.client_name; quote.attention = payload.attention; quote.description = payload.description
        quote.last_edited_by_user_id = current_user.id
        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="EDIT",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.change_reason),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating quote.")

@router.post("/{quote_id}/recalculate", response_model=QuoteResponse)
def recalculate_quote(quote_id: int, payload: QuoteRecalculate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden")
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.CHANGES_REQUESTED): raise HTTPException(status_code=409, detail="Only DRAFT or CHANGES_REQUESTED quotes can be recalculated")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        bom = parse_and_evaluate_requirements(quote.solution, payload.requirement_data)
        req_payload = RequirementPayload(**payload.requirement_data)
        PricingEngine.calculate_and_save_quote(db, quote, req_payload, bom)
        quote.last_edited_by_user_id = current_user.id
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="RECALCULATE",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.change_reason),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except (RequirementEngineError, PricingEngineError) as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error recalculating")


@router.delete("/{quote_id}", response_model=dict)
def delete_quote(quote_id: int, expected_version: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden")
    if expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
    quote.deleted_at = datetime.utcnow()
    quote.last_edited_by_user_id = current_user.id
    quote.version += 1
    db.commit()
    return {"status": "deleted"}

def _log_approval(db: Session, quote: Quote, action: str, from_status: QuoteStatus, to_status: QuoteStatus, user_id: int, comment: Optional[str]):
    log = QuoteApprovalLog(
        quote_id=quote.id,
        quote_version=quote.version,
        action=action,
        from_status=from_status,
        to_status=to_status,
        user_id=user_id,
        comment=comment
    )
    db.add(log)

@router.post("/{quote_id}/submit", response_model=QuoteResponse)
def submit_quote(quote_id: int, payload: QuoteSubmitAction, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id: raise HTTPException(status_code=403, detail="Forbidden")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.CHANGES_REQUESTED): raise HTTPException(status_code=409, detail="Invalid transition")
        old_status = quote.status
        quote.status = QuoteStatus.PENDING_APPROVAL
        quote.last_edited_by_user_id = current_user.id
        _log_approval(db, quote, "SUBMIT", old_status, QuoteStatus.PENDING_APPROVAL, current_user.id, payload.comment)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="SUBMIT",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.comment),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        if not committed:
            db.rollback()
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error submitting quote: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after successful submit: {e}")
            raise HTTPException(status_code=500, detail="The quote was submitted successfully, but an error occurred retrieving the updated data")

@router.post("/{quote_id}/approve", response_model=QuoteResponse)
def approve_quote(quote_id: int, payload: QuoteApproveAction, db: Session = Depends(get_db), current_user: User = Depends(require_permission("finance_tax_admin"))):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        if quote.status != QuoteStatus.PENDING_APPROVAL: raise HTTPException(status_code=409, detail="Invalid transition")
        old_status = quote.status
        quote.status = QuoteStatus.APPROVED
        quote.last_edited_by_user_id = current_user.id
        _log_approval(db, quote, "APPROVE", old_status, QuoteStatus.APPROVED, current_user.id, payload.comment)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="APPROVE",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.comment),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        if not committed:
            db.rollback()
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error approving quote: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after successful approve: {e}")
            raise HTTPException(status_code=500, detail="The quote was approved successfully, but an error occurred retrieving the updated data")

@router.post("/{quote_id}/request-changes", response_model=QuoteResponse)
def request_changes_quote(quote_id: int, payload: QuoteRequestChangesAction, db: Session = Depends(get_db), current_user: User = Depends(require_permission("finance_tax_admin"))):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        if quote.status != QuoteStatus.PENDING_APPROVAL: raise HTTPException(status_code=409, detail="Invalid transition")
        if not payload.comment: raise HTTPException(status_code=400, detail="Comment required")
        old_status = quote.status
        quote.status = QuoteStatus.CHANGES_REQUESTED
        quote.last_edited_by_user_id = current_user.id
        _log_approval(db, quote, "REQUEST_CHANGES", old_status, QuoteStatus.CHANGES_REQUESTED, current_user.id, payload.comment)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="REQUEST_CHANGES",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.comment),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        if not committed:
            db.rollback()
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error requesting changes for quote: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after successful request-changes: {e}")
            raise HTTPException(status_code=500, detail="The quote changes were requested successfully, but an error occurred retrieving the updated data")

@router.post("/{quote_id}/override-approve", response_model=QuoteResponse)
def override_approve_quote(quote_id: int, payload: QuoteOverrideApproveAction, db: Session = Depends(get_db), current_user: User = Depends(require_permission("finance_tax_admin"))):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None: raise HTTPException(status_code=404, detail="Quote not found")
        if payload.expected_version != quote.version: raise HTTPException(status_code=409, detail="Version mismatch")
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.CHANGES_REQUESTED, QuoteStatus.PENDING_APPROVAL): raise HTTPException(status_code=409, detail="Invalid transition")
        if not payload.comment: raise HTTPException(status_code=400, detail="Comment required")
        old_status = quote.status
        quote.status = QuoteStatus.APPROVED
        quote.last_edited_by_user_id = current_user.id
        _log_approval(db, quote, "OVERRIDE_APPROVE", old_status, QuoteStatus.APPROVED, current_user.id, payload.comment)
        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="OVERRIDE_APPROVE",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.comment),
            lock_quote=True,
        )
        db.add(rev)
        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        if not committed:
            db.rollback()
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error override-approving quote: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after successful override-approve: {e}")
            raise HTTPException(status_code=500, detail="The quote was approved successfully, but an error occurred retrieving the updated data")

@router.post("/{quote_id}/urgent", response_model=QuoteResponse)
def set_quote_urgency(
    quote_id: int,
    payload: QuoteUrgentAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance_tax_admin"))
):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Quote not found")
        if payload.expected_version != quote.version:
            raise HTTPException(status_code=409, detail="Version mismatch")
        if quote.status not in (QuoteStatus.PENDING_APPROVAL, QuoteStatus.CHANGES_REQUESTED):
            raise HTTPException(status_code=409, detail=f"Urgency cannot be changed for quote in {quote.status.value} status")

        # Idempotent: if already in requested state, do not duplicate audit logs
        if quote.is_urgent == payload.is_urgent:
            resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
            return mask_quote_financials(resp, current_user)

        quote.is_urgent = payload.is_urgent
        quote.last_edited_by_user_id = current_user.id

        action = "MARK_URGENT" if payload.is_urgent else "UNMARK_URGENT"
        default_comment = "Marked as urgent" if payload.is_urgent else "Urgency removed"
        comment = payload.comment.strip() if (payload.comment and payload.comment.strip()) else default_comment

        _log_approval(db, quote, action, quote.status, quote.status, current_user.id, comment)
        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error setting quote urgency: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after setting urgency: {e}")
            raise HTTPException(status_code=500, detail="Urgency was updated successfully, but an error occurred retrieving the updated data")

@router.get("/{quote_id}/history", response_model=List[QuoteApprovalLogResponse])
def get_quote_history(quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("sales_user"))):
    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")
    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")
    logs = db.query(QuoteApprovalLog).filter(QuoteApprovalLog.quote_id == quote_id).order_by(QuoteApprovalLog.created_at.asc(), QuoteApprovalLog.id.asc()).all()
    return logs


@router.get("/{quote_id}/revisions", response_model=List[QuoteRevisionResponse])
def list_quote_revisions(
    quote_id: int,
    skip: int = 0,
    limit: int = 50,
    order: str = "asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales_user")),
):
    """
    Retrieve deterministic, paginated historical revisions for a quote.

    Ordering:
    - Default is 'asc' (chronological: revision 1, 2, ...).
    - Can specify order='desc' for reverse chronological ordering.

    Pagination:
    - skip: Number of revisions to skip (offset). Must be >= 0.
    - limit: Maximum number of revisions to return. Must be >= 1. Clamped to max 100.

    Permissions:
    - Requires authenticated user with 'sales_user' permission.
    - Sales tier users can only view revisions of quotes they own.
    - Cost and margin fields within snapshot_data are masked to None for users without 'cost_visibility' (Sales, Catalog Entry).
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Invalid skip parameter: must be >= 0")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Invalid limit parameter: must be >= 1")
    if limit > 100:
        limit = 100
    if order.lower() not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="Invalid order parameter: must be 'asc' or 'desc'")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")

    revisions = get_quote_revisions(
        db=db,
        quote_id=quote_id,
        skip=skip,
        limit=limit,
        order=order
    )

    result = []
    for rev in revisions:
        rev_dict = QuoteRevisionResponse.model_validate(rev, from_attributes=True).model_dump()
        rev_dict["snapshot_data"] = mask_revision_snapshot(rev_dict["snapshot_data"], current_user)
        result.append(rev_dict)

    return result


@router.get("/{quote_id}/revisions/compare", response_model=QuoteRevisionComparisonResponse)
def compare_revisions_endpoint(
    quote_id: int,
    base_revision: Optional[int] = Query(None, description="Base revision number to compare from"),
    target_revision: Optional[int] = Query(None, description="Target revision number to compare to"),
    from_revision: Optional[int] = Query(None, description="Alias for base_revision"),
    to_revision: Optional[int] = Query(None, description="Alias for target_revision"),
    rev_a: Optional[int] = Query(None, description="Alias for base_revision"),
    rev_b: Optional[int] = Query(None, description="Alias for target_revision"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales_user")),
):
    """
    Compare two historical revisions of a quote.

    Requirements:
    - base_revision (or from_revision / rev_a): Integer >= 1
    - target_revision (or to_revision / rev_b): Integer >= 1
    - Authenticates the caller with 'sales_user' permission.
    - Enforces quote ownership for Sales tier.
    - Rejects missing revisions and cross-quote comparisons.
    - Applies role-based financial confidentiality masking before difference calculation.
    """
    base_num = base_revision if base_revision is not None else (from_revision if from_revision is not None else rev_a)
    target_num = target_revision if target_revision is not None else (to_revision if to_revision is not None else rev_b)

    if base_num is None or target_num is None:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires two revision numbers (e.g. ?base_revision=1&target_revision=2 or ?from_revision=1&to_revision=2)"
        )

    if base_num < 1 or target_num < 1:
        raise HTTPException(status_code=404, detail="Revision not found")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")

    try:
        comparison = compare_quote_revisions(
            db=db,
            quote_id=quote_id,
            base_revision_number=base_num,
            target_revision_number=target_num,
            current_user=current_user
        )
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{quote_id}/revisions/{base_revision}/compare/{target_revision}", response_model=QuoteRevisionComparisonResponse)
def compare_revisions_path_endpoint(
    quote_id: int,
    base_revision: int,
    target_revision: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales_user")),
):
    """
    Path-based alias for comparing two historical revisions of a quote.
    """
    if base_revision < 1 or target_revision < 1:
        raise HTTPException(status_code=404, detail="Revision not found")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")

    try:
        comparison = compare_quote_revisions(
            db=db,
            quote_id=quote_id,
            base_revision_number=base_revision,
            target_revision_number=target_revision,
            current_user=current_user
        )
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{quote_id}/revisions/{revision_number}", response_model=QuoteRevisionResponse)
def get_quote_revision(
    quote_id: int,
    revision_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales_user")),
):
    """
    Retrieve a specific historical revision snapshot for a quote by revision number.

    Parameters:
    - quote_id: The ID of the parent quote.
    - revision_number: The sequential revision number (1-based).

    Behavior:
    - Verifies parent quote existence and caller access before looking up the revision.
    - Returns 404 if the quote does not exist or is soft-deleted.
    - Returns 403 if a Sales user attempts to access a quote owned by another user.
    - Returns 404 if the revision number does not exist for this quote.
    - Returns the historical snapshot as stored without recalculation.
    - Applies cost_visibility rules, masking cost and margin fields for Sales/Catalog Entry users.
    """
    if revision_number < 1:
        raise HTTPException(status_code=404, detail="Revision not found")

    quote = db.query(Quote).filter(Quote.id == quote_id).first()
    if not quote or quote.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quote not found")

    if current_user.role_tier == RoleTier.SALES and quote.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this quote")

    revision = get_quote_revision_by_number(
        db=db,
        quote_id=quote_id,
        revision_number=revision_number
    )
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    rev_dict = QuoteRevisionResponse.model_validate(revision, from_attributes=True).model_dump()
    rev_dict["snapshot_data"] = mask_revision_snapshot(rev_dict["snapshot_data"], current_user)
    return rev_dict


@router.post("/{quote_id}/refresh-fx", response_model=QuoteResponse)
def refresh_quote_fx_rate(
    quote_id: int,
    payload: QuoteRefreshFXAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance_tax_admin"))
):
    committed = False
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).with_for_update().first()
        if not quote or quote.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Quote not found")

        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.CHANGES_REQUESTED):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot refresh FX rate on a quote in {quote.status.value.upper()} status. Historical quotes are immutable."
            )

        if payload.expected_version != quote.version:
            raise HTTPException(status_code=409, detail="Version mismatch: Quote was modified by another user.")

        region = db.query(Region).filter(Region.id == quote.region_id).first()
        if not region:
            raise HTTPException(status_code=404, detail="Associated region not found")

        if not region.fx_rate_to_usd or region.fx_rate_to_usd <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot refresh: Region '{region.country_name}' does not have a valid positive FX rate configured."
            )

        old_fx = quote.fx_rate_to_usd
        new_fx = Decimal(str(region.fx_rate_to_usd))

        # Recalculate local sell amount & tax without modifying the BoQ or items
        subtotal_sell_usd = Decimal(str(quote.subtotal_sell_usd))
        total_sell_local = subtotal_sell_usd / new_fx

        tax_amount = Decimal("0.0")
        if quote.tax_enabled and quote.tax_rate_percent is not None:
            tax_amount = total_sell_local * (Decimal(str(quote.tax_rate_percent)) / Decimal("100.0"))
        total_sell_local += tax_amount

        quote.fx_rate_to_usd = new_fx
        quote.fx_rate_as_of = region.fx_rate_as_of
        quote.tax_amount = tax_amount
        quote.total_sell_local = total_sell_local
        quote.version += 1
        quote.last_edited_by_user_id = current_user.id

        reason_suffix = f" Reason: {payload.comment.strip()}" if payload.comment and payload.comment.strip() else ""
        comment_text = f"FX rate refreshed: {old_fx} -> {new_fx} (Region: {region.country_name}, Currency: {quote.currency_code}).{reason_suffix}"
        _log_approval(db, quote, "REFRESH_FX_RATE", quote.status, quote.status, current_user.id, comment_text)

        rev = create_quote_revision(
            db=db,
            quote=quote,
            action="FX_REFRESH",
            user_id=current_user.id,
            change_reason=_clean_reason(payload.comment),
            lock_quote=True,
        )
        db.add(rev)

        db.commit()
        committed = True
        db.refresh(quote)
        resp = QuoteResponse.model_validate(quote, from_attributes=True).model_dump()
        return mask_quote_financials(resp, current_user)
    except HTTPException:
        if not committed:
            db.rollback()
        raise
    except Exception as e:
        if not committed:
            db.rollback()
            logger.error(f"Error refreshing FX rate for quote {quote_id}: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred while processing the request")
        else:
            logger.error(f"Error retrieving quote after refreshing FX rate: {e}")
            raise HTTPException(status_code=500, detail="The quote FX rate was refreshed successfully, but an error occurred retrieving the updated data")
