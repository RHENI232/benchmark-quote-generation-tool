from sqlalchemy import Column, Integer, String, Boolean, Enum
import enum
from backend.app.core.database import Base

class RoleTier(str, enum.Enum):
    SALES = "Sales"
    CATALOG_ENTRY = "Catalog Entry"
    MANAGEMENT = "Management"
    ADMIN = "Admin"

class AccountType(str, enum.Enum):
    MANUAL = "manual"
    ENTRA_SYNCED = "entra_synced"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    role_tier = Column(Enum(RoleTier), nullable=False)
    account_type = Column(Enum(AccountType), default=AccountType.MANUAL, nullable=False)
    password_hash = Column(String, nullable=True) # Nullable for entra_synced
    enabled = Column(Boolean, default=True, nullable=False)
    entra_object_id = Column(String, nullable=True)
