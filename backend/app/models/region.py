from sqlalchemy import Column, Integer, String, Boolean, Numeric
from backend.app.core.database import Base

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    country_name = Column(String, unique=True, index=True, nullable=False)
    currency_code = Column(String, nullable=False)
    legal_entity_name = Column(String, nullable=True)
    legal_entity_registration_number = Column(String, nullable=True)
    legal_entity_address = Column(String, nullable=True)
    legal_entity_contact = Column(String, nullable=True)
    
    tax_enabled = Column(Boolean, default=False, nullable=False)
    tax_rate_percent = Column(Numeric(5, 2), nullable=True) # e.g., 18.00 for 18%
    
    fx_rate_to_usd = Column(Numeric(12, 6), nullable=True)
    fx_rate_as_of = Column(String, nullable=True) # e.g. timestamp or date string
