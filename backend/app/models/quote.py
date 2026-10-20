from typing import Optional
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, Enum, Numeric, Boolean, UniqueConstraint, event, DDL
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum
import datetime
from backend.app.core.database import Base

class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"

class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    
    client_name = Column(String, nullable=False)
    quote_ref_no = Column(String, nullable=False, unique=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    attention = Column(String, nullable=True)
    description = Column(String, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    
    requirement_data = Column(JSON, nullable=False, default={})
    
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_edited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    status = Column(Enum(QuoteStatus, values_callable=lambda obj: [e.value for e in obj]), default=QuoteStatus.DRAFT, nullable=False)
    is_urgent = Column(Boolean, nullable=False, default=False)

    # CP-4 Snapshot Fields
    currency_code = Column(String, nullable=False, default="USD")
    fx_rate_to_usd = Column(Numeric(12, 6), nullable=False, default=1.000000)
    fx_rate_as_of = Column(String, nullable=True)
    tax_enabled = Column(Boolean, nullable=False, default=False)
    tax_rate_percent = Column(Numeric(5, 2), nullable=True)
    subtotal_sell_usd = Column(Numeric(14, 2), nullable=False, default=0)
    subtotal_cost_usd = Column(Numeric(14, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(14, 2), nullable=False, default=0)
    total_sell_local = Column(Numeric(14, 2), nullable=False, default=0)
    legal_entity_name = Column(String, nullable=True)
    legal_entity_registration_number = Column(String, nullable=True)
    legal_entity_address = Column(String, nullable=True)
    legal_entity_contact = Column(String, nullable=True)

    solution = relationship("Solution", back_populates="quotes")
    region = relationship("Region")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    last_edited_by = relationship("User", foreign_keys=[last_edited_by_user_id])
    line_items = relationship("QuoteLineItem", back_populates="quote", cascade="all, delete-orphan")
    approval_logs = relationship("QuoteApprovalLog", back_populates="quote", order_by="QuoteApprovalLog.created_at.asc()", cascade="all, delete-orphan")
    revisions = relationship("QuoteRevision", back_populates="quote", order_by="QuoteRevision.revision_number.asc()")

class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    catalog_item_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=True)
    
    part_number = Column(String, nullable=True)
    description = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    section = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    
    quantity = Column(Integer, nullable=False, default=1)
    
    # Snapshots for pricing
    unit_sell_price_snapshot = Column(Numeric(12, 2), nullable=False)
    unit_cost_price_snapshot = Column(Numeric(12, 2), nullable=False)
    line_sell_total = Column(Numeric(14, 2), nullable=False, default=0)
    line_cost_total = Column(Numeric(14, 2), nullable=False, default=0)
    margin_percent = Column(Numeric(7, 2), nullable=False, default=0)

    quote = relationship("Quote", back_populates="line_items")
    catalog_item = relationship("CatalogItem")

class QuoteApprovalLog(Base):
    __tablename__ = "quote_approval_logs"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    quote_version = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    from_status = Column(Enum(QuoteStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    to_status = Column(Enum(QuoteStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    quote = relationship("Quote", back_populates="approval_logs")
    user = relationship("User")

    @property
    def user_email(self) -> Optional[str]:
        return self.user.email if self.user else None

    @property
    def user_role(self) -> Optional[str]:
        return self.user.role_tier.value if self.user and self.user.role_tier else None

class QuoteRevision(Base):
    __tablename__ = "quote_revisions"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False, index=True)
    revision_number = Column(Integer, nullable=False)
    quote_version = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    change_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    snapshot_data = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)

    __table_args__ = (
        UniqueConstraint("quote_id", "revision_number", name="uq_quote_revisions_quote_id_revision_number"),
    )

    quote = relationship("Quote", back_populates="revisions")
    user = relationship("User")

    @property
    def user_email(self) -> Optional[str]:
        return self.user.email if self.user else None

    @property
    def user_role(self) -> Optional[str]:
        return self.user.role_tier.value if self.user and self.user.role_tier else None


# Application/ORM-level immutability enforcement
@event.listens_for(QuoteRevision, "before_update")
def _prevent_orm_revision_update(mapper, connection, target):
    raise RuntimeError("QuoteRevision instances are immutable and cannot be updated.")


@event.listens_for(QuoteRevision, "before_delete")
def _prevent_orm_revision_delete(mapper, connection, target):
    raise RuntimeError("QuoteRevision instances are immutable and cannot be deleted.")


# Database-level PostgreSQL trigger attachment for schema creation events (e.g. Base.metadata.create_all)
_trigger_func_ddl = DDL("""
CREATE OR REPLACE FUNCTION prevent_quote_revision_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'quote_revisions records are immutable and cannot be updated or deleted';
END;
$$ LANGUAGE plpgsql;
""")

_trigger_ddl = DDL("""
DROP TRIGGER IF EXISTS trg_quote_revisions_immutable ON quote_revisions;
CREATE TRIGGER trg_quote_revisions_immutable
BEFORE UPDATE OR DELETE ON quote_revisions
FOR EACH ROW EXECUTE FUNCTION prevent_quote_revision_mutation();
""")

event.listen(
    QuoteRevision.__table__,
    "after_create",
    _trigger_func_ddl.execute_if(dialect="postgresql")
)
event.listen(
    QuoteRevision.__table__,
    "after_create",
    _trigger_ddl.execute_if(dialect="postgresql")
)
