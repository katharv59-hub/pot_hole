import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import create_test_admin_token

client = TestClient(app)

def test_full_device_lifecycle():
    # 1. Admin registers device
    admin_token = create_test_admin_token("dev_lifecycle_admin@roadsentinel.io")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    reg_resp = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "firmware_version": "1.0.0"
    }, headers=admin_headers)
    assert reg_resp.status_code == 200
    dev_id = reg_resp.json()["device_id"]
    prov_secret = reg_resp.json()["provisioning_secret"]

    # 2. Provision Device (One-time secret exchange)
    prov_resp = client.post(f"/api/v1/devices/{dev_id}/provision", json={
        "provisioning_secret": prov_secret
    })
    assert prov_resp.status_code == 200
    cred = prov_resp.json()["device_credential"]

    # 3. Single-use verification: second provisioning attempt with same secret MUST fail!
    prov_reuse_resp = client.post(f"/api/v1/devices/{dev_id}/provision", json={
        "provisioning_secret": prov_secret
    })
    assert prov_reuse_resp.status_code == 401

    # 4. Authenticate Device
    auth_resp = client.post(f"/api/v1/devices/{dev_id}/auth", json={
        "device_credential": cred
    })
    assert auth_resp.status_code == 200
    dev_token = auth_resp.json()["access_token"]
    assert "access_token" in auth_resp.json()

    # 5. Disable Device
    dis_resp = client.post(f"/api/v1/devices/{dev_id}/disable", headers=admin_headers)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["status"] == "disabled"

    # Disabled device authentication MUST fail with 403
    auth_disabled_resp = client.post(f"/api/v1/devices/{dev_id}/auth", json={
        "device_credential": cred
    })
    assert auth_disabled_resp.status_code == 403

    # 6. Enable Device
    en_resp = client.post(f"/api/v1/devices/{dev_id}/enable", headers=admin_headers)
    assert en_resp.status_code == 200

    # 7. Rotate Credential
    rot_resp = client.post(f"/api/v1/devices/{dev_id}/rotate-credential", headers=admin_headers)
    assert rot_resp.status_code == 200
    new_cred = rot_resp.json()["device_credential"]
    assert new_cred != cred

    # Old credential authentication MUST fail
    auth_old_resp = client.post(f"/api/v1/devices/{dev_id}/auth", json={
        "device_credential": cred
    })
    assert auth_old_resp.status_code == 401

    # New credential authentication MUST succeed
    auth_new_resp = client.post(f"/api/v1/devices/{dev_id}/auth", json={
        "device_credential": new_cred
    })
    assert auth_new_resp.status_code == 200
