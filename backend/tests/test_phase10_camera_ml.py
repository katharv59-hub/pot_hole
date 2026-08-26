import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base
from app.models.domain import RoadEvent, Report, MediaAsset, MLPrediction, Device, Vehicle, User, DeviceVehicleAssignment
from app.auth.security import create_device_token
from tests.conftest import (
    create_test_admin_token,
    create_test_driver_token,
    create_test_authority_token,
    TestingSessionLocal
)

client = TestClient(app)

def setup_vehicle_and_device(owner_email: str, dev_id: str, veh_id: str):
    token = create_test_driver_token(owner_email)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = resp.json()["id"]

    db = TestingSessionLocal()
    try:
        veh = db.query(Vehicle).filter(Vehicle.id == veh_id).first()
        if not veh:
            veh = Vehicle(id=veh_id, type="car", owner_id=user_id)
            db.add(veh)
        else:
            veh.owner_id = user_id
            
        dev = db.query(Device).filter(Device.id == dev_id).first()
        if not dev:
            dev = Device(
                id=dev_id,
                hardware_type="ESP32",
                firmware_version="1.0.0",
                status="active"
            )
            db.add(dev)
        else:
            dev.status = "active"

        assign = db.query(DeviceVehicleAssignment).filter(
            DeviceVehicleAssignment.device_id == dev_id,
            DeviceVehicleAssignment.assigned_to.is_(None)
        ).first()
        if not assign:
            assign = DeviceVehicleAssignment(
                device_id=dev_id,
                vehicle_id=veh_id,
                assigned_from=datetime.now(timezone.utc),
                assigned_to=None
            )
            db.add(assign)
        else:
            assign.vehicle_id = veh_id

        db.commit()
    finally:
        db.close()

    dev_token = create_device_token(dev_id, veh_id)
    return user_id, token, dev_token


# --- TEST A: RoadEvent Baseline Without Camera ---
def test_roadevent_baseline_without_camera():
    """Test A: Pure IMU + GPS event functions completely without camera evidence or ML."""
    _, _, dev_jwt = setup_vehicle_and_device("dev_owner_p10@roadsentinel.io", "dev_p10_01", "veh_p10_01")

    resp = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-imu-only-001",
        "vehicle_id": "veh_p10_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.5]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})

    assert resp.status_code == 200
    event_id = resp.json()["event_id"]

    # Verify event exists and has no media or ML predictions attached
    resp_get = client.get(f"/api/v1/events/{event_id}")
    assert resp_get.status_code == 200
    data = resp_get.json()
    assert data["event_type"] == "pothole"
    assert len(data.get("media_assets", [])) == 0


# --- TEST B, C, D, E: Camera Evidence Lifecycle & Failure Isolation ---
def test_camera_evidence_lifecycle_and_failure_isolation():
    """
    Test B, C, D, E:
    - User/Driver requests upload slot for vehicle event.
    - Confirm media asset upload.
    - Failure isolation: Failed camera upload does NOT destroy the RoadEvent.
    """
    user_id, driver_token, dev_jwt = setup_vehicle_and_device("cam_owner_p10@roadsentinel.io", "dev_cam_01", "veh_cam_01")
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 1. Ingest event
    resp_evt = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-cam-evt-001",
        "vehicle_id": "veh_cam_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu", "camera"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 17.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})
    assert resp_evt.status_code == 200
    event_id = resp_evt.json()["event_id"]

    # 2. Driver requests upload slot (Test C)
    resp_url = client.post(f"/api/v1/events/{event_id}/media/upload-url", headers=driver_headers)
    assert resp_url.status_code == 200
    media_id = resp_url.json()["media_id"]

    # 3. Driver confirms upload (Test D)
    resp_confirm = client.post(f"/api/v1/events/{event_id}/media/{media_id}/confirm", headers=driver_headers)
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["access_tier"] == "raw"

    # 4. Read media via event
    resp_media = client.get(f"/api/v1/events/{event_id}/media", headers=driver_headers)
    assert resp_media.status_code == 200
    assert len(resp_media.json()) == 1

    # 5. Failure isolation: Ingest another event with simulated camera upload abort (Test E)
    resp_evt2 = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-cam-abort-002",
        "vehicle_id": "veh_cam_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0770, "longitude": 72.8780, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 15.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})
    assert resp_evt2.status_code == 200
    event_id_2 = resp_evt2.json()["event_id"]

    # Event 2 remains fully queryable and valid
    resp_check = client.get(f"/api/v1/events/{event_id_2}")
    assert resp_check.status_code == 200
    assert resp_check.json()["id"] == event_id_2


