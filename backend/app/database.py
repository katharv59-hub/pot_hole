import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger("roadsentinel_database")

def init_database_engine(db_url: str = None, is_testing: bool = False):
    """
    Initializes and validates SQLAlchemy database engine.
    Enforces strict ROADSentinel v0.4 fail-fast rules:
    - Rejects missing DATABASE_URL
    - Rejects SQLite in runtime (permitted only under explicit is_testing=True)
    - Validates presence of PostgreSQL psycopg2 driver
    """
    target_url = db_url if db_url is not None else settings.DATABASE_URL

    if not target_url:
        raise RuntimeError(
            "FATAL: DATABASE_URL is not configured. "
            "ROADSentinel v0.4 requires PostgreSQL. "
            "Set DATABASE_URL=postgresql+psycopg2://user:pass@host:port/dbname"
        )

    if target_url.startswith("sqlite") and not is_testing:
        raise RuntimeError(
            "FATAL: SQLite is not supported as a runtime database in ROADSentinel v0.4. "
            "Set DATABASE_URL to a PostgreSQL connection string. "
            "SQLite is only permitted in isolated test fixtures via conftest.py."
        )

    if target_url.startswith("postgresql"):
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "FATAL: PostgreSQL driver 'psycopg2' is not installed. "
                "Install it with: pip install psycopg2-binary"
            )

    connect_args = {"check_same_thread": False} if target_url.startswith("sqlite") else {}
    return create_engine(target_url, connect_args=connect_args, echo=False)


# Module-level authoritative engine instance
_is_testing = os.getenv("TESTING", "").lower() == "true"
engine = init_database_engine(settings.DATABASE_URL, _is_testing)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
