import pytest
import os
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.domain import RoadEvent, Report, MediaAsset, MLPrediction, Device, Vehicle, User, DeviceVehicleAssignment
from app.auth.security import create_device_token
from app.services.storage_service import LocalStorageAdapter, S3StorageStubAdapter
from app.services.event_service import process_event_corroboration_and_dedup
from tests.conftest import (
    create_test_admin_token,
    create_test_driver_token,
    create_test_authority_token,
    TestingSessionLocal
)

client = TestClient(app)


# --- CORRECTION 1: Historical Device -> Vehicle Assignment ---
def test_historical_device_vehicle_assignment():
    """
    Correction 1:
    - Event at T_historical (when device was assigned to Vehicle A) attributes to Vehicle A.
    - Event at T_current (after reassignment to Vehicle B) attributes to Vehicle B.
    - Event at T_unassigned (before any assignment existed) is rejected with 409 Conflict.
    """
    token_owner = create_test_driver_token("hist_owner@roadsentinel.io")
    resp_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_owner}"})
    user_id = resp_user.json()["id"]

    db = TestingSessionLocal()
    dev_id = "dev_hist_iot_01"
    veh_a = "veh_hist_alpha"
    veh_b = "veh_hist_beta"

    t0 = datetime(2026, 8, 20, 10, 0, 0)
    t1 = datetime(2026, 8, 20, 10, 30, 0) # Event under Vehicle A
    t2 = datetime(2026, 8, 20, 11, 0, 0) # Reassignment to Vehicle B
    t3 = datetime(2026, 8, 20, 11, 30, 0) # Event under Vehicle B
    t_pre = datetime(2026, 8, 20, 9, 0, 0) # Event before any assignment

    try:
        # Create Vehicles
        for vid in [veh_a, veh_b]:
            if not db.query(Vehicle).filter(Vehicle.id == vid).first():
                db.add(Vehicle(id=vid, type="car", owner_id=user_id))

        # Create Device
        dev = db.query(Device).filter(Device.id == dev_id).first()
        if not dev:
            dev = Device(id=dev_id, hardware_type="ESP32", status="active")
            db.add(dev)
        else:
            dev.status = "active"

        # Create Assignments:
        # 1. Assignment to Vehicle A (t0 to t2)
        # 2. Assignment to Vehicle B (t2 onwards)
        db.query(DeviceVehicleAssignment).filter(DeviceVehicleAssignment.device_id == dev_id).delete()
        db.add(DeviceVehicleAssignment(
            id="dva_hist_01",
            device_id=dev_id,
            vehicle_id=veh_a,
            assigned_from=t0,
            assigned_to=t2
        ))
        db.add(DeviceVehicleAssignment(
            id="dva_hist_02",
            device_id=dev_id,
            vehicle_id=veh_b,
            assigned_from=t2,
            assigned_to=None
        ))
        db.commit()
    finally:
        db.close()

    dev_jwt = create_device_token(dev_id, veh_a)
    headers = {"Authorization": f"Bearer {dev_jwt}"}

    # 1. Historical Event at t1 (under Vehicle A) -> Attributed to Vehicle A
    resp_evt_a = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "evt-hist-alpha-001",
        "vehicle_id": veh_a,
        "device_timestamp": t1.isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 17.5]}}
    }, headers=headers)
    assert resp_evt_a.status_code == 200
    evt_a_id = resp_evt_a.json()["event_id"]

    resp_get_a = client.get(f"/api/v1/events/{evt_a_id}")
    assert resp_get_a.status_code == 200
    assert resp_get_a.json()["vehicle_id"] == veh_a

    # 2. Current Event at t3 (under Vehicle B) -> Attributed to Vehicle B
    resp_evt_b = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "evt-hist-beta-002",
        "vehicle_id": veh_b,
        "device_timestamp": t3.isoformat(),
        "location": {"latitude": 19.0765, "longitude": 72.8778, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.5]}}
    }, headers=headers)
    assert resp_evt_b.status_code == 200
    evt_b_id = resp_evt_b.json()["event_id"]

    resp_get_b = client.get(f"/api/v1/events/{evt_b_id}")
    assert resp_get_b.status_code == 200
    assert resp_get_b.json()["vehicle_id"] == veh_b

    # 3. Unassigned Event at t_pre (before t0) -> 409 Conflict
    resp_evt_pre = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "evt-hist-pre-003",
        "vehicle_id": veh_a,
        "device_timestamp": t_pre.isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.0]}}
    }, headers=headers)
    assert resp_evt_pre.status_code == 409
    assert "no active vehicle assignment" in resp_evt_pre.json()["detail"].lower()


# --- CORRECTION 2: Storage Stub Honesty ---
def test_storage_stub_honesty(tmp_path):
    """
    Correction 2:
    - LocalStorageAdapter honesty: returns True if file on disk, False if nonexistent.
    - S3StorageStubAdapter honesty: marked is_stub = True, verify_object_exists returns False.
    """
    upload_dir = str(tmp_path / "uploads")
    local_adapter = LocalStorageAdapter(upload_dir)
    assert local_adapter.is_stub is False

    # Nonexistent file returns False
    assert local_adapter.verify_object_exists("nonexistent_key_123") is False

    # Existing file returns True
    test_file = os.path.join(upload_dir, "test_asset_001.jpg")
    with open(test_file, "wb") as f:
        f.write(b"dummy image data")
    assert local_adapter.verify_object_exists("test_asset_001") is True

    # S3 Stub Adapter
    s3_stub = S3StorageStubAdapter("test-bucket")
    assert s3_stub.is_stub is True
    upload_info = s3_stub.generate_presigned_upload_url("stub_key_001")
    assert upload_info["storage_provider"] == "s3_development_stub"
    assert s3_stub.verify_object_exists("stub_key_001") is False


