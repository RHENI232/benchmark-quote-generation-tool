from sqlalchemy import Column, Integer, String, Numeric, JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Solution(Base):
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=True)
    
    # Store dynamic schema for form fields
    requirement_schema = Column(JSON, nullable=False, default={})
    
    # Store formula/rules config
    business_rules = Column(JSON, nullable=False, default={})
    
    default_margin_percent = Column(Numeric(5, 2), nullable=False, default=15.00)

    # Relationships
    catalog_items = relationship("CatalogItem", back_populates="solution")
    quotes = relationship("Quote", back_populates="solution")
