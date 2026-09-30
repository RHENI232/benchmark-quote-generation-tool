import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find root directory (4 levels up from backend/app/core/config.py is benchmark-quote-generation-tool)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Benchmark Quote Generation Tool"
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENVIRONMENT: str = "development"
    
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
