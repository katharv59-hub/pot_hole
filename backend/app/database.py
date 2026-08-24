import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger("roadsentinel_database")

db_url = settings.DATABASE_URL
connect_args = {}

# Handle PostgreSQL driver check gracefully if psycopg2 is absent on dev machine
if db_url.startswith("postgresql"):
    try:
        import psycopg2
        connect_args = {}
    except ImportError:
        logger.warning("PostgreSQL driver psycopg2 not found locally. Falling back to SQLite local database.")
        db_url = "sqlite:///./roadsentinel.db"
        connect_args = {"check_same_thread": False}
elif db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
