import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import create_test_admin_token

client = TestClient(app)

def test_public_registration_role_escalation_prevented():
    """Fix #5: Public registration must force role='driver' and ignore self-escalation payloads."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "attacker@example.com",
        "password": "password123",
        "name": "Attacker Account",
        "role": "admin"  # Attempt self-escalation!
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["role"] == "driver"  # Forced driver role!


def test_device_revocation_instant_rejection():
    """Fix #6: Revoking a device must invalidate active access tokens immediately."""
    admin_token = create_test_admin_token("sec_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    dev_reg = client.post("/api/v1/devices/register", json={"hardware_type": "ESP32"}, headers=admin_headers)
    assert dev_reg.status_code == 200, dev_reg.text
    dev_id = dev_reg.json()["device_id"]
    prov_secret = dev_reg.json()["provisioning_secret"]

    prov = client.post(f"/api/v1/devices/{dev_id}/provision", json={"provisioning_secret": prov_secret})
    cred = prov.json()["device_credential"]

    auth = client.post(f"/api/v1/devices/{dev_id}/auth", json={"device_credential": cred})
    dev_token = auth.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    revoke_resp = client.post(f"/api/v1/devices/{dev_id}/revoke", headers=admin_headers)
    assert revoke_resp.status_code == 200, revoke_resp.text

    ingest_resp = client.post("/api/v1/events", json={
        "schema_version": "1.0",
        "device_event_id": "evt-after-revoke",
        "vehicle_id": "veh_test",
        "device_timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": 19.07, "longitude": 72.88, "source": "gnss"}
    }, headers=dev_headers)
    assert ingest_resp.status_code == 403
