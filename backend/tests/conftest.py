import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings

@pytest.fixture(scope="session")
def engine():
    return create_engine(settings.DATABASE_URL)

@pytest.fixture(scope="function")
def db(engine):
    """
    Creates a new database session for a test, wrapped in a transaction.
    Rolls back the transaction after the test completes, ensuring no
    destructive changes are made to the development database.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
