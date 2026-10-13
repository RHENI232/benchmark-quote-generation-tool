import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from backend.app.core.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True, index=True)
    bool_value = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