# --- CORRECTION 3: Deterministic Corroboration Matching ---
def test_deterministic_corroboration_matching():
    """
    Correction 3:
    When multiple events qualify within temporal/spatial window,
    the deterministic winner is chosen by:
    1. Temporal distance ascending
    2. Spatial distance ascending
    3. Event ID ascending
    """
    db = TestingSessionLocal()
    base_time = datetime(2026, 8, 25, 12, 0, 0)
    
    try:
        # Create 2 candidate events
        # Cand 1: 10 seconds away, 5 meters away
        cand1 = RoadEvent(
            id="evt_cand_01",
            device_event_id="cand-01",
            device_id="dev_cand_01",
            vehicle_id="veh_test_01",
            device_timestamp=base_time + timedelta(seconds=10),
            server_timestamp=base_time,
            latitude=19.07600,
            longitude=72.87770,
            event_type="pothole",
            status="unverified"
        )
        # Cand 2: 60 seconds away, 2 meters away
        cand2 = RoadEvent(
            id="evt_cand_02",
            device_event_id="cand-02",
            device_id="dev_cand_02",
            vehicle_id="veh_test_02",
            device_timestamp=base_time + timedelta(seconds=60),
            server_timestamp=base_time,
            latitude=19.07601,
            longitude=72.87771,
            event_type="pothole",
            status="unverified"
        )
        db.query(RoadEvent).filter(RoadEvent.id.in_(["evt_cand_01", "evt_cand_02"])).delete()
        db.add(cand1)
        db.add(cand2)
        db.commit()

        # Query from a new independent device at base_time + 12s, lat 19.07600, lon 72.87770
        # Cand 1 has temporal diff = 2s. Cand 2 has temporal diff = 48s.
        # Cand 1 must be selected deterministically!
        matching, count = process_event_corroboration_and_dedup(
            db=db,
            new_device_id="dev_new_independent",
            new_vehicle_id="veh_new",
            latitude=19.07600,
            longitude=72.87770,
            device_timestamp=base_time + timedelta(seconds=12),
            event_type="pothole"
        )
        assert matching is not None
        assert matching.id == "evt_cand_01"
    finally:
        db.close()


# --- CORRECTION 7: CORS Configuration ---
def test_cors_configuration():
    """
    Correction 7:
    CORS allowed origins is configurable and does not use wildcard '*' with allow_credentials=True.
    """
    assert isinstance(settings.cors_origins_list, list)
    assert len(settings.cors_origins_list) > 0
    assert "*" not in settings.cors_origins_list


# --- CORRECTION 9: Domain & Range Constraints ---
def test_domain_boundary_constraints():
    """
    Correction 9:
    Invalid geographic coordinates, confidence, or severity are rejected by Pydantic validation (422).
    """
    token = create_test_driver_token("bounds_user@roadsentinel.io")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid Latitude (> 90) -> 422
    resp_lat = client.post("/api/v1/reports", json={
        "latitude": 95.0,
        "longitude": 72.8777,
        "description": "Invalid latitude report"
    }, headers=headers)
    assert resp_lat.status_code == 422

    # 2. Invalid Longitude (< -180) -> 422
    resp_lon = client.post("/api/v1/reports", json={
        "latitude": 19.0760,
        "longitude": -185.0,
        "description": "Invalid longitude report"
    }, headers=headers)
    assert resp_lon.status_code == 422

    # 3. Invalid Confidence (> 1.0) on ML prediction -> 422
    admin_token = create_test_admin_token("admin_bounds@roadsentinel.io")
    resp_conf = client.post("/api/v1/events/evt_cand_01/predictions", json={
        "modality": "camera",
        "model_name": "pothole-net",
        "model_version": "1.0.0",
        "predicted_type": "pothole",
        "confidence": 1.5, # Invalid > 1.0
        "inference_location": "cloud"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_conf.status_code == 422


# --- CORRECTION 10: Media Retention Expiration Population ---
def test_media_retention_expiration_population():
    """
    Correction 10:
    MediaAsset creation calculates and stores retention_expires_at matching configured retention.
    """
    driver_token = create_test_driver_token("media_retention@roadsentinel.io")
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Create report
    resp_rpt = client.post("/api/v1/reports", json={
        "latitude": 19.0760,
        "longitude": 72.8777,
        "description": "Retention test report"
    }, headers=driver_headers)
    assert resp_rpt.status_code == 200
    report_id = resp_rpt.json()["id"]

    # Request upload URL & confirm
    resp_url = client.post(f"/api/v1/reports/{report_id}/media/upload-url", headers=driver_headers)
    media_id = resp_url.json()["media_id"]

    before_confirm = datetime.now(timezone.utc)
    resp_confirm = client.post(f"/api/v1/reports/{report_id}/media/{media_id}/confirm", headers=driver_headers)
    assert resp_confirm.status_code == 200
    asset_data = resp_confirm.json()

    assert asset_data["retention_expires_at"] is not None
    # Verify retention duration matches settings (approx 90 days)
    expires_str = asset_data["retention_expires_at"].replace("Z", "+00:00")
    expires_at = datetime.fromisoformat(expires_str)
    expires_at_naive = expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at
    before_confirm_naive = before_confirm.replace(tzinfo=None)
    expected_expiry = before_confirm_naive + timedelta(days=settings.DEFAULT_MEDIA_RETENTION_DAYS)
    diff_hours = abs((expires_at_naive - expected_expiry).total_seconds()) / 3600.0
    assert diff_hours < 1.0 # Within 1 hour tolerance
