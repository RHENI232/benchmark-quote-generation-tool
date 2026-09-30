from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from backend.app.core.database import Base

class CatalogItemKind(str, enum.Enum):
    RULE_DRIVEN = "rule_driven"
    REFERENCE = "reference"

class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    lookup_key = Column(String, nullable=False, unique=True, index=True)
    kind = Column(Enum(CatalogItemKind), nullable=False)
    
    part_number = Column(String, nullable=True) # Blank allowed (e.g. support)
    description = Column(String, nullable=False)
    brand = Column(String, nullable=True)
    
    sell_price = Column(Numeric(12, 2), nullable=True)
    cost_price = Column(Numeric(12, 2), nullable=True)

    solution = relationship("Solution", back_populates="catalog_items")
