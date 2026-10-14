import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import model_validator

# Find root directory (4 levels up from backend/app/core/config.py is benchmark-quote-generation-tool)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Benchmark Quote Generation Tool"
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENVIRONMENT: str = "development"
    
    # Email & Invitation Settings
    EMAIL_PROVIDER: str = "console"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Benchmark Broadcast Systems"
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_email_settings(self):
        provider = (self.EMAIL_PROVIDER or "console").strip().lower()
        if provider not in ("console", "gmail"):
            raise ValueError(f"Invalid EMAIL_PROVIDER '{self.EMAIL_PROVIDER}'. Must be 'console' or 'gmail'.")
        self.EMAIL_PROVIDER = provider

        if provider == "gmail":
            missing = []
            if not self.SMTP_USERNAME:
                missing.append("SMTP_USERNAME")
            if not self.SMTP_PASSWORD:
                missing.append("SMTP_PASSWORD")
            if not self.SMTP_FROM_EMAIL:
                if self.SMTP_USERNAME:
                    self.SMTP_FROM_EMAIL = self.SMTP_USERNAME
                else:
                    missing.append("SMTP_FROM_EMAIL")
            if missing:
                raise ValueError(
                    f"Missing required Gmail SMTP settings when EMAIL_PROVIDER='gmail': {', '.join(missing)}. "
                    "Please configure them in your root .env file."
                )
        return self

settings = Settings()
