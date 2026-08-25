"""Initial ROADSentinel v0.4 PostgreSQL + PostGIS Schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-25

Creates all 11 domain tables with proper constraints, indexes,
and PostGIS spatial geometry for RoadSegment.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, server_default='driver'),
        sa.Column('saved_locations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. vehicles
    op.create_table(
        'vehicles',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('type', sa.String(), nullable=False, server_default='car'),
        sa.Column('owner_id', sa.String(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 3. devices
    op.create_table(
        'devices',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('vehicle_id', sa.String(), sa.ForeignKey('vehicles.id'), nullable=True),
        sa.Column('hardware_type', sa.String(), nullable=False, server_default='ESP32'),
        sa.Column('firmware_version', sa.String(), nullable=False, server_default='1.0.0'),
        sa.Column('credential_hash', sa.String(), nullable=True),
        sa.Column('provisioning_secret', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='provisioning'),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_devices_status', 'devices', ['status'])
    op.create_index('ix_devices_vehicle_id', 'devices', ['vehicle_id'])

    # 4. device_vehicle_assignments
    op.create_table(
        'device_vehicle_assignments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_id', sa.String(), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('vehicle_id', sa.String(), sa.ForeignKey('vehicles.id'), nullable=False),
        sa.Column('assigned_from', sa.DateTime(), nullable=False),
        sa.Column('assigned_to', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_dva_device_id', 'device_vehicle_assignments', ['device_id'])
    op.create_index('ix_dva_vehicle_id', 'device_vehicle_assignments', ['vehicle_id'])
    op.create_index('ix_dva_active', 'device_vehicle_assignments', ['device_id', 'assigned_to'])

    # 5. road_segments (with PostGIS geometry)
    op.create_table(
        'road_segments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('road_network_ref', sa.String(), nullable=True),
        sa.Column('safety_score', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
    )
    # Add PostGIS geometry column with SRID 4326 and GiST spatial index
    op.execute("""
        ALTER TABLE road_segments
        ADD COLUMN geometry geometry(LineString, 4326)
    """)
    op.execute("""
        CREATE INDEX ix_road_segments_geometry_gist
        ON road_segments USING GIST (geometry)
    """)

    # 6. road_events
    op.create_table(
        'road_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_event_id', sa.String(), nullable=False),
        sa.Column('device_id', sa.String(), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('vehicle_id', sa.String(), sa.ForeignKey('vehicles.id'), nullable=False),
        sa.Column('device_timestamp', sa.DateTime(), nullable=False),
        sa.Column('server_timestamp', sa.DateTime(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location_accuracy_m', sa.Float(), nullable=True),
        sa.Column('location_source', sa.String(), nullable=False, server_default='gnss'),
        sa.Column('road_segment_id', sa.String(), sa.ForeignKey('road_segments.id'), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False, server_default='pothole'),
        sa.Column('modality_sources', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('severity', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('severity_label', sa.String(), nullable=False, server_default='medium'),
        sa.Column('status', sa.String(), nullable=False, server_default='unverified'),
        sa.Column('schema_version', sa.String(), nullable=False, server_default='1.0'),
        sa.Column('firmware_version', sa.String(), nullable=False, server_default='1.0.0'),
        sa.Column('corroboration_count', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('device_id', 'device_event_id', name='uq_device_event_id'),
    )
    op.create_index('ix_road_events_device_id', 'road_events', ['device_id'])
    op.create_index('ix_road_events_device_event_id', 'road_events', ['device_event_id'])
    op.create_index('ix_road_events_device_timestamp', 'road_events', ['device_timestamp'])
    op.create_index('ix_road_events_status', 'road_events', ['status'])
    op.create_index('ix_road_events_lat_lon', 'road_events', ['latitude', 'longitude'])
    op.create_index('ix_road_events_vehicle_id', 'road_events', ['vehicle_id'])

    # 7. telemetry
    op.create_table(
        'telemetry',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_id', sa.String(), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('vehicle_id', sa.String(), sa.ForeignKey('vehicles.id'), nullable=False),
        sa.Column('device_timestamp', sa.DateTime(), nullable=False),
        sa.Column('server_timestamp', sa.DateTime(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('linked_event_id', sa.String(), sa.ForeignKey('road_events.id'), nullable=True),
    )
    op.create_index('ix_telemetry_device_id', 'telemetry', ['device_id'])
    op.create_index('ix_telemetry_device_timestamp', 'telemetry', ['device_timestamp'])

    # 8. reports (references users.id and road_events.id)
    op.create_table(
        'reports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('event_id', sa.String(), sa.ForeignKey('road_events.id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_reports_user_id', 'reports', ['user_id'])
    op.create_index('ix_reports_status', 'reports', ['status'])

    # 9. media_assets (references road_events.id and reports.id)
    op.create_table(
        'media_assets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('road_events.id'), nullable=True),
        sa.Column('report_id', sa.String(), sa.ForeignKey('reports.id'), nullable=True),
        sa.Column('type', sa.String(), nullable=False, server_default='image'),
        sa.Column('storage_url', sa.String(), nullable=False),
        sa.Column('captured_at', sa.DateTime(), nullable=True),
        sa.Column('retention_expires_at', sa.DateTime(), nullable=True),
        sa.Column('access_tier', sa.String(), nullable=False, server_default='raw'),
    )
    op.create_index('ix_media_assets_event_id', 'media_assets', ['event_id'])
    op.create_index('ix_media_assets_report_id', 'media_assets', ['report_id'])

    # 10. ml_predictions (references road_events.id)
    op.create_table(
        'ml_predictions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('road_events.id'), nullable=False),
        sa.Column('modality', sa.String(), nullable=False, server_default='imu'),
        sa.Column('model_name', sa.String(), nullable=False, server_default='imu-rf-v1'),
        sa.Column('model_version', sa.String(), nullable=False, server_default='1.0.0'),
        sa.Column('predicted_type', sa.String(), nullable=False, server_default='pothole'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('inference_location', sa.String(), nullable=False, server_default='cloud'),
        sa.Column('fused_from', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_ml_predictions_event_id', 'ml_predictions', ['event_id'])

    # 11. geo_index_buckets
    op.create_table(
        'geo_index_buckets',
        sa.Column('geohash', sa.String(), primary_key=True),
        sa.Column('event_count', sa.Integer(), server_default='0'),
        sa.Column('last_event_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # Drop tables in exact reverse dependency order
    op.drop_table('geo_index_buckets')
    op.drop_table('ml_predictions')
    op.drop_table('media_assets')
    op.drop_table('reports')
    op.drop_table('telemetry')
    op.drop_table('road_events')
    op.drop_table('road_segments')
    op.drop_table('device_vehicle_assignments')
    op.drop_table('devices')
    op.drop_table('vehicles')
    op.drop_table('users')
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
