import os
import sys
import pytest
from unittest.mock import patch

from app.database import init_database_engine

def test_database_url_missing_fails_fast():
    """TEST A: Missing DATABASE_URL fails fast with clear error."""
    with pytest.raises(RuntimeError) as exc_info:
        init_database_engine(db_url="", is_testing=False)
    assert "DATABASE_URL is not configured" in str(exc_info.value)
    assert "ROADSentinel v0.4 requires PostgreSQL" in str(exc_info.value)


def test_sqlite_url_rejected_outside_testing():
    """TEST B: SQLite DATABASE_URL is rejected in non-testing runtime."""
    with pytest.raises(RuntimeError) as exc_info:
        init_database_engine(db_url="sqlite:///./production_violation.db", is_testing=False)
    assert "SQLite is not supported as a runtime database in ROADSentinel v0.4" in str(exc_info.value)


def test_sqlite_url_allowed_in_testing_mode():
    """TEST B.1: SQLite DATABASE_URL is allowed when is_testing=True."""
    engine = init_database_engine(db_url="sqlite:///:memory:", is_testing=True)
    assert engine.dialect.name == "sqlite"


def test_missing_driver_rejected_outside_testing():
    """TEST C: Missing psycopg2 PostgreSQL driver is rejected with clear error."""
    # Temporarily hide psycopg2 from sys.modules and builtins
    with patch.dict(sys.modules, {"psycopg2": None}):
        with pytest.raises(RuntimeError) as exc_info:
            init_database_engine(
                db_url="postgresql+psycopg2://postgres:pass@localhost:5432/roadsentinel",
                is_testing=False
            )
        assert "PostgreSQL driver 'psycopg2' is not installed" in str(exc_info.value)


def test_valid_postgresql_engine_initializes():
    """TEST D: Valid PostgreSQL URL initializes SQLAlchemy engine with PostgreSQL dialect."""
    pg_url = "postgresql+psycopg2://testuser:testpass@localhost:5432/roadsentinel"
    engine = init_database_engine(db_url=pg_url, is_testing=False)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg2"
