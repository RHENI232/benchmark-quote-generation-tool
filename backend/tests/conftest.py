import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings
from backend.app.core.database import Base

@pytest.fixture(scope="session")
def engine():
    # Construct test database URL
    base_url = settings.DATABASE_URL.rsplit('/', 1)[0]
    test_db_url = f"{base_url}/benchmark_test_db"

    # Ensure Windows psycopg compatibility (matching database.py)
    import os
    os.environ.setdefault("PSYCOPG_IMPL", "python")
    try:
        os.add_dll_directory(r"C:\Program Files\PostgreSQL\18\bin")
    except FileNotFoundError:
        pass

    from sqlalchemy import text
    engine_for_creation = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with engine_for_creation.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='benchmark_test_db'")).scalar()
            if not exists:
                conn.execute(text("CREATE DATABASE benchmark_test_db"))
    except Exception as e:
        print(f"Note: Could not automatically create test database: {e}")
    finally:
        engine_for_creation.dispose()

    test_engine = create_engine(test_db_url, pool_pre_ping=True)

    # Reset test database schema
    Base.metadata.drop_all(bind=test_engine)

    # We must also drop the sequence if it exists (CASCADE on drop_all usually doesn't hit standalone sequences)
    try:
        with test_engine.connect() as conn:
            conn.execute(text("DROP SEQUENCE IF EXISTS quote_ref_seq CASCADE"))
            conn.commit()
    except:
        pass

    Base.metadata.create_all(bind=test_engine)

    # Create the sequence required by quote generation
    try:
        with test_engine.connect() as conn:
            conn.execute(text("CREATE SEQUENCE quote_ref_seq START 1000"))
            conn.commit()
    except Exception as e:
        print(f"Note: Could not create quote_ref_seq: {e}")

    # Seed the test database (tests assume it is pre-seeded)
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionTest()
    try:
        from backend.seed import seed_solutions, seed_regions, seed_admin_user, seed_catalog_items
        solution = seed_solutions(db)
        seed_regions(db)
        seed_admin_user(db)
        seed_catalog_items(db, solution)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    yield test_engine

    # Teardown after all tests
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def db(engine):
    """
    Creates a new database session for a test, wrapped in a transaction.
    Rolls back the transaction after the test completes, ensuring no
    destructive changes are made to the development database.
    """
    connection = engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
        join_transaction_mode="create_savepoint"
    )
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.deps import get_db

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

