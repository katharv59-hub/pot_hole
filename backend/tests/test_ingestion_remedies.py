import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import create_test_admin_token

client = TestClient(app)

def test_raw_imu_below_threshold_rejection():
    """Fix #3: Acceleration below 11.5 m/s² must produce explicit rejection/no-event outcome."""
    admin_token = create_test_admin_token("below_thresh_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    dev_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_assigned_01"}, headers=admin_headers)
    dev_id = dev_reg.json()["device_id"]
    prov_secret = dev_reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    headers = {"Authorization": f"Bearer {dev_token}"}

    below_thresh_payload = {
        "schema_version": "1.0",
        "device_event_id": "evt-below-thresh-01",
        "vehicle_id": "veh_assigned_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0728, "longitude": 72.8826, "source": "gnss"},
        "modality_sources": ["imu"],
        "sensor_data": {
            "imu_window": {
                "z_accel": [9.8, 10.1, 10.2, 9.8]
            }
        }
    }

    resp = client.post("/api/v1/events", json=below_thresh_payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "rejected"
    assert "below minimum detection threshold" in data["warnings"][0]


def test_canonical_event_deduplication_no_duplicate_rows():
    """Fix #2: Corroborating an existing canonical event must NOT create a second duplicate RoadEvent row."""
    admin_token = create_test_admin_token("dedup_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Device A
    dev1_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_dev1"}, headers=admin_headers)
    dev1_id = dev1_reg.json()["device_id"]
    prov1 = client.post(f"/api/v1/devices/{dev1_id}/provision", json={"provisioning_secret": dev1_reg.json()["provisioning_secret"]})
    auth1 = client.post(f"/api/v1/devices/{dev1_id}/auth", json={"device_credential": prov1.json()["device_credential"]})
    headers1 = {"Authorization": f"Bearer {auth1.json()['access_token']}"}

    payload1 = {
        "schema_version": "1.0",
        "device_event_id": "dev1-evt-001",
        "vehicle_id": "veh_dev1",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "event_type": "pothole",
        "confidence": 0.85,
        "severity": 0.70
    }
    resp1 = client.post("/api/v1/events", json=payload1, headers=headers1)
    assert resp1.status_code == 200
    canonical_id = resp1.json()["event_id"]

    # Device B (Independent device)
    dev2_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_dev2"}, headers=admin_headers)
    dev2_id = dev2_reg.json()["device_id"]
    prov2 = client.post(f"/api/v1/devices/{dev2_id}/provision", json={"provisioning_secret": dev2_reg.json()["provisioning_secret"]})
    auth2 = client.post(f"/api/v1/devices/{dev2_id}/auth", json={"device_credential": prov2.json()["device_credential"]})
    headers2 = {"Authorization": f"Bearer {auth2.json()['access_token']}"}

    payload2 = {
        "schema_version": "1.0",
        "device_event_id": "dev2-evt-001",
        "vehicle_id": "veh_dev2",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.0760, "longitude": 72.8777, "source": "gnss"},
        "event_type": "pothole",
        "confidence": 0.88,
        "severity": 0.70
    }
    resp2 = client.post("/api/v1/events", json=payload2, headers=headers2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["event_id"] == canonical_id
    assert data2["corroboration_count"] == 2


def test_admin_event_status_endpoint_alignment():
    """Fix #9: Verify PATCH /admin/events/{id}/status endpoint availability."""
    admin_token = create_test_admin_token("status_endpoint_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Ingest dummy event
    dev_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32", "vehicle_id": "veh_stat_01"}, headers=admin_headers)
    dev_id = dev_reg.json()["device_id"]
    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": dev_reg.json()["provisioning_secret"]})
    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": prov.json()["device_credential"]})
    dev_headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}

    evt_resp = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "stat-evt-100",
        "vehicle_id": "veh_stat_01",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"},
        "event_type": "pothole",
        "confidence": 0.9,
        "severity": 0.8
    }, headers=dev_headers)
    evt_id = evt_resp.json()["event_id"]

    patch_resp = client.patch(f"/api/v1/admin/events/{evt_id}/status", json={"status": "verified"}, headers=admin_headers)
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["status"] == "verified"
