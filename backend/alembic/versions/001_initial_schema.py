"""Initial ROADSentinel v0.4 PostgreSQL + PostGIS Schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Schema creation handled by Alembic migrations
    pass

def downgrade() -> None:
    pass
