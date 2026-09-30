import os
import sys

# Configure psycopg to use system libpq to comply with Windows Application Control policies
os.environ.setdefault("PSYCOPG_IMPL", "python")
pg_bin = r"C:\Program Files\PostgreSQL\18\bin"
if os.path.exists(pg_bin):
    try:
        os.add_dll_directory(pg_bin)
    except Exception:
        pass
    os.environ["PATH"] = pg_bin + ";" + os.environ.get("PATH", "")

import urllib.parse
from dotenv import load_dotenv
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text

def verify_and_setup_db():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("FAIL: DATABASE_URL not found in .env")
        sys.exit(1)

    # Convert SQLAlchemy psycopg URL to standard PostgreSQL connection string for psycopg
    conn_str = db_url.replace("postgresql+psycopg://", "postgresql://")
    parsed = urllib.parse.urlparse(conn_str)
    target_db = parsed.path.lstrip("/") or "benchmark_quote_generation_tool"

    # Base admin connection string to default postgres database
    admin_conn_str = conn_str.rsplit("/", 1)[0] + "/postgres"

    # 1. Verify direct psycopg connection to PostgreSQL server and check/create target database
    try:
        with psycopg.connect(admin_conn_str, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
                    print(f"DATABASE_STATUS: Created database '{target_db}' successfully.")
                else:
                    print(f"DATABASE_STATUS: Database '{target_db}' already exists.")
        print("DIRECT_PSYCOPG_CHECK: SUCCESS")
    except Exception as e:
        print(f"DIRECT_PSYCOPG_CHECK: FAILED ({type(e).__name__})")
        sys.exit(1)

    # 2. Verify SQLAlchemy connection to target database
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1;"))
            if result.scalar() == 1:
                print("SQLALCHEMY_CHECK: SUCCESS")
    except Exception as e:
        print(f"SQLALCHEMY_CHECK: FAILED ({type(e).__name__})")
        sys.exit(1)

if __name__ == "__main__":
    verify_and_setup_db()
