import os
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

from app.config import settings
from app.database import Base
import app.models.domain  # Register models

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_database_url() -> str:
    """Dynamically resolves DATABASE_URL from environment variable or app settings."""
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured for Alembic migrations.")
    return url

def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    url = get_database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
