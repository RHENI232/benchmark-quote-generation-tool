from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, Enum, Numeric
from sqlalchemy.orm import relationship
import enum
import datetime
from backend.app.core.database import Base

class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SAVED = "saved"

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
    
    status = Column(Enum(QuoteStatus), default=QuoteStatus.DRAFT, nullable=False)

    solution = relationship("Solution", back_populates="quotes")
    region = relationship("Region")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    last_edited_by = relationship("User", foreign_keys=[last_edited_by_user_id])
    line_items = relationship("QuoteLineItem", back_populates="quote", cascade="all, delete-orphan")

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

    quote = relationship("Quote", back_populates="line_items")
    catalog_item = relationship("CatalogItem")
