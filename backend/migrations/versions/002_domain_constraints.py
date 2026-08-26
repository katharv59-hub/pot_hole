"""Domain & Geographic Boundary Constraints

Revision ID: 002_domain_constraints
Revises: 001_initial_schema
Create Date: 2026-08-26

Adds PostgreSQL check constraints for latitude, longitude, confidence, and severity
across road_events, telemetry, reports, and ml_predictions tables.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_domain_constraints'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Check constraints on road_events
    op.create_check_constraint(
        'chk_roadevent_latitude',
        'road_events',
        'latitude >= -90.0 AND latitude <= 90.0'
    )
    op.create_check_constraint(
        'chk_roadevent_longitude',
        'road_events',
        'longitude >= -180.0 AND longitude <= 180.0'
    )
    op.create_check_constraint(
        'chk_roadevent_confidence',
        'road_events',
        'confidence >= 0.0 AND confidence <= 1.0'
    )
    op.create_check_constraint(
        'chk_roadevent_severity',
        'road_events',
        'severity >= 0.0 AND severity <= 1.0'
    )

    # 2. Check constraints on telemetry
    op.create_check_constraint(
        'chk_telemetry_latitude',
        'telemetry',
        'latitude >= -90.0 AND latitude <= 90.0'
    )
    op.create_check_constraint(
        'chk_telemetry_longitude',
        'telemetry',
        'longitude >= -180.0 AND longitude <= 180.0'
    )

    # 3. Check constraints on reports
    op.create_check_constraint(
        'chk_report_latitude',
        'reports',
        'latitude >= -90.0 AND latitude <= 90.0'
    )
    op.create_check_constraint(
        'chk_report_longitude',
        'reports',
        'longitude >= -180.0 AND longitude <= 180.0'
    )

    # 4. Check constraints on ml_predictions
    op.create_check_constraint(
        'chk_mlpred_confidence',
        'ml_predictions',
        'confidence >= 0.0 AND confidence <= 1.0'
    )


def downgrade() -> None:
    op.drop_constraint('chk_mlpred_confidence', 'ml_predictions', type_='check')
    op.drop_constraint('chk_report_longitude', 'reports', type_='check')
    op.drop_constraint('chk_report_latitude', 'reports', type_='check')
    op.drop_constraint('chk_telemetry_longitude', 'telemetry', type_='check')
    op.drop_constraint('chk_telemetry_latitude', 'telemetry', type_='check')
    op.drop_constraint('chk_roadevent_severity', 'road_events', type_='check')
    op.drop_constraint('chk_roadevent_confidence', 'road_events', type_='check')
    op.drop_constraint('chk_roadevent_longitude', 'road_events', type_='check')
    op.drop_constraint('chk_roadevent_latitude', 'road_events', type_='check')
