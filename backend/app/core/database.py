import os

# Important: This workaround is required for the specific Windows Application Control
# environment this code runs in, which blocks .pyd files from executing in user space.
# We force psycopg to use its pure Python implementation, and manually add the PostgreSQL
# bin directory to the DLL search path so it can find libpq.dll.
os.environ.setdefault("PSYCOPG_IMPL", "python")
try:
    os.add_dll_directory(r"C:\Program Files\PostgreSQL\18\bin")
except FileNotFoundError:
    # If not on this specific machine, it might fail, just ignore
    pass
# Also add to PATH just in case
os.environ["PATH"] = r"C:\Program Files\PostgreSQL\18\bin" + os.pathsep + os.environ.get("PATH", "")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
