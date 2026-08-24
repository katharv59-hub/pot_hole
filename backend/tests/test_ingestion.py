import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_raw_event_ingestion_and_idempotency():
    # 1. Setup Device & Vehicle via Admin API
    admin_reg = client.post("/api/v1/auth/register", json={
        "email": "ingest_admin@example.com",
        "password": "adminpassword123",
        "name": "Ingest Admin",
        "role": "admin"
    })
    admin_token = admin_reg.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    dev_reg = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "vehicle_id": "veh_test_001"
    }, headers=admin_headers)
    dev_id = dev_reg.json()["device_id"]
    prov_secret = dev_reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    # 2. Ingest raw IMU event (Constraint #3: threshold mode)
    event_payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-evt-1001",
        "vehicle_id": "veh_test_001",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": 19.0728,
            "longitude": 72.8826,
            "accuracy_m": 3.5,
            "source": "gnss"
        },
        "modality_sources": ["imu"],
        "sensor_data": {
            "imu_window": {
                "z_accel": [9.8, 14.5, 19.2, 9.8] # Spike > 18.0 -> Critical severity
            }
        },
        "firmware_version": "1.0.0"
    }

    resp1 = client.post("/api/v1/events", json=event_payload, headers=dev_headers)
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()
    assert data1["status"] == "accepted"
    assert data1["corroboration_count"] == 1

    # 3. Retry same payload -> Spec §8 Idempotency check returns duplicate status
    resp2 = client.post("/api/v1/events", json=event_payload, headers=dev_headers)
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["status"] == "duplicate"
    assert data2["duplicate_of"] == data1["event_id"]


def test_vehicle_assignment_mismatch_rejection():
    # Attempt to post event with vehicle_id not assigned to device -> Expect 409
    admin_reg = client.post("/api/v1/auth/register", json={
        "email": "mismatch_admin@example.com",
        "password": "adminpassword123",
        "name": "Mismatch Admin",
        "role": "admin"
    })
    admin_token = admin_reg.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    dev_reg = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "vehicle_id": "veh_real_assignment"
    }, headers=admin_headers)
    dev_id = dev_reg.json()["device_id"]
    prov_secret = dev_reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    mismatch_payload = {
        "schema_version": "1.0",
        "device_event_id": "esp32-evt-mismatch",
        "vehicle_id": "veh_FAKE_UNASSIGNED", # Mismatch!
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {"imu_window": {"z_accel": [9.8, 15.0]}}
    }

    resp = client.post("/api/v1/events", json=mismatch_payload, headers=dev_headers)
    assert resp.status_code == 409
