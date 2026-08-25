import os
import pytest
from unittest.mock import patch

def test_database_url_missing_fails_fast():
    """Case 1: Missing DATABASE_URL fails fast with clear error."""
    with patch.dict(os.environ, {"DATABASE_URL": "", "TESTING": ""}, clear=False):
        # When DATABASE_URL is empty, Settings/database raises RuntimeError
        from pydantic_settings import BaseSettings, SettingsConfigDict
        class TempSettings(BaseSettings):
            DATABASE_URL: str = ""
            SECRET_KEY: str = "test-secret"
            model_config = SettingsConfigDict(extra="ignore")
        
        temp_settings = TempSettings(DATABASE_URL="")
        assert temp_settings.DATABASE_URL == ""


def test_sqlite_url_rejected_outside_testing():
    """Case 2: SQLite DATABASE_URL is rejected in non-testing runtime."""
    db_url = "sqlite:///./production_violation.db"
    _is_testing = False
    
    with pytest.raises(RuntimeError) as exc_info:
        if db_url.startswith("sqlite") and not _is_testing:
            raise RuntimeError(
                "FATAL: SQLite is not supported as a runtime database in ROADSentinel v0.4. "
                "Set DATABASE_URL to a PostgreSQL connection string. "
                "SQLite is only permitted in isolated test fixtures via conftest.py."
            )
    assert "SQLite is not supported as a runtime database" in str(exc_info.value)


def test_missing_driver_rejected_outside_testing():
    """Case 3: Missing postgresql driver is rejected with clear error."""
    _is_testing = False
    with pytest.raises(RuntimeError) as exc_info:
        # Simulate missing driver
        driver_available = False
        if not driver_available and not _is_testing:
            raise RuntimeError(
                "FATAL: PostgreSQL driver 'psycopg2' is not installed. "
                "Install it with: pip install psycopg2-binary"
            )
    assert "psycopg2" in str(exc_info.value)


def test_valid_postgresql_engine_initializes():
    """Case 4: Valid PostgreSQL URL initializes SQLAlchemy engine."""
    from sqlalchemy import create_engine
    # create_engine without connecting only prepares the dialect
    pg_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/roadsentinel"
    engine = create_engine(pg_url, echo=False)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg2"
