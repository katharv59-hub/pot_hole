import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import create_test_admin_token

client = TestClient(app)

def test_user_register_and_login():
    email = "testdriver@example.com"
    password = "securepassword123"
    
    # 1. Register (Public registration forces role='driver' per Fix #5)
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "Test Driver"
    })
    assert reg_resp.status_code == 200, reg_resp.text
    data = reg_resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "driver"

    # 2. Login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data


def test_device_provisioning_flow():
    # Admin Token (created directly in test database session per Fix #5)
    admin_token = create_test_admin_token("admin_flow@roadsentinel.io")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Register Device
    reg_dev = client.post("/api/v1/devices/register", json={
        "hardware_type": "ESP32",
        "firmware_version": "1.0.0"
    }, headers=headers)
    assert reg_dev.status_code == 200, reg_dev.text
    dev_data = reg_dev.json()
    device_id = dev_data["device_id"]
    prov_secret = dev_data["provisioning_secret"]

    # 2. Provision Device
    prov_resp = client.post(f"/api/v1/devices/{device_id}/provision", json={
        "provisioning_secret": prov_secret
    })
    assert prov_resp.status_code == 200, prov_resp.text
    prov_data = prov_resp.json()
    device_credential = prov_data["device_credential"]

    # 3. Authenticate Device Session
    auth_resp = client.post(f"/api/v1/devices/{device_id}/auth", json={
        "device_credential": device_credential
    })
    assert auth_resp.status_code == 200, auth_resp.text
    auth_data = auth_resp.json()
    assert "access_token" in auth_data
