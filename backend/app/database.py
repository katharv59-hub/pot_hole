import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger("roadsentinel_database")

# PostgreSQL is the sole v0.4 runtime database. No SQLite fallback.
db_url = settings.DATABASE_URL

if not db_url:
    raise RuntimeError(
        "FATAL: DATABASE_URL is not configured. "
        "ROADSentinel v0.4 requires PostgreSQL. "
        "Set DATABASE_URL=postgresql+psycopg2://user:pass@host:port/dbname"
    )

_is_testing = os.getenv("TESTING", "").lower() == "true"

if db_url.startswith("sqlite") and not _is_testing:
    raise RuntimeError(
        "FATAL: SQLite is not supported as a runtime database in ROADSentinel v0.4. "
        "Set DATABASE_URL to a PostgreSQL connection string. "
        "SQLite is only permitted in isolated test fixtures via conftest.py."
    )

if db_url.startswith("postgresql"):
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        if not _is_testing:
            raise RuntimeError(
                "FATAL: PostgreSQL driver 'psycopg2' is not installed. "
                "Install it with: pip install psycopg2-binary"
            )
        else:
            # In test mode, the production engine is never used (conftest overrides get_db).
            # Create a dummy SQLite engine so the module can be imported.
            logger.warning("Test mode: psycopg2 not available. Production engine will not be functional.")
            db_url = "sqlite:///./test_placeholder.db"

connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(db_url, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