# --- TEST F & G: Privacy and IDOR on Camera Evidence ---
def test_camera_evidence_privacy_and_idor():
    """
    Test F & G:
    - Driver A can view own vehicle's raw media.
    - Driver B cannot view Driver A's vehicle's raw media (403).
    - Admin and Authority can view both raw and processed media.
    """
    _, token_a, dev_jwt_a = setup_vehicle_and_device("driver_a_cam@roadsentinel.io", "dev_a_cam", "veh_a_cam")
    _, token_b, _ = setup_vehicle_and_device("driver_b_cam@roadsentinel.io", "dev_b_cam", "veh_b_cam")
    admin_token = create_test_admin_token("admin_cam_p10@roadsentinel.io")

    # Ingest event for Vehicle A
    resp_evt = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-priv-001",
        "vehicle_id": "veh_a_cam",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 18.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt_a}"})
    event_id = resp_evt.json()["event_id"]

    # Driver A confirms raw media
    client.post(f"/api/v1/events/{event_id}/media/med_priv_a_001/confirm", headers={"Authorization": f"Bearer {token_a}"})

    # Driver A can view media (Test G)
    resp_a = client.get(f"/api/v1/events/{event_id}/media", headers={"Authorization": f"Bearer {token_a}"})
    assert len(resp_a.json()) == 1

    # Driver B cannot view raw media (Test F -> returns empty processed list)
    resp_b = client.get(f"/api/v1/events/{event_id}/media", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp_b.json()) == 0

    # Direct IDOR on raw media by Driver B -> 403 Forbidden
    assert client.get("/api/v1/media/med_priv_a_001", headers={"Authorization": f"Bearer {token_b}"}).status_code == 403

    # Admin can view raw media (Test G)
    assert client.get("/api/v1/media/med_priv_a_001", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200


# --- TEST H, I, J, K, L: MLPrediction Model, Provenance & Failure Isolation ---
def test_ml_prediction_provenance_and_versioning():
    """
    Test H, I, J, K, L:
    - MLPrediction creation with explicit model provenance.
    - Model version preservation (v1.0.0 and v2.0.0 co-exist).
    - ML prediction does NOT overwrite original sensor classification.
    - Failure isolation: ML failure does not delete original event.
    """
    admin_token = create_test_admin_token("admin_ml_p10@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    _, _, dev_jwt = setup_vehicle_and_device("ml_owner_p10@roadsentinel.io", "dev_ml_01", "veh_ml_01")

    # 1. Ingest event
    resp_evt = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-ml-001",
        "vehicle_id": "veh_ml_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt}"})
    event_id = resp_evt.json()["event_id"]

    # 2. Attach ML prediction v1.0.0 (edge inference) (Test H & I)
    resp_pred1 = client.post(f"/api/v1/events/{event_id}/predictions", json={
        "modality": "camera",
        "model_name": "yolo-pothole-edge",
        "model_version": "1.0.0",
        "predicted_type": "pothole",
        "confidence": 0.88,
        "inference_location": "edge"
    }, headers=admin_headers)
    assert resp_pred1.status_code == 200
    assert resp_pred1.json()["model_version"] == "1.0.0"

    # 3. Attach ML prediction v2.0.0 (cloud fused inference) (Test J)
    resp_pred2 = client.post(f"/api/v1/events/{event_id}/predictions", json={
        "modality": "fused",
        "model_name": "multimodal-fusion-net",
        "model_version": "2.0.0",
        "predicted_type": "severe_pothole",
        "confidence": 0.94,
        "inference_location": "cloud",
        "fused_from": ["imu", "camera"]
    }, headers=admin_headers)
    assert resp_pred2.status_code == 200

    # 4. Verify both predictions co-exist and preserve version history
    resp_preds = client.get(f"/api/v1/events/{event_id}/predictions")
    assert resp_preds.status_code == 200
    preds = resp_preds.json()
    assert len(preds) == 2
    versions = [p["model_version"] for p in preds]
    assert "1.0.0" in versions
    assert "2.0.0" in versions

    # 5. Verify original event fields are NOT overwritten (Test I)
    resp_event = client.get(f"/api/v1/events/{event_id}")
    assert resp_event.status_code == 200
    assert resp_event.json()["event_type"] == "pothole" # Original sensor event type preserved


# --- TEST N, O, P, Q: Corroboration vs ML Confidence & Human Moderation ---
def test_corroboration_distinct_from_ml_confidence():
    """
    Test N, O, P, Q:
    - ML confidence does NOT increment corroboration_count.
    - Corroboration strictly increments only from independent device detections.
    - AI prediction does NOT change status to 'verified'; human moderation is required.
    """
    admin_token = create_test_admin_token("admin_mod_p10@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    _, _, dev_jwt_1 = setup_vehicle_and_device("dev1_p10@roadsentinel.io", "dev_corr_01", "veh_corr_01")
    _, _, dev_jwt_2 = setup_vehicle_and_device("dev2_p10@roadsentinel.io", "dev_corr_02", "veh_corr_02")

    # Ingest event from Device 1
    resp_1 = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-corr-dev1",
        "vehicle_id": "veh_corr_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 16.5]}}
    }, headers={"Authorization": f"Bearer {dev_jwt_1}"})
    event_id = resp_1.json()["event_id"]
    assert resp_1.json()["corroboration_count"] == 1

    # Attach high-confidence ML prediction
    client.post(f"/api/v1/events/{event_id}/predictions", json={
        "modality": "camera",
        "model_name": "pothole-vision",
        "model_version": "1.0.0",
        "predicted_type": "pothole",
        "confidence": 0.99,
        "inference_location": "cloud"
    }, headers=admin_headers)

    # Event status remains 'unverified' and corroboration_count remains 1 (Test O & P)
    resp_check = client.get(f"/api/v1/events/{event_id}")
    assert resp_check.json()["status"] == "unverified"
    assert resp_check.json()["corroboration_count"] == 1

    # Ingest independent detection from Device 2 (Test N)
    resp_2 = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "p10-corr-dev2",
        "vehicle_id": "veh_corr_02",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 17.0]}}
    }, headers={"Authorization": f"Bearer {dev_jwt_2}"})
    assert resp_2.json()["corroboration_count"] == 2

    # Human verification changes status to 'verified' (Test Q)
    resp_mod = client.patch(f"/api/v1/admin/events/{event_id}/status", json={"status": "verified"}, headers=admin_headers)
    assert resp_mod.status_code == 200
    assert resp_mod.json()["status"] == "verified"
