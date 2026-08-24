import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import create_test_admin_token

client = TestClient(app)

def test_telemetry_ingestion_isolation():
    """Phase 5: Telemetry path must authenticate device, validate vehicle, and NOT create RoadEvent or MLPrediction."""
    admin_token = create_test_admin_token("telemetry_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Setup device
    dev_reg = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "vehicle_id": "veh_tel_001"
    }, headers=admin_headers)
    dev_id = dev_reg.json()["device_id"]
    prov_secret = dev_reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    # 1. Post Telemetry
    tel_payload = {
        "vehicle_id": "veh_tel_001",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": 19.0760,
        "longitude": 72.8777,
        "raw_payload": {"z_accel": [9.8, 9.9, 9.8]},
        "label": "smooth_road"
    }

    resp = client.post("/api/v1/telemetry", json=tel_payload, headers=dev_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "accepted"

    # 2. Verify that Telemetry did NOT create any RoadEvent entries
    events = client.get("/api/v1/events").json()
    assert len(events) == 0

    # 3. Vehicle mismatch rejection test -> Expect 409
    mismatch_payload = {
        "vehicle_id": "veh_UNASSIGNED_FAKE",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": 19.0760,
        "longitude": 72.8777,
        "raw_payload": {"z_accel": [9.8]}
    }
    mismatch_resp = client.post("/api/v1/telemetry", json=mismatch_payload, headers=dev_headers)
    assert mismatch_resp.status_code == 409
