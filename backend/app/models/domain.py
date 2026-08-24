import uuid
import os
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, JSON, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid(prefix: str = "") -> str:
    val = str(uuid.uuid4()).replace("-", "")[:12]
    return f"{prefix}_{val}" if prefix else val

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("usr"))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="driver")  # driver, admin, authority
    saved_locations = Column(JSON, nullable=True, default=list) # List of saved locations
    created_at = Column(DateTime, default=utc_now)
    
    reports = relationship("Report", back_populates="user")


class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("veh"))
    type = Column(String, nullable=False, default="car") # 2-wheeler, car, bus, truck, fleet, other
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=utc_now)
    
    devices = relationship("Device", back_populates="vehicle")
    assignments = relationship("DeviceVehicleAssignment", back_populates="vehicle")


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("dev"))
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=True)
    hardware_type = Column(String, nullable=False, default="ESP32") # ESP32, edge-ai, other
    firmware_version = Column(String, nullable=False, default="1.0.0")
    credential_hash = Column(String, nullable=True)
    provisioning_secret = Column(String, nullable=True)
    status = Column(String, nullable=False, default="provisioning") # provisioning, active, disabled, revoked
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    
    vehicle = relationship("Vehicle", back_populates="devices")
    assignments = relationship("DeviceVehicleAssignment", back_populates="device")


class DeviceVehicleAssignment(Base):
    __tablename__ = "device_vehicle_assignments"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("dva"))
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    assigned_from = Column(DateTime, nullable=False, default=utc_now)
    assigned_to = Column(DateTime, nullable=True) # None means currently active
    
    device = relationship("Device", back_populates="assignments")
    vehicle = relationship("Vehicle", back_populates="assignments")


class RoadEvent(Base):
    __tablename__ = "road_events"
    __table_args__ = (
        UniqueConstraint("device_id", "device_event_id", name="uq_device_event_id"),
    )
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("evt"))
    device_event_id = Column(String, nullable=False) # Idempotency key per device
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    device_timestamp = Column(DateTime, nullable=False)
    server_timestamp = Column(DateTime, nullable=False, default=utc_now)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_accuracy_m = Column(Float, nullable=True)
    location_source = Column(String, nullable=False, default="gnss") # gnss, network, fused
    
    road_segment_id = Column(String, ForeignKey("road_segments.id"), nullable=True)
    event_type = Column(String, nullable=False, default="pothole") # pothole, speed_breaker, crack, waterlogging, debris, manhole, edge_damage, other
    modality_sources = Column(JSON, nullable=False, default=lambda: ["imu"]) # ["imu"], ["camera"], ["imu", "camera"]
    confidence = Column(Float, nullable=False, default=0.8) # 0.0 - 1.0
    severity = Column(Float, nullable=False, default=0.5) # 0.0 - 1.0 float
    severity_label = Column(String, nullable=False, default="medium") # low, medium, high, critical
    status = Column(String, nullable=False, default="unverified") # unverified, verified, duplicate, resolved
    schema_version = Column(String, nullable=False, default="1.0")
    firmware_version = Column(String, nullable=False, default="1.0.0")
    corroboration_count = Column(Integer, nullable=False, default=1)
    
    media_assets = relationship("MediaAsset", back_populates="event", cascade="all, delete-orphan")
    ml_predictions = relationship("MLPrediction", back_populates="event", cascade="all, delete-orphan")


class Telemetry(Base):
    __tablename__ = "telemetry"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("tel"))
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    device_timestamp = Column(DateTime, nullable=False)
    server_timestamp = Column(DateTime, nullable=False, default=utc_now)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    label = Column(String, nullable=True) # smooth_road, confirmed_pothole, etc.
    linked_event_id = Column(String, ForeignKey("road_events.id"), nullable=True)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("med"))
    event_id = Column(String, ForeignKey("road_events.id"), nullable=True)
    report_id = Column(String, ForeignKey("reports.id"), nullable=True)
    type = Column(String, nullable=False, default="image") # image, video
    storage_url = Column(String, nullable=False)
    captured_at = Column(DateTime, default=utc_now)
    retention_expires_at = Column(DateTime, nullable=True)
    access_tier = Column(String, nullable=False, default="raw") # raw, processed
    
    event = relationship("RoadEvent", back_populates="media_assets")
    report = relationship("Report", back_populates="media_assets")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("pred"))
    event_id = Column(String, ForeignKey("road_events.id"), nullable=False)
    modality = Column(String, nullable=False, default="imu") # imu, camera, fused
    model_name = Column(String, nullable=False, default="imu-rf-v1")
    model_version = Column(String, nullable=False, default="1.0.0")
    predicted_type = Column(String, nullable=False, default="pothole")
    confidence = Column(Float, nullable=False, default=0.8)
    inference_location = Column(String, nullable=False, default="cloud") # edge, cloud
    fused_from = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    
    event = relationship("RoadEvent", back_populates="ml_predictions")


# Use PostGIS geometry type for RoadSegment when GeoAlchemy2 is available.
# Falls back to JSON only in isolated test environments without PostGIS.
try:
    from geoalchemy2 import Geometry as PostGISGeometry
    _GEOMETRY_TYPE = PostGISGeometry('LINESTRING', srid=4326)
except ImportError:
    _GEOMETRY_TYPE = JSON  # Test-only fallback


class RoadSegment(Base):
    __tablename__ = "road_segments"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("seg"))
    road_network_ref = Column(String, nullable=True) # OSM way ID or external ref
    geometry = Column(_GEOMETRY_TYPE, nullable=True)  # PostGIS LINESTRING(4326) with GiST index
    safety_score = Column(Float, nullable=False, default=100.0) # 0 - 100
    last_updated = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index('ix_road_segments_geometry_gist', 'geometry', postgresql_using='gist'),
    ) if _GEOMETRY_TYPE is not JSON else ()


class GeoIndexBucket(Base):
    __tablename__ = "geo_index_buckets"
    
    geohash = Column(String, primary_key=True)
    event_count = Column(Integer, default=0)
    last_event_at = Column(DateTime, default=utc_now)


class Report(Base):
    __tablename__ = "reports"
    
    id = Column(String, primary_key=True, default=lambda: generate_uuid("rpt"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    event_id = Column(String, ForeignKey("road_events.id"), nullable=True)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending") # pending, verified, resolved
    created_at = Column(DateTime, default=utc_now)
    
    user = relationship("User", back_populates="reports")
    media_assets = relationship("MediaAsset", back_populates="report", cascade="all, delete-orphan")
